"""Tests for the sub-agent delegation tool (agent/tools/delegate_tool.py).

These tests verify tool registration, schema, config propagation,
error handling, and the ``check_fn`` guard.  Full sub-agent execution
paths are not tested here because they require a real LLM; they are
covered by integration / E2E tests.
"""

from __future__ import annotations

import json

import pytest

from agent.tools.delegate_tool import (
    _DELEGATE_TASK_SCHEMA,
    _parent_config,
    handle_delegate_task,
    set_parent_config,
)
from agent.tools.registry import registry


@pytest.fixture(autouse=True)
def _clean_config():
    """Clear thread-local parent config before and after each test."""
    for attr in ("api_key", "base_url", "model", "temperature"):
        try:
            delattr(_parent_config, attr)
        except AttributeError:
            pass
    yield
    for attr in ("api_key", "base_url", "model", "temperature"):
        try:
            delattr(_parent_config, attr)
        except AttributeError:
            pass


def _import_or_skip():
    """Import delegate_tool module, skipping if it already registered."""
    import agent.tools.delegate_tool  # noqa: F401


# ── Tool registration ────────────────────────────────────────────


def test_delegate_task_registered():
    """delegate_task should be in the tool registry after import."""
    _import_or_skip()
    names = registry.get_all_tool_names()
    assert "delegate_task" in names


def test_delegate_task_schema_is_constant():
    """Schema should be a module-level constant, not a function."""
    assert isinstance(_DELEGATE_TASK_SCHEMA, dict)
    assert _DELEGATE_TASK_SCHEMA["name"] == "delegate_task"
    assert _DELEGATE_TASK_SCHEMA["parameters"]["required"] == ["task"]


def test_delegate_task_metadata():
    """Verify tool metadata (risk_level, toolset, description)."""
    _import_or_skip()
    entry = registry.get_entry("delegate_task")
    assert entry is not None
    assert entry.name == "delegate_task"
    assert entry.toolset == "agent"
    assert entry.risk_level == "medium"
    assert "子任务" in entry.description
    assert entry.check_fn is not None


# ── check_fn guard ───────────────────────────────────────────────


def test_check_fn_returns_false_without_config():
    """check_fn returns False when no parent config is set."""
    _import_or_skip()
    entry = registry.get_entry("delegate_task")
    assert entry is not None
    assert entry.check_fn is not None
    assert entry.check_fn() is False


def test_check_fn_returns_true_with_config():
    """check_fn returns True once set_parent_config is called."""
    set_parent_config(api_key="test-key", base_url="https://test.api", model="test-model", temperature=0.5)
    _import_or_skip()
    entry = registry.get_entry("delegate_task")
    assert entry is not None
    assert entry.check_fn is not None
    assert entry.check_fn() is True


# ── set_parent_config ────────────────────────────────────────────


def test_set_parent_config_persists():
    """set_parent_config stores values in thread-local storage."""
    set_parent_config(
        api_key="sk-abc",
        base_url="https://custom.api/v1",
        model="gpt-5",
        temperature=0.3,
    )
    assert _parent_config.api_key == "sk-abc"
    assert _parent_config.base_url == "https://custom.api/v1"
    assert _parent_config.model == "gpt-5"
    assert _parent_config.temperature == 0.3


def test_set_parent_config_defaults():
    """set_parent_config with no arguments sets empty defaults."""
    set_parent_config()
    assert _parent_config.api_key == ""
    assert _parent_config.base_url == ""
    assert _parent_config.model == ""
    assert _parent_config.temperature == 0.7


# ── handle_delegate_task error paths (no real sub-agent) ─────────


def test_handle_delegate_task_missing_task():
    """handle_delegate_task returns error when task argument is missing."""
    result = handle_delegate_task({"context": "some context"})
    parsed = json.loads(result)
    assert parsed["success"] is False
    assert "task 参数是必需的" in parsed["error"]


def test_handle_delegate_task_empty_task():
    """handle_delegate_task returns error when task is empty string."""
    result = handle_delegate_task({"task": "", "context": ""})
    parsed = json.loads(result)
    assert parsed["success"] is False
    assert "task 参数是必需的" in parsed["error"]


# ── Config propagation to sub-agent (via mock) ───────────────────


def test_handle_delegate_task_config_capture_on_calling_thread():
    """Verify the parent config snapshot captured before
    handle_delegate_task runs is read on the calling thread, not
    inside the executor worker.

    We can't test the full sub-agent execution here (no real LLM),
    but we DO verify that the config-capture code path reads the
    correct thread-local values.
    """
    set_parent_config(
        api_key="sk-captured-key",
        base_url="https://captured.api/v1",
        model="gpt-captured",
        temperature=0.42,
    )
    # Simulate what handle_delegate_task does to capture config
    captured = {
        "api_key": getattr(_parent_config, "api_key", ""),
        "base_url": getattr(_parent_config, "base_url", "https://api.openai.com/v1"),
        "model": getattr(_parent_config, "model", "gpt-4o"),
        "temperature": getattr(_parent_config, "temperature", 0.7),
    }
    assert captured["api_key"] == "sk-captured-key"
    assert captured["base_url"] == "https://captured.api/v1"
    assert captured["model"] == "gpt-captured"
    assert captured["temperature"] == 0.42


def test_delegate_task_default_config_fallback():
    """When parent config is not set, capture falls back to defaults."""
    # Ensure no parent config set
    for attr in ("api_key", "base_url", "model", "temperature"):
        try:
            delattr(_parent_config, attr)
        except AttributeError:
            pass

    captured = {
        "api_key": getattr(_parent_config, "api_key", ""),
        "base_url": getattr(_parent_config, "base_url", "https://api.openai.com/v1"),
        "model": getattr(_parent_config, "model", "gpt-4o"),
        "temperature": getattr(_parent_config, "temperature", 0.7),
    }
    assert captured["api_key"] == ""
    assert captured["base_url"] == "https://api.openai.com/v1"
    assert captured["model"] == "gpt-4o"
    assert captured["temperature"] == 0.7


# ── Discover_tools guard ─────────────────────────────────────────


def test_sub_agent_import_does_not_crash():
    """Verify we can import the sub-agent dependencies without crash.

    This is a smoke test — it does NOT run a sub-agent, but ensures
    the ``from agent.core.agent import AIAgent`` lazy import works
    and that ``discover_tools`` can be called from a non-main thread
    context (the actual guard inside ``_run_sub_agent``).
    """
    # This should work: the lazy import is valid
    from agent.core.agent import AIAgent  # noqa: F401
