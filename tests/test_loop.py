"""Tests for agent/core/loop.py — the zero-policy async loop."""

from __future__ import annotations

import asyncio
import json

import pytest

from agent.core.kernel_types import (
    AgentContext,
    AgentEnd,
    AgentEvent,
    AgentLoopConfig,
    CancelToken,
    MessageStart,
    MessageUpdate,
    TurnEnd,
    TurnStart,
)
from agent.core.llm_providers.base import LLMResponse, ToolCallPayload
from agent.core.loop import run_agent_loop, run_agent_loop_continue
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
    """Fake call_llm: returns scripted LLMResponses and records messages."""

    def __init__(self, *responses: LLMResponse) -> None:
        self.responses = list(responses)
        self.calls: list[list[dict]] = []
        self.emitted_updates: list[MessageUpdate] = []

    async def __call__(self, full_messages, *, emit, message, token):
        self.calls.append(list(full_messages))
        resp = self.responses.pop(0)
        if resp.content:
            message["content"] = resp.content
        if resp.reasoning:
            message["reasoning_content"] = resp.reasoning
        return resp


class _Recorder:
    def __init__(self) -> None:
        self.events: list[AgentEvent] = []

    async def __call__(self, event: AgentEvent) -> None:
        self.events.append(event)


def _run(coro):
    return asyncio.run(coro)


def _cfg(**kw) -> AgentLoopConfig:
    base: dict = {
        "model": "test-model",
        "call_llm": _ScriptedLLM(LLMResponse(content="hi")),
    }
    base.update(kw)
    return AgentLoopConfig(**base)


def _tool_response(tool_name: str, args: dict, call_id: str = "c1") -> LLMResponse:
    return LLMResponse(
        content="",
        tool_calls=[ToolCallPayload(id=call_id, name=tool_name, arguments=json.dumps(args))],
    )


def test_plain_text_event_sequence_and_return():
    llm = _ScriptedLLM(LLMResponse(content="hello back"))
    rec = _Recorder()
    ctx = AgentContext()
    result = _run(run_agent_loop([{"role": "user", "content": "hi"}], ctx, _cfg(call_llm=llm), rec, CancelToken()))

    assert result == [
        {"role": "user", "content": "hi"},
        {"role": "assistant", "content": "hello back"},
    ]
    types = [e.type for e in rec.events]
    assert types[0] == "agent_start"
    assert types[-1] == "agent_end"
    assert types == [
        "agent_start",
        "message_start",
        "message_end",  # user prompt
        "turn_start",
        "message_start",
        "message_end",  # assistant reply
        "turn_end",
        "agent_end",
    ]
    assert ctx.api_calls == 1
    # AgentEnd carries the full new-messages list
    end = rec.events[-1]
    assert isinstance(end, AgentEnd)
    assert end.messages[-1]["content"] == "hello back"


def test_tool_call_then_text_orders_transcript():
    def echo(args: dict) -> str:
        return tool_result(data={"v": args.get("v")})
    registry.register(name="echo", toolset="test", schema={"type": "object"}, handler=echo)
    llm = _ScriptedLLM(
        _tool_response("echo", {"v": "x"}),
        LLMResponse(content="done"),
    )
    rec = _Recorder()
    ctx = AgentContext()
    result = _run(run_agent_loop([{"role": "user", "content": "go"}], ctx, _cfg(call_llm=llm), rec, CancelToken()))

    roles = [m["role"] for m in result]
    assert roles == ["user", "assistant", "tool", "assistant"]
    assert result[2]["tool_call_id"] == "c1"
    assert json.loads(result[2]["content"])["data"]["v"] == "x"
    # assistant + tool messages appended to context too
    assert [m["role"] for m in ctx.messages] == ["user", "assistant", "tool", "assistant"]
    # turn boundaries: 2 TurnStart / 2 TurnEnd
    assert sum(1 for e in rec.events if isinstance(e, TurnStart)) == 2
    turn_ends = [e for e in rec.events if isinstance(e, TurnEnd)]
    assert len(turn_ends) == 2
    assert len(turn_ends[0].tool_results) == 1


def test_second_llm_call_includes_assistant_tool_calls_message():
    """Regression: assistant tool_calls message must enter context.messages,
    otherwise tool results reach the provider orphaned (DeepSeek 400)."""

    def echo(args: dict) -> str:
        return tool_result(data={"ok": True})

    registry.register(name="echo", toolset="test", schema={"type": "object"}, handler=echo)
    llm = _ScriptedLLM(
        _tool_response("echo", {}, call_id="c1"),
        LLMResponse(content="done"),
    )
    rec = _Recorder()
    _run(run_agent_loop([{"role": "user", "content": "go"}], AgentContext(), _cfg(call_llm=llm), rec, CancelToken()))

    assert len(llm.calls) == 2
    second_call_roles = [m["role"] for m in llm.calls[1]]
    assert second_call_roles == ["user", "assistant", "tool"]
    assistant_msg = llm.calls[1][1]
    assert assistant_msg["tool_calls"][0]["id"] == "c1"
    assert llm.calls[1][2]["tool_call_id"] == "c1"


def test_steering_message_injected_next_turn():
    def _steer(token: CancelToken) -> list[dict]:
        # inject one steering message only on the second poll
        _steer.polls += 1
        if _steer.polls == 2:
            return [{"role": "user", "content": "interrupt"}]
        return []

    _steer.polls = 0  # type: ignore[attr-defined]

    llm = _ScriptedLLM(LLMResponse(content="first"), LLMResponse(content="second"))
    rec = _Recorder()
    result = _run(
        run_agent_loop(
            [{"role": "user", "content": "go"}],
            AgentContext(),
            _cfg(call_llm=llm, get_steering_messages=_steer),
            rec,
            CancelToken(),
        )
    )
    assert [m["content"] for m in result] == ["go", "first", "interrupt", "second"]
    # steering user message emitted with MessageStart/MessageEnd pair
    msgs = [e for e in rec.events if isinstance(e, MessageStart)]
    assert [m.message.get("content") for m in msgs] == ["go", "first", "interrupt", "second"]


def test_follow_up_opens_outer_loop():
    def _followup(token: CancelToken) -> list[dict]:
        if _followup.called:  # type: ignore[attr-defined]
            return []
        _followup.called = True  # type: ignore[attr-defined]
        return [{"role": "user", "content": "follow up"}]

    _followup.called = False  # type: ignore[attr-defined]

    llm = _ScriptedLLM(LLMResponse(content="a"), LLMResponse(content="b"))
    result = _run(
        run_agent_loop(
            [{"role": "user", "content": "go"}],
            AgentContext(),
            _cfg(call_llm=llm, get_follow_up_messages=_followup),
            _Recorder(),
            CancelToken(),
        )
    )
    assert [m["content"] for m in result] == ["go", "a", "follow up", "b"]


def test_should_stop_after_turn_ends_with_agent_end():
    llm = _ScriptedLLM(LLMResponse(content="only"))

    async def _stop(ctx: dict, token: CancelToken) -> bool:
        return True

    rec = _Recorder()
    _run(
        run_agent_loop(
            [{"role": "user", "content": "go"}],
            AgentContext(),
            _cfg(call_llm=llm, should_stop_after_turn=_stop),
            rec,
            CancelToken(),
        )
    )
    assert rec.events[-1].type == "agent_end"
    assert len(llm.calls) == 1


def test_llm_error_encodes_in_message_and_ends():
    llm = _ScriptedLLM(LLMResponse(error="API down", stop_reason="error"))
    rec = _Recorder()
    result = _run(
        run_agent_loop([{"role": "user", "content": "go"}], AgentContext(), _cfg(call_llm=llm), rec, CancelToken())
    )

    assert result[-1]["is_error"] is True
    assert result[-1]["errorMessage"] == "API down"
    assert rec.events[-1].type == "agent_end"
    # no tools executed, no TurnEnd tool results
    turn_ends = [e for e in rec.events if isinstance(e, TurnEnd)]
    assert turn_ends[-1].tool_results == []


def test_length_stop_reason_fails_truncated_tool_batch():
    ran: list[str] = []

    def spy(args: dict) -> str:
        ran.append("ran")
        return tool_result()

    registry.register(name="spy", toolset="test", schema={"type": "object"}, handler=spy)
    llm = _ScriptedLLM(
        LLMResponse(
            content="", tool_calls=[ToolCallPayload(id="c1", name="spy", arguments="{}")], stop_reason="length"
        ),
        LLMResponse(content="please re-issue"),
    )
    rec = _Recorder()
    result = _run(
        run_agent_loop([{"role": "user", "content": "go"}], AgentContext(), _cfg(call_llm=llm), rec, CancelToken())
    )

    assert ran == [], "truncated batch must never execute handlers"
    tool_msgs = [m for m in result if m.get("role") == "tool"]
    assert len(tool_msgs) == 1
    assert "参数可能被截断，请重新完整发出" in tool_msgs[0]["content"]
    assert result[-1]["content"] == "please re-issue"


def test_prepare_next_turn_applies_model_override():
    seen_models: list[str] = []

    def _echo(args: dict) -> str:
        return tool_result(data={"v": args.get("v")})

    registry.register(name="echo", toolset="test", schema={"type": "object"}, handler=_echo)

    class _LLM:
        def __init__(self):
            self.responses = [
                _tool_response("echo", {"v": 1}),
                LLMResponse(content="b"),
            ]

        async def __call__(self, full_messages, *, emit, message, token):
            seen_models.append(full_messages[0]["content"] if full_messages else "?")
            resp = self.responses.pop(0)
            message["content"] = resp.content
            return resp

    async def _prepare(ctx: dict, token: CancelToken):
        from agent.core.kernel_types import TurnUpdate

        return TurnUpdate(model="next-model")

    _run(
        run_agent_loop(
            [{"role": "user", "content": "go"}],
            AgentContext(),
            _cfg(call_llm=_LLM(), prepare_next_turn=_prepare),
            _Recorder(),
            CancelToken(),
        )
    )
    # Turn 1 ends with a tool call, so the loop runs turn 2; the update
    # returned by prepare_next_turn is applied (via dataclasses.replace)
    # between the two calls — so call_llm must be invoked exactly twice.
    assert len(seen_models) == 2


def test_cancelled_token_raises_cancelled_error():
    llm = _ScriptedLLM(LLMResponse(content="a"), LLMResponse(content="b"))
    token = CancelToken()

    async def _steer(t: CancelToken) -> list[dict]:
        token.cancel()
        return []

    with pytest.raises(asyncio.CancelledError):
        _run(
            run_agent_loop(
                [{"role": "user", "content": "go"}],
                AgentContext(),
                _cfg(call_llm=llm, get_steering_messages=_steer),
                _Recorder(),
                token,
            )
        )


def test_continue_requires_non_assistant_tail():
    ctx = AgentContext(messages=[{"role": "assistant", "content": "last"}])
    with pytest.raises(ValueError, match="Cannot continue from message role: assistant"):
        _run(run_agent_loop_continue(ctx, _cfg(), _Recorder(), CancelToken()))

    ctx2 = AgentContext(messages=[{"role": "user", "content": "ok"}])
    llm = _ScriptedLLM(LLMResponse(content="continued"))
    result = _run(run_agent_loop_continue(ctx2, _cfg(call_llm=llm), _Recorder(), CancelToken()))
    assert result == [{"role": "assistant", "content": "continued"}]


def test_streaming_message_update_events():
    """MessageUpdate fires while the LLM streams (via call_llm's emit)."""

    async def _streaming_llm(full_messages, *, emit, message, token):
        for chunk in ("你", "好"):
            message["content"] = message.get("content", "") + chunk
            await emit(MessageUpdate(message=dict(message), delta=chunk))
        return LLMResponse(content="你好")

    rec = _Recorder()
    result = _run(
        run_agent_loop(
            [{"role": "user", "content": "hi"}],
            AgentContext(),
            _cfg(call_llm=_streaming_llm),
            rec,
            CancelToken(),
        )
    )
    updates = [e for e in rec.events if isinstance(e, MessageUpdate)]
    assert [u.delta for u in updates] == ["你", "好"]
    assert result[-1]["content"] == "你好"
