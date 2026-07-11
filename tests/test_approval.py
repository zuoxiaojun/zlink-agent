"""Tests for the approval security system (approval_mode + risk_level + approval_hook).

These tests verify the three approval modes and the BeforeHook
blocking/pass-through logic.  They do NOT depend on a running backend
or WebSocket connection — they test the hook function directly.
"""

from __future__ import annotations

import json
import time

import pytest

from agent.tools.registry import registry
from agent.tools.security_hooks import _APPROVAL_TTL, _APPROVED_CALLS


@pytest.fixture(autouse=True)
def clean_registry():
    """Snapshot and restore registry state."""
    saved = set(registry.get_all_tool_names())
    saved_before = list(registry._before_hooks)
    saved_after = list(registry._after_hooks)
    yield
    for name in set(registry.get_all_tool_names()) - saved:
        try:
            registry.deregister(name)
        except Exception:
            pass
    registry._before_hooks[:] = saved_before
    registry._after_hooks[:] = saved_after


def _register_test_tool(name: str, risk_level: str = "low"):
    """Register a minimal test tool with given risk_level."""

    def handler(args: dict) -> str:
        return json.dumps({"success": True, "data": "ok"})

    registry.register(
        name=name,
        toolset="test",
        schema={"type": "object", "properties": {}},
        handler=handler,
        risk_level=risk_level,
    )


def _make_approval_hook():
    """Import and return a fresh approval_hook with clean state."""
    from agent.tools.security_hooks import approval_hook, clear_approvals, record_approval

    clear_approvals()
    return approval_hook, record_approval, clear_approvals


def test_allow_all_mode_passes_all_tools(monkeypatch):
    """When approval_mode='allow_all', all tools pass through regardless of risk."""
    _register_test_tool("test_low", risk_level="low")
    _register_test_tool("test_med", risk_level="medium")
    _register_test_tool("test_high", risk_level="high")
    hook, _, _ = _make_approval_hook()

    from agent.config_model import AppConfig

    monkeypatch.setattr(
        "agent.config_manager.load",
        lambda: AppConfig(approval_mode="allow_all"),
    )

    for tool in ("test_low", "test_med", "test_high"):
        result = hook(tool, {"msg": "hello"})
        assert "__block__" not in result, f"{tool} should not be blocked in allow_all mode"
        assert result.get("msg") == "hello"


def test_reject_all_blocks_medium_and_high(monkeypatch):
    """When approval_mode='reject_all', medium and high risk tools are blocked."""
    _register_test_tool("test_low", risk_level="low")
    _register_test_tool("test_med", risk_level="medium")
    _register_test_tool("test_high", risk_level="high")
    hook, _, _ = _make_approval_hook()

    from agent.config_model import AppConfig

    monkeypatch.setattr(
        "agent.config_manager.load",
        lambda: AppConfig(approval_mode="reject_all"),
    )

    # Low risk passes
    result = hook("test_low", {})
    assert "__block__" not in result

    # Medium risk blocked
    result = hook("test_med", {})
    assert "__block__" in result
    assert "已被管理员禁用" in result.get("__reason__", "")

    # High risk blocked
    result = hook("test_high", {})
    assert "__block__" in result
    assert "已被管理员禁用" in result.get("__reason__", "")


def test_approve_mode_blocks_high_risk(monkeypatch):
    """When approval_mode='approve', high-risk tools are blocked unless pre-approved."""
    _register_test_tool("test_low", risk_level="low")
    _register_test_tool("test_high", risk_level="high")
    hook, record, _ = _make_approval_hook()

    from agent.config_model import AppConfig

    monkeypatch.setattr(
        "agent.config_manager.load",
        lambda: AppConfig(approval_mode="approve"),
    )

    # Low risk still passes
    result = hook("test_low", {})
    assert "__block__" not in result

    # High risk blocked without approval
    result = hook("test_high", {"path": "/tmp/test"})
    assert "__block__" in result
    assert "需要你的确认" in result.get("__reason__", "")


def test_approve_mode_passes_pre_approved_calls(monkeypatch):
    """High-risk tools pass when pre-approved via record_approval()."""
    _register_test_tool("test_high", risk_level="high")
    hook, record, _ = _make_approval_hook()

    from agent.config_model import AppConfig

    monkeypatch.setattr(
        "agent.config_manager.load",
        lambda: AppConfig(approval_mode="approve"),
    )

    args = {"path": "/tmp/test", "content": "data"}
    record("test_high", args)

    # Same tool + args passes now
    result = hook("test_high", dict(args))
    assert "__block__" not in result
    assert result.get("path") == "/tmp/test"


def test_approval_cache_expires(monkeypatch):
    """Pre-approvals expire after _APPROVAL_TTL seconds."""
    _register_test_tool("test_high", risk_level="high")
    hook, record, _ = _make_approval_hook()

    from agent.config_model import AppConfig

    monkeypatch.setattr(
        "agent.config_manager.load",
        lambda: AppConfig(approval_mode="approve"),
    )

    # Manually set an old approval timestamp using the same key format
    # that approval_hook uses internally.
    args = {"action": "delete"}
    key = f"test_high:{json.dumps(args, ensure_ascii=False, sort_keys=True)}"
    _APPROVED_CALLS[key] = time.monotonic() - _APPROVAL_TTL - 1

    # Should be blocked because cache entry expired
    result = hook("test_high", args)
    assert "__block__" in result


def test_unknown_tool_defaults_to_low(monkeypatch):
    """Unregistered tools should default to 'low' risk and never block."""
    hook, _, _ = _make_approval_hook()

    from agent.config_model import AppConfig

    monkeypatch.setattr(
        "agent.config_manager.load",
        lambda: AppConfig(approval_mode="reject_all"),
    )

    result = hook("nonexistent_tool", {})
    assert "__block__" not in result


def test_approval_integration_with_dispatch(monkeypatch):
    """End-to-end: approval_hook integrated via registry.dispatch()."""
    _register_test_tool("test_high", risk_level="high")
    hook, record, _ = _make_approval_hook()

    from agent.config_model import AppConfig

    monkeypatch.setattr(
        "agent.config_manager.load",
        lambda: AppConfig(approval_mode="approve"),
    )

    # Register the hook
    registry.add_before_hook(hook)
    try:
        # Without approval → blocked
        result = registry.dispatch("test_high", {"x": "y"})
        payload = json.loads(result)
        assert payload["success"] is False
        assert "需要你的确认" in payload["error"]

        # With approval → passes
        record("test_high", {"x": "y"})
        result = registry.dispatch("test_high", {"x": "y"})
        payload = json.loads(result)
        assert payload["success"] is True
    finally:
        registry.remove_before_hook(hook)
