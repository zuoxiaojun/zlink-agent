"""Tests for agent/core/tool_dispatcher.py — async batch dispatch (P1: sequential)."""

from __future__ import annotations

import asyncio
import json
import sys
import time

import pytest

from agent.core.kernel_types import (
    AgentEvent,
    AgentLoopConfig,
    CancelToken,
    ToolExecutionEnd,
    ToolExecutionStart,
)
from agent.core.llm_providers.base import ToolCallPayload
from agent.core.tool_dispatcher import dispatch_tool_batch
from agent.tools.registry import registry, tool_result


@pytest.fixture(autouse=True)
def clean_tool_registry():
    """Snapshot the registry, run the test, restore it (same as test_tool_registry)."""
    saved_before = set(registry.get_all_tool_names())
    saved_hooks_before = list(registry._before_hooks)
    saved_hooks_after = list(registry._after_hooks)
    yield
    for name in set(registry.get_all_tool_names()) - saved_before:
        try:
            registry.deregister(name)
        except Exception:
            pass
    registry._before_hooks[:] = saved_hooks_before
    registry._after_hooks[:] = saved_hooks_after


def _make_config(**kw) -> AgentLoopConfig:
    base = {"model": "test-model"}
    base.update(kw)
    return AgentLoopConfig(**base)


class _EventRecorder:
    def __init__(self) -> None:
        self.events: list[AgentEvent] = []

    async def __call__(self, event: AgentEvent) -> None:
        self.events.append(event)


def _run(coro):
    return asyncio.run(coro)


def test_batch_sequential_order_and_events():
    """P1: tools run strictly in call order; Start/End events per tool."""
    order: list[str] = []

    def handler_a(args: dict) -> str:
        order.append("a")
        return tool_result(data={"x": args.get("x")})

    def handler_b(args: dict) -> str:
        order.append("b")
        return tool_result(data={"y": args.get("y")})

    registry.register(name="t_a", toolset="test", schema={"type": "object"}, handler=handler_a)
    registry.register(name="t_b", toolset="test", schema={"type": "object"}, handler=handler_b)

    recorder = _EventRecorder()
    calls = [
        ToolCallPayload(id="c1", name="t_a", arguments='{"x": 1}'),
        ToolCallPayload(id="c2", name="t_b", arguments='{"y": 2}'),
    ]
    batch = _run(
        dispatch_tool_batch(
            calls,
            max_result_length=sys.maxsize,
            token=CancelToken(),
            emit=recorder,
            config=_make_config(),
        )
    )

    assert order == ["a", "b"]
    assert [r.tool_call_id for r in batch.messages] == ["c1", "c2"]
    assert json.loads(batch.messages[0].result)["data"]["x"] == 1
    assert json.loads(batch.messages[1].result)["data"]["y"] == 2

    starts = [e for e in recorder.events if isinstance(e, ToolExecutionStart)]
    ends = [e for e in recorder.events if isinstance(e, ToolExecutionEnd)]
    assert [e.tool_name for e in starts] == ["t_a", "t_b"]
    assert [e.tool_name for e in ends] == ["t_a", "t_b"]
    assert ends[0].tool_call_id == "c1"


def test_invalid_json_arguments_produce_error_result():
    registry.register(name="t_json", toolset="test", schema={"type": "object"}, handler=lambda args: "unused")
    recorder = _EventRecorder()
    batch = _run(
        dispatch_tool_batch(
            [ToolCallPayload(id="c1", name="t_json", arguments="{not json")],
            max_result_length=sys.maxsize,
            token=CancelToken(),
            emit=recorder,
            config=_make_config(),
        )
    )
    assert batch.messages[0].is_error is True
    assert "Invalid JSON arguments" in batch.messages[0].result


def test_before_tool_call_block_skips_handler():
    called: list[str] = []

    def handler(args: dict) -> str:
        called.append("handler")
        return tool_result()

    registry.register(name="t_block", toolset="test", schema={"type": "object"}, handler=handler)

    async def _block_hook(name: str, args: dict, token: CancelToken) -> dict:
        return {"__block__": True, "__reason__": "test blocked"}

    recorder = _EventRecorder()
    batch = _run(
        dispatch_tool_batch(
            [ToolCallPayload(id="c1", name="t_block", arguments="{}")],
            max_result_length=sys.maxsize,
            token=CancelToken(),
            emit=recorder,
            config=_make_config(before_tool_call=_block_hook),
        )
    )
    assert called == []
    assert batch.messages[0].is_error is True
    assert "test blocked" in batch.messages[0].result


def test_before_tool_call_can_rewrite_args():
    seen: list[dict] = []

    def handler(args: dict) -> str:
        seen.append(args)
        return tool_result(data={"v": args.get("v")})

    registry.register(name="t_rewrite", toolset="test", schema={"type": "object"}, handler=handler)

    def _rewrite_hook(name: str, args: dict, token: CancelToken) -> dict:
        return {**args, "v": args.get("v", "") + "-hooked"}

    batch = _run(
        dispatch_tool_batch(
            [ToolCallPayload(id="c1", name="t_rewrite", arguments='{"v": "orig"}')],
            max_result_length=sys.maxsize,
            token=CancelToken(),
            emit=_EventRecorder(),
            config=_make_config(before_tool_call=_rewrite_hook),
        )
    )
    assert seen == [{"v": "orig-hooked"}]
    assert json.loads(batch.messages[0].result)["data"]["v"] == "orig-hooked"


def test_handler_exception_becomes_error_result():
    def handler(args: dict) -> str:
        raise RuntimeError("boom")

    registry.register(name="t_raise", toolset="test", schema={"type": "object"}, handler=handler)
    batch = _run(
        dispatch_tool_batch(
            [ToolCallPayload(id="c1", name="t_raise", arguments="{}")],
            max_result_length=sys.maxsize,
            token=CancelToken(),
            emit=_EventRecorder(),
            config=_make_config(),
        )
    )
    assert batch.messages[0].is_error is True
    assert "boom" in batch.messages[0].result


def test_after_tool_call_hook_rewrites_result():
    def handler(args: dict) -> str:
        return tool_result(data={"v": "raw"})

    registry.register(name="t_after", toolset="test", schema={"type": "object"}, handler=handler)

    def _after_hook(name: str, args: dict, result: str, token: CancelToken) -> str:
        payload = json.loads(result)
        payload["data"]["v"] = "redacted"
        return json.dumps(payload, ensure_ascii=False)

    batch = _run(
        dispatch_tool_batch(
            [ToolCallPayload(id="c1", name="t_after", arguments="{}")],
            max_result_length=sys.maxsize,
            token=CancelToken(),
            emit=_EventRecorder(),
            config=_make_config(after_tool_call=_after_hook),
        )
    )
    assert json.loads(batch.messages[0].result)["data"]["v"] == "redacted"


def test_truncation_applies_per_result():
    def handler(args: dict) -> str:
        return tool_result(data={"big": "x" * 500})

    registry.register(name="t_big", toolset="test", schema={"type": "object"}, handler=handler)
    recorder = _EventRecorder()
    batch = _run(
        dispatch_tool_batch(
            [ToolCallPayload(id="c1", name="t_big", arguments="{}")],
            max_result_length=100,
            token=CancelToken(),
            emit=recorder,
            config=_make_config(),
        )
    )
    assert len(batch.messages[0].result) == 100 + len("\n\n...")
    assert batch.messages[0].result.endswith("\n\n...")
    # ToolExecutionEnd carries the truncated result too
    ends = [e for e in recorder.events if isinstance(e, ToolExecutionEnd)]
    assert ends[0].result.endswith("\n\n...")


def test_bridge_dispatch_hook_used_for_bridge_tools():
    from agent.tools.tool_search import BRIDGE_TOOL_NAMES

    bridge_name = next(iter(BRIDGE_TOOL_NAMES))  # tool_search
    bridge_calls: list[str] = []
    registry.register(name=bridge_name, toolset="test", schema={"type": "object"}, handler=lambda args: "unused")

    def _bridge(name: str, args: dict) -> str:
        bridge_calls.append(name)
        return tool_result(data={"bridged": True})

    batch = _run(
        dispatch_tool_batch(
            [ToolCallPayload(id="c1", name=bridge_name, arguments="{}")],
            max_result_length=sys.maxsize,
            token=CancelToken(),
            emit=_EventRecorder(),
            config=_make_config(bridge_dispatch=_bridge),
        )
    )
    assert bridge_calls == [bridge_name]
    assert json.loads(batch.messages[0].result)["data"]["bridged"] is True


def test_approval_blocked_denied_returns_denial():
    from agent.tools.security_hooks import ApprovalBlockedError

    def handler(args: dict) -> str:
        return tool_result()

    registry.register(name="t_approve", toolset="test", schema={"type": "object"}, handler=handler, risk_level="high")

    def _raise_hook(name, args):
        raise ApprovalBlockedError(tool_name=name, tool_args=args, reason="need approval")

    registry.add_before_hook(_raise_hook)
    decisions: list[str] = []
    try:

        async def _on_blocked(name: str, reason: str) -> str:
            decisions.append(name)
            return "denied"

        batch = _run(
            dispatch_tool_batch(
                [ToolCallPayload(id="c1", name="t_approve", arguments="{}")],
                max_result_length=sys.maxsize,
                token=CancelToken(),
                emit=_EventRecorder(),
                config=_make_config(on_approval_blocked=_on_blocked),
            )
        )
    finally:
        registry.remove_before_hook(_raise_hook)

    assert decisions == ["t_approve"]
    assert batch.messages[0].is_error is True
    assert "用户拒绝了操作" in batch.messages[0].result


def test_approval_blocked_approved_runs_handler_directly():
    from agent.tools.security_hooks import ApprovalBlockedError

    ran: list[str] = []

    def handler(args: dict) -> str:
        ran.append("handler")
        return tool_result(data={"approved": True})

    registry.register(name="t_approve2", toolset="test", schema={"type": "object"}, handler=handler, risk_level="high")

    def _raise_hook(name, args):
        raise ApprovalBlockedError(tool_name=name, tool_args=args, reason="need approval")

    registry.add_before_hook(_raise_hook)
    try:

        async def _on_blocked(name: str, reason: str) -> str:
            return "approved"

        batch = _run(
            dispatch_tool_batch(
                [ToolCallPayload(id="c1", name="t_approve2", arguments="{}")],
                max_result_length=sys.maxsize,
                token=CancelToken(),
                emit=_EventRecorder(),
                config=_make_config(on_approval_blocked=_on_blocked),
            )
        )
    finally:
        registry.remove_before_hook(_raise_hook)

    assert ran == ["handler"]
    assert json.loads(batch.messages[0].result)["data"]["approved"] is True


def test_sequential_batch_sleeps_are_serial():
    """P1 sanity: two 0.15s tools take >= ~0.3s (sequential, not parallel yet)."""

    def sleepy(args: dict) -> str:
        time.sleep(0.15)
        return tool_result()

    registry.register(name="t_sleep", toolset="test", schema={"type": "object"}, handler=sleepy)
    start = time.monotonic()
    batch = _run(
        dispatch_tool_batch(
            [
                ToolCallPayload(id="c1", name="t_sleep", arguments="{}"),
                ToolCallPayload(id="c2", name="t_sleep", arguments="{}"),
            ],
            max_result_length=sys.maxsize,
            token=CancelToken(),
            emit=_EventRecorder(),
            config=_make_config(),
        )
    )
    elapsed = time.monotonic() - start
    assert len(batch.messages) == 2
    assert elapsed >= 0.28, f"expected serial execution, took {elapsed:.3f}s"
