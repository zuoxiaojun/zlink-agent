"""Minimal async agent loop — zero policy, only event-flow orchestration.

Pi-style kernel redesign (spec 2026-08-06-pi-style-kernel-design).
Mirrors Pi's ``agent-loop.ts``: a two-level loop (inner = tool_calls /
steering messages, outer = follow-up messages); every "should we
continue / compact / prepare next turn" decision is a hook on
:class:`AgentLoopConfig`.  This module contains NO business policy —
compaction, budget, security and steering are all hooks.
"""

from __future__ import annotations

import asyncio
import dataclasses
import logging
from collections.abc import Awaitable, Callable

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
    ToolExecutionEnd,
    ToolExecutionStart,
    ToolResult,
    TurnEnd,
    TurnStart,
)
from agent.core.tool_dispatcher import dispatch_tool_batch
from agent.tools.registry import tool_error

logger = logging.getLogger(__name__)


async def _await_maybe(value):
    """Await *value* if it is a coroutine (hooks may be sync or async)."""
    if asyncio.iscoroutine(value):
        return await value
    return value


async def run_agent_loop(
    prompts: list[dict],
    context: AgentContext,
    config: AgentLoopConfig,
    emit: Callable[[AgentEvent], Awaitable[None]],
    token: CancelToken,
) -> list[dict]:
    """Start a run with new prompts.  Returns the new messages
    (prompts + everything the loop appended)."""
    new_messages = list(prompts)
    context.messages += prompts
    await emit(AgentStart())
    for p in prompts:
        await emit(MessageStart(p))
        await emit(MessageEnd(p))
    await _run_loop(context, new_messages, config, emit, token)
    return new_messages


async def run_agent_loop_continue(
    context: AgentContext,
    config: AgentLoopConfig,
    emit: Callable[[AgentEvent], Awaitable[None]],
    token: CancelToken,
) -> list[dict]:
    """Continue from the current context.  The last message must not be
    an assistant message (a fresh LLM call needs a user/tool tail)."""
    if not context.messages or context.messages[-1].get("role") == "assistant":
        raise ValueError("Cannot continue from message role: assistant")
    new_messages: list[dict] = []
    await emit(AgentStart())
    await _run_loop(context, new_messages, config, emit, token)
    return new_messages


async def _run_loop(
    context: AgentContext,
    new_messages: list[dict],
    config: AgentLoopConfig,
    emit: Callable[[AgentEvent], Awaitable[None]],
    token: CancelToken,
) -> None:
    """Two-level loop: inner = tool_calls/steering, outer = follow-up."""

    async def _no_messages(_token: CancelToken) -> list[dict]:
        return []

    get_steering = config.get_steering_messages or _no_messages
    get_followup = config.get_follow_up_messages or _no_messages

    pending = await _await_maybe(get_steering(token))
    while True:  # outer loop — follow-up messages
        has_more_tool_calls = True
        while has_more_tool_calls or pending:  # inner loop
            token.check()
            await emit(TurnStart())
            if pending:  # steering injection
                for msg in pending:
                    await emit(MessageStart(msg))
                    await emit(MessageEnd(msg))
                    context.messages.append(msg)
                    new_messages.append(msg)
                pending = []
            # 1) context transform (compaction hook)
            if config.transform_context is not None:
                context.messages = await _await_maybe(config.transform_context(context.messages, token))
            # 2) LLM call (never raises: failures are encoded into the message)
            message, stop_reason = await _stream_assistant_response(context, config, emit, token)
            context.messages.append(message)
            new_messages.append(message)
            if message.get("is_error") or stop_reason in ("error", "aborted"):
                await emit(TurnEnd(message, []))
                await emit(AgentEnd(new_messages))
                return
            # 3) tool batch execution
            tool_calls = message.get("tool_calls") or []
            tool_results: list[ToolResult] = []
            has_more_tool_calls = False
            if tool_calls:
                if stop_reason == "length":
                    executed = await _fail_truncated_batch(tool_calls, emit)
                else:
                    executed = await _execute_tool_batch(context, message, config, emit, token)
                tool_results = executed.messages
                has_more_tool_calls = not executed.terminate
                for r in tool_results:
                    tm = _to_tool_message(r)
                    context.messages.append(tm)
                    new_messages.append(tm)
            turn_ctx = {
                "message": message,
                "tool_results": tool_results,
                "messages": new_messages,
                "api_calls": context.api_calls,
            }
            await emit(TurnEnd(message, tool_results))
            # 4) next-turn overrides (model/temperature/max_tokens)
            if config.prepare_next_turn is not None:
                update = await _await_maybe(config.prepare_next_turn(turn_ctx, token))
                if update is not None:
                    config = _apply_update(config, update)
            # 5) stop decision (IterationBudget consumption point)
            if config.should_stop_after_turn is not None and await _await_maybe(
                config.should_stop_after_turn(turn_ctx, token)
            ):
                await emit(AgentEnd(new_messages))
                return
            # 6) steering re-poll (one-at-a-time drain semantics live in Agent)
            pending = await _await_maybe(get_steering(token))
        # outer: follow-up messages
        follow_ups = await _await_maybe(get_followup(token))
        if follow_ups:
            pending = follow_ups
            continue
        break
    await emit(AgentEnd(new_messages))


async def _stream_assistant_response(
    context: AgentContext,
    config: AgentLoopConfig,
    emit: Callable[[AgentEvent], Awaitable[None]],
    token: CancelToken,
) -> tuple[dict, str | None]:
    """Make one LLM call; emit MessageStart/MessageUpdate/MessageEnd.

    Returns ``(assistant_message_dict, stop_reason)``.  ``call_llm`` is
    responsible for streaming MessageUpdate events (via *emit*); content
    and reasoning are copied from the response here (idempotent with the
    streaming accumulation).
    """
    token.check()
    if config.call_llm is None:
        raise RuntimeError("AgentLoopConfig.call_llm is required")
    full_messages: list[dict] = []
    if config.system_prompt:
        full_messages.append({"role": "system", "content": config.system_prompt})
    full_messages.extend(context.messages)
    message: dict = {"role": "assistant", "content": ""}
    await emit(MessageStart(message))
    response = await config.call_llm(full_messages, emit=emit, message=message, token=token)
    if response.content:
        message["content"] = response.content
    if response.reasoning:
        message["reasoning_content"] = response.reasoning
    if response.tool_calls:
        message["tool_calls"] = [
            {
                "id": tc.id,
                "type": "function",
                "function": {"name": tc.name, "arguments": tc.arguments},
            }
            for tc in response.tool_calls
        ]
    if response.failed:
        message["is_error"] = True
        message["errorMessage"] = response.error
    context.api_calls += 1
    await emit(MessageEnd(message))
    return message, response.stop_reason


async def _execute_tool_batch(
    context: AgentContext,
    message: dict,
    config: AgentLoopConfig,
    emit: Callable[[AgentEvent], Awaitable[None]],
    token: CancelToken,
) -> ExecutedToolBatch:
    """Translate the assistant message's tool_calls into payloads and
    hand them to the (async) dispatcher."""
    from agent.core.llm_providers.base import ToolCallPayload

    calls = [
        ToolCallPayload(
            id=tc["id"],
            name=tc["function"]["name"],
            arguments=tc["function"]["arguments"],
        )
        for tc in message.get("tool_calls", [])
    ]
    return await dispatch_tool_batch(
        calls,
        max_result_length=config.max_tool_result_length,
        token=token,
        emit=emit,
        config=config,
    )


async def _fail_truncated_batch(
    tool_calls: list[dict],
    emit: Callable[[AgentEvent], Awaitable[None]],
) -> ExecutedToolBatch:
    """``stop_reason == "length"`` guard: no tool call executes; every one
    returns a truncation error so the model re-issues it (Pi's
    failToolCallsFromTruncatedMessage)."""
    results: list[ToolResult] = []
    for tc in tool_calls:
        name = tc["function"]["name"]
        cid = tc["id"]
        err = tool_error("参数可能被截断，请重新完整发出")
        await emit(ToolExecutionStart(tool_call_id=cid, tool_name=name, args={}))
        await emit(ToolExecutionEnd(tool_call_id=cid, tool_name=name, result=err, is_error=True))
        results.append(ToolResult(tool_call_id=cid, tool_name=name, result=err, is_error=True))
    return ExecutedToolBatch(messages=results, terminate=False)


def _to_tool_message(r: ToolResult) -> dict:
    return {"role": "tool", "tool_call_id": r.tool_call_id, "content": r.result}


def _apply_update(config: AgentLoopConfig, update) -> AgentLoopConfig:
    """Return a copy of *config* with non-None TurnUpdate fields applied."""
    kw = {
        "model": update.model if update.model is not None else config.model,
        "temperature": update.temperature if update.temperature is not None else config.temperature,
        "max_tokens": update.max_tokens if update.max_tokens is not None else config.max_tokens,
    }
    return dataclasses.replace(config, **kw)


__all__ = ["run_agent_loop", "run_agent_loop_continue"]
