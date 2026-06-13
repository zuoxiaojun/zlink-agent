"""Event bus — synchronous publish/subscribe.

M1 design notes
---------------
* Synchronous: ``publish(event)`` calls every subscriber in registration order
  and returns when they all complete.  This is intentional — the agent loop
  is itself synchronous, so we don't need async event handling.  Subscribers
  that want to do background work can spawn their own thread.
* Thread-safe: YS-Agent runs the agent in a thread pool
  (see ``backend/api/chat.py``), so subscribers may be added/removed from
  multiple threads.  Registration takes a lock; publish does not (since
  iteration over the subscriber list is GIL-safe in CPython and we replace
  the list atomically on subscribe/unsubscribe).
* Cancellation: events subclass ``Event`` which exposes ``cancel(reason)``.
  Subscribers that mutate the event (e.g. modifying ``event.args``) can
  also call ``cancel()`` to block downstream processing.
* No filtering: every subscriber sees every event.  M2 will add typed
  handlers via the Extension API (``on_before_tool_call`` etc.) so this
  raw bus is mostly for low-level cases.

Why not Pi's async event bus?
-----------------------------
Pi's runtime is async (TypeScript + asyncio pattern).  YS-Agent's agent
loop is sync (single thread, called from a worker thread).  An async bus
would require making the whole agent loop async — a 3-4 day rewrite for
no current benefit.  Revisit if we ever move to async streaming.
"""

from __future__ import annotations

import logging
import threading
from collections.abc import Callable
from typing import Any

logger = logging.getLogger(__name__)


class Event:
    """Base class for all events flowing through the bus.

    Subclasses define their payload as plain attributes.  The bus does not
    introspect them — handlers receive the event object and read fields
    directly.

    Cancellation
    ------------
    ``cancel(reason)`` sets ``_cancelled=True`` and records the reason.
    The agent loop checks ``event._cancelled`` after ``publish()`` returns
    and short-circuits the corresponding action.  This is the Pi-style
    "block the action" hook.
    """

    # Subclasses override this.  Not enforced — we use it for logging only.
    type: str = "event"

    def __init__(self, **fields: Any) -> None:
        # Initialise payload fields.  Subclasses either pass them here
        # (``BeforeToolCallEvent(tool_name=..., args=...)``) or assign
        # them after construction.  We accept kwargs for convenience.
        self._cancelled: bool = False
        self._cancel_reason: str | None = None
        for k, v in fields.items():
            setattr(self, k, v)

    @property
    def cancelled(self) -> bool:
        return self._cancelled

    @property
    def cancel_reason(self) -> str | None:
        return self._cancel_reason

    def cancel(self, reason: str = "") -> None:
        """Mark this event as cancelled.  The agent loop will short-circuit
        the corresponding action after ``publish()`` returns.
        """
        self._cancelled = True
        self._cancel_reason = reason or "cancelled"

    def __repr__(self) -> str:
        bits = [f"type={self.type!r}"]
        if self._cancelled:
            bits.append(f"cancelled={self._cancel_reason!r}")
        return f"Event({', '.join(bits)})"


# Subscriber signature: receive an event, return nothing.
Subscriber = Callable[[Event], None]


class EventBus:
    """Synchronous, thread-safe pub/sub for agent events.

    Usage::

        bus = EventBus()
        bus.subscribe(my_handler)
        bus.publish(BeforeToolCallEvent(...))
    """

    def __init__(self) -> None:
        self._subscribers: list[Subscriber] = []
        self._lock = threading.Lock()

    def subscribe(self, handler: Subscriber) -> Callable[[], None]:
        """Register a handler.  Returns an unsubscribe function."""
        with self._lock:
            self._subscribers.append(handler)

        def _unsub() -> None:
            self.unsubscribe(handler)

        return _unsub

    def unsubscribe(self, handler: Subscriber) -> bool:
        """Remove a previously registered handler.  Returns True if removed."""
        with self._lock:
            try:
                self._subscribers.remove(handler)
                return True
            except ValueError:
                return False

    def subscribers(self) -> tuple[Subscriber, ...]:
        """Snapshot of current subscribers (for introspection / tests)."""
        # Safe to read without lock — tuple() is atomic in CPython.
        return tuple(self._subscribers)

    def clear(self) -> None:
        """Remove all subscribers.  Mostly for tests."""
        with self._lock:
            self._subscribers.clear()

    def publish(self, event: Event) -> Event:
        """Dispatch *event* to every subscriber in registration order.

        Returns the same event (possibly mutated, possibly cancelled).
        Subscriber exceptions are logged and swallowed — one buggy handler
        must not break the agent loop.
        """
        for handler in list(self._subscribers):
            try:
                handler(event)
            except Exception:
                logger.exception("Event handler %r failed for %s", handler, event.type)
        return event


# Module-level singleton — the agent loop and tool registry publish here.
event_bus = EventBus()


__all__ = ["Event", "EventBus", "event_bus"]
