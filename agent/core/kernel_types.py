"""Kernel type contracts — the only interface between the loop and policy.

Pi-style kernel redesign (spec 2026-08-06-pi-style-kernel-design).  This
module mirrors Pi's ``packages/agent/src/types.ts``: pure types + constants,
no logic.  ``AgentLoopConfig`` carries every strategy hook; ``CancelToken``
replaces Pi's AbortSignal; the 11 ``AgentEvent`` classes are the kernel's
only outward event channel.
"""

from __future__ import annotations

import asyncio
import sys
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from agent.core.llm_providers.base import LLMResponse


class CancelToken:
    """Cancellation token — the Python analogue of Pi's AbortSignal.

    Passed through every hook and the whole loop; ``cancel()`` from any
    thread marks it cancelled; ``check()`` raises ``asyncio.CancelledError``
    at the next cooperative point.
    """

    def __init__(self) -> None:
        self._event = asyncio.Event()

    def cancel(self) -> None:
        self._event.set()

    @property
    def cancelled(self) -> bool:
        return self._event.is_set()

    async def wait(self) -> None:
        await self._event.wait()

    def check(self) -> None:
        if self._event.is_set():
            raise asyncio.CancelledError()


@dataclass
class AgentContext:
    """Mutable per-run state owned by the loop."""

    messages: list[dict] = field(default_factory=list)
    api_calls: int = 0


@dataclass(frozen=True)
class TurnUpdate:
    """Returned by ``prepare_next_turn`` — per-turn config overrides."""

    model: str | None = None
    temperature: float | None = None
    max_tokens: int | None = None


@dataclass
class ToolResult:
    """One executed (or failed) tool call, in transcript order."""

    tool_call_id: str
    tool_name: str
    result: str
    is_error: bool = False
    terminate: bool = False


@dataclass
class ExecutedToolBatch:
    """Return value of ``dispatch_tool_batch``."""

    messages: list[ToolResult] = field(default_factory=list)
    terminate: bool = False


# ── AgentLoopConfig ────────────────────────────────────────────────
# Hook signatures (all optional; sync or async — the loop awaits them):
#   call_llm(full_messages, *, emit, message, token) -> LLMResponse
#       full_messages = [system?] + context.messages; must emit MessageUpdate
#       via *emit* while streaming (message = the partial assistant dict)
#   transform_context(messages, token) -> list[dict]
#   before_tool_call(tool_name, args, token) -> dict
#       returns modified args, or {"__block__": True, "__reason__": <原因>} to block
#   after_tool_call(tool_name, args, result, token) -> str
#   prepare_next_turn(ctx, token) -> TurnUpdate | None
#   should_stop_after_turn(ctx, token) -> bool
#   get_steering_messages(token) -> list[dict]
#   get_follow_up_messages(token) -> list[dict]
#   bridge_dispatch(tool_name, args) -> str
#   on_approval_blocked(tool_name, reason) -> str   ("approved" | "denied")
# ctx = {"message": dict, "tool_results": list[ToolResult],
#        "messages": list[dict], "api_calls": int}


@dataclass(frozen=True)
class AgentLoopConfig:
    """One run's configuration + all strategy hooks (all optional)."""

    model: str
    temperature: float = 0.7
    max_tokens: int | None = None
    system_prompt: str = ""
    tool_defs: list[dict] = field(default_factory=list)
    max_tool_result_length: int = sys.maxsize
    call_llm: Callable[..., Awaitable[LLMResponse]] | None = None
    transform_context: Callable[[list[dict], CancelToken], list[dict] | Awaitable[list[dict]]] | None = None
    before_tool_call: Callable[[str, dict, CancelToken], dict | Awaitable[dict]] | None = None
    after_tool_call: Callable[[str, dict, str, CancelToken], str | Awaitable[str]] | None = None
    prepare_next_turn: Callable[[dict, CancelToken], TurnUpdate | None | Awaitable[TurnUpdate | None]] | None = None
    should_stop_after_turn: Callable[[dict, CancelToken], bool | Awaitable[bool]] | None = None
    get_steering_messages: Callable[[CancelToken], list[dict] | Awaitable[list[dict]]] | None = None
    get_follow_up_messages: Callable[[CancelToken], list[dict] | Awaitable[list[dict]]] | None = None
    bridge_dispatch: Callable[[str, dict], str | Awaitable[str]] | None = None
    on_approval_blocked: Callable[[str, str], str | Awaitable[str]] | None = None


# ── AgentEvent union: dataclasses discriminated by ``type`` ────────


@dataclass(frozen=True)
class AgentStart:
    type: str = "agent_start"


@dataclass(frozen=True)
class AgentEnd:
    messages: list[dict]
    type: str = "agent_end"


@dataclass(frozen=True)
class TurnStart:
    type: str = "turn_start"


@dataclass(frozen=True)
class TurnEnd:
    message: dict
    tool_results: list[ToolResult]
    type: str = "turn_end"


@dataclass(frozen=True)
class MessageStart:
    message: dict
    type: str = "message_start"


@dataclass(frozen=True)
class MessageUpdate:
    message: dict
    delta: str
    reasoning_delta: str | None = None
    type: str = "message_update"


@dataclass(frozen=True)
class MessageEnd:
    message: dict
    type: str = "message_end"


@dataclass(frozen=True)
class ToolExecutionStart:
    tool_call_id: str
    tool_name: str
    args: dict
    type: str = "tool_execution_start"


@dataclass(frozen=True)
class ToolExecutionUpdate:
    tool_call_id: str
    tool_name: str
    partial_result: str
    type: str = "tool_execution_update"


@dataclass(frozen=True)
class ToolExecutionEnd:
    tool_call_id: str
    tool_name: str
    result: str
    is_error: bool = False
    denied: bool = False
    type: str = "tool_execution_end"


@dataclass(frozen=True)
class LLMRetry:
    """One failed LLM attempt that will be retried after ``delay`` seconds.

    Emitted from the provider retry loop (via the adapter) so frontends can
    show live feedback instead of a silent spinner.  ``error`` is a short
    human-readable reason (e.g. ``"HTTP 429"``, ``"ConnectError"``).
    """

    attempt: int
    delay: float
    error: str
    type: str = "llm_retry"


AgentEvent = (
    AgentStart
    | AgentEnd
    | TurnStart
    | TurnEnd
    | MessageStart
    | MessageUpdate
    | MessageEnd
    | ToolExecutionStart
    | ToolExecutionUpdate
    | ToolExecutionEnd
    | LLMRetry
)

__all__ = [
    "CancelToken",
    "AgentContext",
    "TurnUpdate",
    "ToolResult",
    "ExecutedToolBatch",
    "AgentLoopConfig",
    "AgentStart",
    "AgentEnd",
    "TurnStart",
    "TurnEnd",
    "MessageStart",
    "MessageUpdate",
    "MessageEnd",
    "ToolExecutionStart",
    "ToolExecutionUpdate",
    "ToolExecutionEnd",
    "LLMRetry",
    "AgentEvent",
]
