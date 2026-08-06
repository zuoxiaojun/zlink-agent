"""Tool dispatch — async batch execution.

Pi-style kernel redesign (spec 2026-08-06-pi-style-kernel-design).
:func:`dispatch_tool_batch` runs every tool through ``registry.dispatch``
in a worker thread so the security before/after hook chain and the
``__block__`` protocol stay intact (Layer 2), then results are truncated
per entry and returned in original order.  Batches run in parallel,
degrading to strict sequential execution when a batch contains an
``execution_mode == "sequential"`` tool.
"""

from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from agent.core.kernel_types import (
    AgentEvent,
    AgentLoopConfig,
    CancelToken,
    ExecutedToolBatch,
    ToolExecutionEnd,
    ToolExecutionStart,
    ToolResult,
)
from agent.core.llm_providers.base import ToolCallPayload
from agent.tools.registry import registry, tool_error
from agent.tools.tool_search import BRIDGE_TOOL_NAMES

logger = logging.getLogger(__name__)

_TRUNCATION_SUFFIX = "\n\n..."


def _truncate(content: Any, limit: int) -> str:
    if isinstance(content, str) and len(content) > limit:
        return content[:limit] + _TRUNCATION_SUFFIX
    return content if isinstance(content, str) else str(content)


def _is_error_result(result: str) -> bool:
    """True when *result* is a ``tool_error`` payload (``success: false``).

    ``registry.dispatch`` swallows handler exceptions and returns an
    error JSON string instead of raising, so the batch detects failure
    from the payload rather than from an exception.
    """
    try:
        payload = json.loads(result)
    except (json.JSONDecodeError, TypeError):
        return False
    return isinstance(payload, dict) and payload.get("success") is False


async def _await_maybe(value):
    """Await *value* if it is a coroutine (hooks may be sync or async)."""
    if asyncio.iscoroutine(value):
        return await value
    return value


def _entry_mode(name: str) -> str:
    """Return a tool's execution_mode, defaulting to "parallel"."""
    entry = registry.get_entry(name)
    if entry is None:
        return "parallel"  # unknown tools produce an error result anyway
    return getattr(entry, "execution_mode", "parallel")


@dataclass
class _Prepared:
    tc: ToolCallPayload
    args: dict
    index: int
    immediate: str | None = None


@dataclass
class _HandlerResult:
    result: str
    denied: bool = False


async def dispatch_tool_batch(
    calls: list[ToolCallPayload],
    *,
    max_result_length: int,
    token: CancelToken,
    emit: Callable[[AgentEvent], Awaitable[None]],
    config: AgentLoopConfig,
) -> ExecutedToolBatch:
    """Execute a batch of tool calls and return results in original order.

    P2: parallel with sequential degradation — a batch containing any
    ``execution_mode == "sequential"`` tool falls back to strict serial
    execution (Pi's hasSequentialToolCall → executeToolCallsSequential).
    """
    sequential = any(_entry_mode(tc.name) == "sequential" for tc in calls)
    if sequential:
        return await _dispatch_sequential(
            calls,
            max_result_length=max_result_length,
            token=token,
            emit=emit,
            config=config,
        )
    return await _dispatch_parallel(
        calls,
        max_result_length=max_result_length,
        token=token,
        emit=emit,
        config=config,
    )


async def _dispatch_parallel(
    calls: list[ToolCallPayload],
    *,
    max_result_length: int,
    token: CancelToken,
    emit: Callable[[AgentEvent], Awaitable[None]],
    config: AgentLoopConfig,
) -> ExecutedToolBatch:
    """Prepare serially, execute handlers concurrently, emit in order."""
    prepared: list[_Prepared] = []
    for i, tc in enumerate(calls):  # prepare serial
        token.check()
        args, immediate = await _prepare(tc, config, token, emit)
        prepared.append(_Prepared(tc=tc, args=args, index=i, immediate=immediate))

    runnable = [p for p in prepared if p.immediate is None]
    # ToolExecutionStart in original order — WS tool_call cards are ordered
    for p in runnable:
        await emit(ToolExecutionStart(tool_call_id=p.tc.id, tool_name=p.tc.name, args=p.args))

    async def _run(prep: _Prepared) -> tuple[int, str, bool, bool]:
        res = await _run_handler(prep.tc.name, prep.args, config, token)
        finalized = await _finalize(prep.tc.name, prep.args, res.result, config, token)
        return prep.index, _truncate(finalized, max_result_length), _is_error_result(finalized), res.denied

    if runnable:
        completed = await asyncio.gather(*(_run(p) for p in runnable))
    else:
        completed = []
    by_index = {idx: (truncated, is_error, denied) for idx, truncated, is_error, denied in completed}

    # Restore original order: immediate errors + executed results
    results: list[ToolResult] = []
    for p in prepared:
        if p.immediate is not None:
            results.append(
                ToolResult(
                    tool_call_id=p.tc.id,
                    tool_name=p.tc.name,
                    result=_truncate(p.immediate, max_result_length),
                    is_error=True,
                )
            )
            continue
        truncated, is_error, denied = by_index[p.index]
        await emit(
            ToolExecutionEnd(
                tool_call_id=p.tc.id,
                tool_name=p.tc.name,
                result=truncated,
                is_error=is_error,
                denied=denied,
            )
        )
        results.append(
            ToolResult(
                tool_call_id=p.tc.id,
                tool_name=p.tc.name,
                result=truncated,
                is_error=is_error,
            )
        )
    return ExecutedToolBatch(messages=results, terminate=False)


async def _dispatch_sequential(
    calls: list[ToolCallPayload],
    *,
    max_result_length: int,
    token: CancelToken,
    emit: Callable[[AgentEvent], Awaitable[None]],
    config: AgentLoopConfig,
) -> ExecutedToolBatch:
    """Strict serial: prepare → execute → finalize, one call at a time."""
    results: list[ToolResult] = []
    for tc in calls:
        token.check()
        args, immediate = await _prepare(tc, config, token, emit)
        if immediate is not None:
            results.append(
                ToolResult(
                    tool_call_id=tc.id,
                    tool_name=tc.name,
                    result=_truncate(immediate, max_result_length),
                    is_error=True,
                )
            )
            continue
        await emit(ToolExecutionStart(tool_call_id=tc.id, tool_name=tc.name, args=args))
        raw = await _run_handler(tc.name, args, config, token)
        finalized = await _finalize(tc.name, args, raw.result, config, token)
        truncated = _truncate(finalized, max_result_length)
        is_error = _is_error_result(finalized)
        await emit(
            ToolExecutionEnd(
                tool_call_id=tc.id,
                tool_name=tc.name,
                result=truncated,
                is_error=is_error,
                denied=raw.denied,
            )
        )
        results.append(
            ToolResult(
                tool_call_id=tc.id,
                tool_name=tc.name,
                result=truncated,
                is_error=is_error,
            )
        )
    return ExecutedToolBatch(messages=results, terminate=False)


async def _prepare(
    tc: ToolCallPayload,
    config: AgentLoopConfig,
    token: CancelToken,
    emit: Callable[[AgentEvent], Awaitable[None]],
) -> tuple[dict, str | None]:
    """Parse JSON args and run the before_tool_call hook.

    Returns ``(args, None)`` on success or ``(args, error_result)`` when
    the arguments are invalid or a hook blocked the call.
    """
    try:
        args = json.loads(tc.arguments) if tc.arguments else {}
    except json.JSONDecodeError:
        return {}, tool_error("Invalid JSON arguments")
    if config.before_tool_call is not None:
        try:
            result = await _await_maybe(config.before_tool_call(tc.name, args, token))
        except Exception as e:  # noqa: BLE001
            return args, tool_error(f"Hook blocked execution: {e}")
        if isinstance(result, dict) and result.get("__block__"):
            return result, tool_error(str(result.get("__reason__", "Blocked by hook")))
        if isinstance(result, dict):
            args = result
    return args, None


async def _run_handler(
    name: str,
    args: dict,
    config: AgentLoopConfig,
    token: CancelToken,
) -> _HandlerResult:
    """Execute one tool.

    Bridge tools go through ``config.bridge_dispatch`` (progressive
    disclosure); everything else runs through ``registry.dispatch`` in a
    worker thread so the security hook chain and the ``__block__``
    protocol are preserved (Layer 2).  ApprovalBlockedError is routed to
    ``config.on_approval_blocked``; an approved retry calls the raw
    handler directly (mirrors the legacy approved path).  A denial is
    flagged via ``_HandlerResult.denied`` so the frontend can show
    "已拒绝" instead of a generic failure.
    """
    if config.bridge_dispatch is not None and name in BRIDGE_TOOL_NAMES:
        raw = await _await_maybe(config.bridge_dispatch(name, args))
        return _HandlerResult(raw if isinstance(raw, str) else json.dumps(raw, ensure_ascii=False))
    try:
        raw = await asyncio.to_thread(registry.dispatch, name, args)
    except Exception as e:  # noqa: BLE001
        if type(e).__name__ == "ApprovalBlockedError":
            decision = "denied"
            if config.on_approval_blocked is not None:
                decision = await _await_maybe(config.on_approval_blocked(name, str(e)))
            if decision == "approved":
                raw = await asyncio.to_thread(_dispatch_bypassing_hooks, name, args)
                return _HandlerResult(raw if isinstance(raw, str) else json.dumps(raw, ensure_ascii=False))
            return _HandlerResult(tool_error("用户拒绝了操作"), denied=True)
        logger.exception("Tool %s failed", name)
        return _HandlerResult(tool_error(str(e)))
    return _HandlerResult(raw if isinstance(raw, str) else json.dumps(raw, ensure_ascii=False))


def _dispatch_bypassing_hooks(name: str, args: dict) -> str:
    """Approved retry: call the raw handler directly, skipping hooks."""
    entry = registry.get_entry(name)
    if entry is None:
        return tool_error(f"Unknown tool: {name}")
    try:
        result = entry.handler(args)
    except Exception as e:  # noqa: BLE001
        return tool_error(str(e))
    return result if isinstance(result, str) else json.dumps(result, ensure_ascii=False)


async def _finalize(
    name: str,
    args: dict,
    result: str,
    config: AgentLoopConfig,
    token: CancelToken,
) -> str:
    """Run the after_tool_call hook (AfterToolCallEvent + rewrites)."""
    if config.after_tool_call is not None:
        try:
            result = await _await_maybe(config.after_tool_call(name, args, result, token))
        except Exception as e:  # noqa: BLE001
            logger.warning("After-hook failed for tool %s: %s", name, e)
    return result


__all__ = ["dispatch_tool_batch"]
