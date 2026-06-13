"""Complete event types — built on top of :mod:`agent.events.bus`.

These mirror the Pi event set, scoped to the events YS-Agent actually
needs.  New event types should be added here, not in random modules, so
the full lifecycle is discoverable in one file.

Conventions
-----------
* All event types end in ``Event``.
* All event types inherit :class:`agent.events.bus.Event` (so ``cancel()``
  and ``cancelled`` work).
* All events carry a ``type`` class attribute that the bus logs.

Cancellation
------------
Events that the agent loop checks for cancellation:

* :class:`BeforeToolCallEvent`  — cancelled → skip the tool, return the
  ``cancel_reason`` as the tool result.
* :class:`BeforeLLMCallEvent`   — cancelled → skip the LLM call entirely.
  Useful for prompt-injection guards.

Other events are pure observation; cancelling them has no effect.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from agent.events.bus import Event

if TYPE_CHECKING:
    from agent.core.llm_client import LLMResponse


# -- Session lifecycle --


class SessionStartEvent(Event):
    """A new agent session is starting.

    Fired by ``AIAgent.__init__`` (or, more correctly, by the chat
    endpoint after a session is created).  Carries the loaded history so
    extensions can inspect it (e.g. inject a topic header).
    """

    type = "session_start"
    session_id: str
    history: list[dict]


class SessionEndEvent(Event):
    """The agent has finished a turn (either final response or stop).

    Fired at the end of ``run_conversation`` regardless of outcome.
    Extensions can flush state, write logs, etc.
    """

    type = "session_end"
    session_id: str
    final_response: str
    error: str | None = None
    api_calls: int = 0


# -- Per-turn events --


class UserMessageEvent(Event):
    """A user message arrived.

    Extensions can modify ``content`` (e.g. add context, redact PII) or
    cancel to reject the message entirely (rare).
    """

    type = "user_message"
    content: str | list


# -- LLM call events --


class BeforeLLMCallEvent(Event):
    """Fired immediately before the LLM call.

    Extensions may:
    * modify ``messages`` (add context, drop noisy tool results)
    * modify ``api_kwargs`` (override temperature, model, etc.)
    * cancel to skip the call (e.g. to short-circuit with a cached answer)
    """

    type = "before_llm_call"
    model: str
    messages: list[dict]  # full payload incl. system prompt
    api_kwargs: dict


class AfterLLMCallEvent(Event):
    """Fired after the LLM call returns.

    Read-only — extensions can inspect ``response`` but not modify it
    (M3's LLMProvider abstraction doesn't support re-injection yet).
    """

    type = "after_llm_call"
    model: str
    response: LLMResponse


# -- Tool call events --


class BeforeToolCallEvent(Event):
    """Fired immediately before a single tool executes.

    Extensions may:
    * modify ``args`` to rewrite the call
    * cancel to block execution; ``cancel_reason`` is returned as the
      tool result so the model sees a clean error.
    """

    type = "before_tool_call"
    tool_name: str
    args: dict


class AfterToolCallEvent(Event):
    """Fired after a tool returns, before the result is appended to messages.

    Extensions may rewrite ``result`` (a JSON string).  Useful for
    log redaction, size caps, format conversion.
    """

    type = "after_tool_call"
    tool_name: str
    args: dict
    result: str


# -- Compaction events (M4) --


class SessionBeforeCompactEvent(Event):
    """Fired inside ``compact_messages`` before the summary is finalised.

    This is the **Pi-style** hook that lets extensions contribute
    information to the summary (e.g. file snapshots, fact extraction).

    Extensions may:
    * read ``old_messages`` and the draft ``summary``
    * write ``event.extra`` — a list of strings appended to the
      final summary.
    """

    type = "session_before_compact"
    old_messages: list[dict]
    summary: str
    tracked_files: dict[str, str]  # path → contents (filled by core)
    extra: list[str]  # extension contributions


__all__ = [
    "Event",
    "SessionStartEvent",
    "SessionEndEvent",
    "UserMessageEvent",
    "BeforeLLMCallEvent",
    "AfterLLMCallEvent",
    "BeforeToolCallEvent",
    "AfterToolCallEvent",
    "SessionBeforeCompactEvent",
]
