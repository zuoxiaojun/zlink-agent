"""Tests for agent/core/agent.py — the stateful Agent wrapper."""

from __future__ import annotations

import asyncio

import pytest

from agent.core.agent import Agent
from agent.core.kernel_types import (
    AgentEnd,
    AgentLoopConfig,
    CancelToken,
    MessageEnd,
    MessageStart,
)
from agent.core.llm_providers.base import LLMResponse, ToolCallPayload
from agent.tools.registry import registry, tool_result


@pytest.fixture(autouse=True)
def clean_tool_registry():
    saved_before = set(registry.get_all_tool_names())
    yield
    for name in set(registry.get_all_tool_names()) - saved_before:
        try:
            registry.deregister(name)
        except Exception:
            pass


class _ScriptedLLM:
    def __init__(self, *responses: LLMResponse) -> None:
        self.responses = list(responses)

    async def __call__(self, full_messages, *, emit, message, token):
        resp = self.responses.pop(0)
        message["content"] = resp.content
        return resp


def _cfg(*responses: LLMResponse, **kw) -> AgentLoopConfig:
    base: dict = {"model": "test-model", "call_llm": _ScriptedLLM(*responses)}
    base.update(kw)
    return AgentLoopConfig(**base)


def _run(coro):
    return asyncio.run(coro)


def test_subscribe_and_unsubscribe():
    agent = Agent()
    seen: list[str] = []
    listener = lambda e: seen.append(e.type)  # noqa: E731
    unsub = agent.subscribe(listener)
    agent._token = CancelToken()
    _run(agent._emit(MessageStart(message={"role": "user"})))
    assert seen == ["message_start"]
    unsub()
    _run(agent._emit(MessageEnd(message={"role": "user"})))
    assert seen == ["message_start"]


def test_steering_one_at_a_time():
    agent = Agent()
    agent.steer({"role": "user", "content": "first"})
    agent.steer({"role": "user", "content": "second"})
    assert agent.next_steering_message() == [{"role": "user", "content": "first"}]
    assert agent.next_steering_message() == [{"role": "user", "content": "second"}]
    assert agent.next_steering_message() == []


def test_clear_steering_queue():
    agent = Agent()
    agent.steer({"role": "user", "content": "x"})
    agent.clear_steering_queue()
    assert agent.next_steering_message() == []


def test_follow_up_drain_all():
    agent = Agent()
    agent.follow_up({"role": "user", "content": "a"})
    agent.follow_up({"role": "user", "content": "b"})
    assert agent.next_follow_up_messages() == [
        {"role": "user", "content": "a"},
        {"role": "user", "content": "b"},
    ]
    assert agent.next_follow_up_messages() == []


def test_run_async_basic_lifecycle():
    agent = Agent()
    result = _run(
        agent.run_async(
            [{"role": "user", "content": "hi"}],
            _cfg(LLMResponse(content="hello")),
        )
    )
    assert [m["content"] for m in result] == ["hi", "hello"]
    assert agent.state.running is False
    assert agent.state.messages[-1]["content"] == "hello"
    assert agent.state.pendingToolCalls == 0


def test_cancel_and_wait_idle():
    import time

    def sleepy(args: dict) -> str:
        time.sleep(0.5)
        return tool_result()

    registry.register(name="sleeper", toolset="test", schema={"type": "object"}, handler=sleepy)
    agent = Agent()
    token = CancelToken()

    async def _scenario():
        task = asyncio.create_task(
            agent.run_async(
                [{"role": "user", "content": "go"}],
                _cfg(LLMResponse(content="", tool_calls=[ToolCallPayload(id="c1", name="sleeper", arguments="{}")])),
                token,
            )
        )
        await asyncio.sleep(0.05)
        token.cancel()  # cancel the in-use token mid-run
        await agent.wait_idle()
        assert agent.state.running is False
        with pytest.raises(asyncio.CancelledError):
            await task

    _run(_scenario())


def test_pending_tool_calls_tracked_through_events():
    def echo(args: dict) -> str:
        return tool_result(data={"v": args.get("v")})

    registry.register(name="echo", toolset="test", schema={"type": "object"}, handler=echo)
    agent = Agent()
    _run(
        agent.run_async(
            [{"role": "user", "content": "go"}],
            _cfg(
                LLMResponse(content="", tool_calls=[ToolCallPayload(id="c1", name="echo", arguments='{"v": 1}')]),
                LLMResponse(content="done"),
            ),
        )
    )
    assert agent.state.pendingToolCalls == 0
    assert agent.state.running is False


def test_listener_receives_agent_end_with_messages():
    agent = Agent()
    ends: list[AgentEnd] = []
    agent.subscribe(lambda e: ends.append(e) if isinstance(e, AgentEnd) else None)
    _run(agent.run_async([{"role": "user", "content": "hi"}], _cfg(LLMResponse(content="yo"))))
    assert len(ends) == 1
    assert ends[0].messages[-1]["content"] == "yo"


def test_run_async_accepts_fresh_token_after_cancel():
    """M-6: an explicitly passed fresh token must be adopted even when the
    instance's internal token was previously cancelled."""
    agent = Agent()
    agent.cancel()  # internal token now cancelled
    fresh = CancelToken()
    result = _run(agent.run_async([{"role": "user", "content": "hi"}], _cfg(LLMResponse(content="ok")), fresh))
    assert [m["content"] for m in result] == ["hi", "ok"]


def test_run_async_resets_token_after_cancel_without_argument():
    """M-6: with no token passed, a previously cancelled internal token is
    replaced so the Agent instance can be reused."""
    agent = Agent()
    agent.cancel()
    result = _run(agent.run_async([{"role": "user", "content": "hi"}], _cfg(LLMResponse(content="ok"))))
    assert [m["content"] for m in result] == ["hi", "ok"]


def test_subscribe_is_idempotent():
    """M-6: subscribing the same listener twice must register it once."""
    agent = Agent()
    seen: list[str] = []
    listener = lambda e: seen.append(e.type)  # noqa: E731
    unsub = agent.subscribe(listener)
    agent.subscribe(listener)  # duplicate — must be a no-op
    assert agent._listeners.count(listener) == 1
    _run(agent._emit(MessageStart(message={"role": "user"})))
    assert seen == ["message_start"]
    unsub()
    _run(agent._emit(MessageEnd(message={"role": "user"})))
    assert seen == ["message_start"]
