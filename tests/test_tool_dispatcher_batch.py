"""Tests for agent/core/tool_dispatcher.py — async batch dispatch (P2: parallel with sequential degradation)."""

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
    """P2: Start/End events and results stay in call order (parallel-safe)."""

    def handler_a(args: dict) -> str:
        return tool_result(data={"x": args.get("x")})

    def handler_b(args: dict) -> str:
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


def test_parallel_batch_sleeps_are_concurrent():
    """P2: default-parallel tools run concurrently — elapsed ≈ max, not Σ."""

    def sleepy(args: dict) -> str:
        time.sleep(0.25)
        return tool_result()

    registry.register(name="t_sleep", toolset="test", schema={"type": "object"}, handler=sleepy)
    start = time.monotonic()
    batch = _run(
        dispatch_tool_batch(
            [
                ToolCallPayload(id="c1", name="t_sleep", arguments="{}"),
                ToolCallPayload(id="c2", name="t_sleep", arguments="{}"),
                ToolCallPayload(id="c3", name="t_sleep", arguments="{}"),
            ],
            max_result_length=sys.maxsize,
            token=CancelToken(),
            emit=_EventRecorder(),
            config=_make_config(),
        )
    )
    elapsed = time.monotonic() - start
    assert len(batch.messages) == 3
    assert elapsed < 0.60, f"expected concurrent execution, took {elapsed:.3f}s (3 x 0.25s serial = 0.75s)"


def test_parallel_preserves_call_order_in_results_and_events():
    def sleeper(args: dict) -> str:
        delay = args.get("d", 0.0)
        time.sleep(delay)
        return tool_result(data={"tag": args.get("tag")})

    registry.register(name="t_psleep", toolset="test", schema={"type": "object"}, handler=sleeper)
    recorder = _EventRecorder()
    calls = [
        ToolCallPayload(id="c1", name="t_psleep", arguments='{"tag": "first", "d": 0.25}'),
        ToolCallPayload(id="c2", name="t_psleep", arguments='{"tag": "second", "d": 0.0}'),
        ToolCallPayload(id="c3", name="t_psleep", arguments='{"tag": "third", "d": 0.1}'),
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
    # transcript order == original call order (fast "second" must not jump ahead)
    assert [r.tool_call_id for r in batch.messages] == ["c1", "c2", "c3"]
    assert [json.loads(r.result)["data"]["tag"] for r in batch.messages] == ["first", "second", "third"]
    # ToolExecutionStart and ToolExecutionEnd both in call order
    starts = [e.tool_call_id for e in recorder.events if isinstance(e, ToolExecutionStart)]
    ends = [e.tool_call_id for e in recorder.events if isinstance(e, ToolExecutionEnd)]
    assert starts == ["c1", "c2", "c3"]
    assert ends == ["c1", "c2", "c3"]


def test_sequential_tool_degrades_whole_batch():
    order: list[str] = []

    def parallel_sleep(args: dict) -> str:
        order.append(args.get("tag"))
        time.sleep(0.15)
        return tool_result()

    def seq_tool(args: dict) -> str:
        order.append("seq")
        time.sleep(0.15)
        return tool_result()

    registry.register(name="t_ps", toolset="test", schema={"type": "object"}, handler=parallel_sleep)
    registry.register(
        name="t_seq", toolset="test", schema={"type": "object"}, handler=seq_tool, execution_mode="sequential"
    )

    start = time.monotonic()
    batch = _run(
        dispatch_tool_batch(
            [
                ToolCallPayload(id="c1", name="t_ps", arguments='{"tag": "a"}'),
                ToolCallPayload(id="c2", name="t_seq", arguments="{}"),
                ToolCallPayload(id="c3", name="t_ps", arguments='{"tag": "c"}'),
            ],
            max_result_length=sys.maxsize,
            token=CancelToken(),
            emit=_EventRecorder(),
            config=_make_config(),
        )
    )
    elapsed = time.monotonic() - start
    assert order == ["a", "seq", "c"], f"must run strictly serially, got {order}"
    assert elapsed >= 0.40, f"expected serial (3 x 0.15s), took {elapsed:.3f}s"
    assert [r.tool_call_id for r in batch.messages] == ["c1", "c2", "c3"]


def test_prepare_runs_serially_before_handlers():
    seen: list[str] = []

    def record(args: dict) -> str:
        return tool_result()

    registry.register(name="t_prep", toolset="test", schema={"type": "object"}, handler=record)

    def _before(name: str, args: dict, token: CancelToken) -> dict:
        seen.append(f"prep:{name}")
        return args

    batch = _run(
        dispatch_tool_batch(
            [ToolCallPayload(id=f"c{i}", name="t_prep", arguments="{}") for i in range(3)],
            max_result_length=sys.maxsize,
            token=CancelToken(),
            emit=_EventRecorder(),
            config=_make_config(before_tool_call=_before),
        )
    )
    assert seen == ["prep:t_prep", "prep:t_prep", "prep:t_prep"]
    assert len(batch.messages) == 3
