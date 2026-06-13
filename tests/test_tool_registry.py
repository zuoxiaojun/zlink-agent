"""Tests for the ToolRegistry + Hook chain.

These tests guard the M1-era tool dispatch logic.  The hook chain is
the only thing standing between a bad tool call and the real
filesystem / shell / network, so we want to know immediately if a
refactor breaks the ``__block__`` protocol or the after-hook
result-rewriting contract.
"""

from __future__ import annotations

import json

import pytest

from agent.tools.registry import registry


@pytest.fixture(autouse=True)
def clean_tool_registry():
    """Snapshot the registry, run the test, restore it.

    Several test modules register their own tools and we don't want
    leakage.  This is the lightest-weight isolation we can do
    without rewriting the ToolRegistry API.
    """
    saved_before = set(registry.get_all_tool_names())
    saved_hooks_before = list(registry._before_hooks)
    saved_hooks_after = list(registry._after_hooks)
    yield
    # Best-effort: drop any tool the test added, restore hook lists.
    for name in set(registry.get_all_tool_names()) - saved_before:
        try:
            registry.deregister(name)
        except Exception:
            pass
    registry._before_hooks[:] = saved_hooks_before
    registry._after_hooks[:] = saved_hooks_after


def _register_stub_tool(name: str, return_value: str = "stub-ok"):
    """Register a no-op tool that returns ``return_value`` JSON.

    ToolRegistry.register's real signature is
    ``(name, toolset, schema, handler, ...)`` — we use ``toolset="test"``
    and put the JSON schema under the ``schema`` keyword (NOT
    ``parameters``, which doesn't exist).
    """
    from agent.tools.registry import tool_result

    def _handler(args: dict) -> str:
        return tool_result(data={"echo": args.get("msg", ""), "tag": return_value})

    registry.register(
        name=name,
        toolset="test",
        schema={
            "type": "object",
            "properties": {"msg": {"type": "string"}},
        },
        handler=_handler,
    )


def test_register_and_dispatch_basic():
    """A registered tool can be dispatched with args and returns its
    handler's result."""
    _register_stub_tool("test_echo")
    result = registry.dispatch("test_echo", {"msg": "hi"})
    payload = json.loads(result)
    assert payload["success"] is True
    assert payload["data"]["echo"] == "hi"


def test_dispatch_unknown_tool_returns_error():
    """Unknown tool name returns a structured error — never raises."""
    result = registry.dispatch("does_not_exist_tool_xyz", {})
    payload = json.loads(result)
    assert payload["success"] is False
    assert "Unknown tool" in payload["error"]


def test_before_hook_can_block_dispatch():
    """A before-hook returning ``__block__: True`` must short-circuit
    dispatch and return a structured error."""

    def block_hook(tool_name, args):
        if tool_name == "test_block":
            return {**args, "__block__": True, "__reason__": "test blocked"}
        return args

    _register_stub_tool("test_block")
    registry.add_before_hook(block_hook)
    try:
        result = registry.dispatch("test_block", {"msg": "x"})
        payload = json.loads(result)
        assert payload["success"] is False
        assert "test blocked" in payload["error"]
    finally:
        registry.remove_before_hook(block_hook)


def test_before_hook_can_modify_args():
    """A before-hook can rewrite the args dict before the handler
    sees them.  This is how audit / redaction hooks work."""

    def rewrite_hook(tool_name, args):
        if tool_name == "test_rewrite":
            return {**args, "msg": args.get("msg", "") + " [rewritten]"}
        return args

    _register_stub_tool("test_rewrite")
    registry.add_before_hook(rewrite_hook)
    try:
        result = registry.dispatch("test_rewrite", {"msg": "hello"})
        payload = json.loads(result)
        assert payload["data"]["echo"] == "hello [rewritten]"
    finally:
        registry.remove_before_hook(rewrite_hook)


def test_after_hook_can_modify_result():
    """An after-hook can rewrite the result string the handler
    returned.  Used by sanitisation / log redaction."""

    def strip_after(tool_name, args, result):
        if tool_name == "test_strip":
            data = json.loads(result)
            data["data"]["echo"] = "[REDACTED]"
            return json.dumps(data, ensure_ascii=False)
        return result

    _register_stub_tool("test_strip")
    registry.add_after_hook(strip_after)
    try:
        result = registry.dispatch("test_strip", {"msg": "secret"})
        payload = json.loads(result)
        assert payload["data"]["echo"] == "[REDACTED]"
    finally:
        registry.remove_after_hook(strip_after)
