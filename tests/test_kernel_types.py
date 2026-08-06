"""Tests for agent/core/kernel_types.py — kernel type contracts."""

from __future__ import annotations

import asyncio

import pytest

from agent.core.kernel_types import (
    AgentContext,
    AgentEnd,
    AgentEvent,
    AgentLoopConfig,
    AgentStart,
    CancelToken,
    ExecutedToolBatch,
    MessageEnd,
    MessageStart,
    MessageUpdate,
    ToolExecutionEnd,
    ToolExecutionStart,
    ToolExecutionUpdate,
    ToolResult,
    TurnEnd,
    TurnStart,
    TurnUpdate,
)


class TestCancelToken:
    def test_starts_uncancelled(self):
        token = CancelToken()
        assert token.cancelled is False

    def test_cancel_sets_flag(self):
        token = CancelToken()
        token.cancel()
        assert token.cancelled is True

    def test_wait_returns_after_cancel(self):
        async def _scenario():
            token = CancelToken()

            async def _canceller():
                await asyncio.sleep(0.01)
                token.cancel()

            task = asyncio.create_task(token.wait())
            await asyncio.create_task(_canceller())
            await task  # must return once cancelled

        asyncio.run(_scenario())

    def test_check_raises_cancelled_error_when_cancelled(self):
        token = CancelToken()
        token.cancel()
        with pytest.raises(asyncio.CancelledError):
            token.check()

    def test_check_passes_when_not_cancelled(self):
        CancelToken().check()  # must not raise


class TestAgentLoopConfig:
    def test_defaults(self):
        cfg = AgentLoopConfig(model="gpt-4o")
        assert cfg.model == "gpt-4o"
        assert cfg.temperature == 0.7
        assert cfg.max_tokens is None
        assert cfg.system_prompt == ""
        assert cfg.tool_defs == []
        assert cfg.call_llm is None
        assert cfg.transform_context is None
        assert cfg.before_tool_call is None
        assert cfg.after_tool_call is None
        assert cfg.prepare_next_turn is None
        assert cfg.should_stop_after_turn is None
        assert cfg.get_steering_messages is None
        assert cfg.get_follow_up_messages is None
        assert cfg.bridge_dispatch is None
        assert cfg.on_approval_blocked is None

    def test_turn_update_defaults(self):
        u = TurnUpdate()
        assert u.model is None
        assert u.temperature is None
        assert u.max_tokens is None


class TestToolResultAndBatch:
    def test_tool_result_defaults(self):
        r = ToolResult(tool_call_id="c1", tool_name="ls", result="[]")
        assert r.is_error is False
        assert r.terminate is False

    def test_executed_batch_defaults(self):
        b = ExecutedToolBatch()
        assert b.messages == []
        assert b.terminate is False


class TestAgentEvents:
    def test_discriminator_types(self):
        assert AgentStart().type == "agent_start"
        assert AgentEnd(messages=[]).type == "agent_end"
        assert TurnStart().type == "turn_start"
        assert TurnEnd(message={}, tool_results=[]).type == "turn_end"
        assert MessageStart(message={}).type == "message_start"
        assert MessageUpdate(message={}, delta="hi").type == "message_update"
        assert MessageUpdate(message={}, delta="", reasoning_delta="think").reasoning_delta == "think"
        assert MessageEnd(message={}).type == "message_end"
        assert ToolExecutionStart(tool_call_id="c1", tool_name="ls", args={}).type == "tool_execution_start"
        assert (
            ToolExecutionUpdate(tool_call_id="c1", tool_name="ls", partial_result="x").type == "tool_execution_update"
        )
        assert ToolExecutionEnd(tool_call_id="c1", tool_name="ls", result="[]").type == "tool_execution_end"
        assert ToolExecutionEnd(tool_call_id="c1", tool_name="ls", result="err", is_error=True).is_error is True
        assert ToolExecutionEnd(tool_call_id="c1", tool_name="ls", result="err", is_error=True).denied is False

    def test_events_are_frozen(self):
        with pytest.raises(Exception, match="cannot assign to field"):
            MessageStart(message={}).message = {"role": "user"}  # type: ignore[misc]

    def test_agent_event_union_members(self):
        events: list[AgentEvent] = [
            AgentStart(),
            AgentEnd(messages=[]),
            TurnStart(),
            TurnEnd(message={}, tool_results=[]),
            MessageStart(message={}),
            MessageUpdate(message={}, delta="d"),
            MessageEnd(message={}),
            ToolExecutionStart(tool_call_id="c1", tool_name="t", args={}),
            ToolExecutionUpdate(tool_call_id="c1", tool_name="t", partial_result="p"),
            ToolExecutionEnd(tool_call_id="c1", tool_name="t", result="r"),
        ]
        assert len(events) == 10

    def test_agent_context_defaults(self):
        ctx = AgentContext()
        assert ctx.messages == []
        assert ctx.api_calls == 0
