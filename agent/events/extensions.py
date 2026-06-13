"""Extension system — typed handlers for agent events.

Pi's extension model lets users add behaviour without modifying the
agent loop.  YS-Agent adopts the same shape:

* :class:`Extension` is the base class.  Subclasses override typed
  handler methods (``on_before_tool_call`` etc.).
* :class:`ExtensionRunner` walks the class, finds the handler methods
  that match an event's ``type``, and subscribes them to the bus.

Why typed methods instead of a single ``handle(event)``?
--------------------------------------------------------
* IDE auto-complete works on event-specific signatures.
* Subclasses don't need to write ``if event.type == "..."`` dispatch.
* Static type checkers can catch signature mismatches.

What extensions can do
----------------------
* Read events (logging, telemetry, audit).
* Modify mutable event fields (e.g. ``event.args`` for tool calls,
  ``event.messages`` for LLM calls).
* Cancel events that have a cancellation contract (see
  :mod:`agent.events.types`).
* Spawn background work in their own thread (the bus is synchronous,
  but extensions can ``threading.Thread(...).start()`` if needed).

What extensions cannot do
-------------------------
* Replace the LLM call.  (M3 will add a ``provider`` swap extension
  point.)
* Modify a tool's schema.  (Use the tool registry directly.)
* Persist state across sessions without going through
  ``fact_memory`` / ``memory_manager`` — extensions are not given a DB.
"""

from __future__ import annotations

import logging
from collections.abc import Callable

from agent.events.bus import Event, EventBus, event_bus

logger = logging.getLogger(__name__)


class Extension:
    """Base class for YS-Agent extensions.

    Subclass and override any ``on_*`` method.  Only methods that match
    the typed event contract are wired up.  Unhandled events are
    ignored by this extension.

    Naming convention
    -----------------
    The handler name must be ``on_<event_type>`` (with underscores, not
    camelCase).  Example: event type ``"before_tool_call"`` →
    handler ``on_before_tool_call``.

    Subclasses may also override :meth:`on_event` to receive *all*
    events (typed handlers run first, then ``on_event``).  This is
    useful for the logging extension.
    """

    # A short human-readable name.  Subclasses should override.
    name: str = "unnamed-extension"

    # Whether to enable this extension by default.  M5 will wire this
    # into a config toggle; for now, all extensions auto-register.
    enabled: bool = True

    def on_event(self, event: Event) -> None:
        """Catch-all handler.  Called *after* any typed handler.

        Default: do nothing.  Override for diagnostics / logging.
        """
        return None


# Map event type → handler name suffix (after "on_")
_EVENT_TYPE_TO_HANDLER = {
    "session_start": "on_session_start",
    "session_end": "on_session_end",
    "user_message": "on_user_message",
    "before_llm_call": "on_before_llm_call",
    "after_llm_call": "on_after_llm_call",
    "before_tool_call": "on_before_tool_call",
    "after_tool_call": "on_after_tool_call",
    "session_before_compact": "on_session_before_compact",
}


class ExtensionRunner:
    """Wires a single :class:`Extension` instance to the event bus.

    The runner introspects the extension's methods at construction
    time, finds those that match a known event type, and subscribes a
    small dispatcher function for each.  When the bus publishes an
    event, the dispatcher looks up the right method and calls it.

    One runner per extension.  Most users will only ever instantiate
    one via :func:`register_extensions`.
    """

    def __init__(
        self,
        extension: Extension,
        bus: EventBus | None = None,
    ) -> None:
        self.extension = extension
        self.bus = bus or event_bus
        self._unsubscribers: list[Callable[[], None]] = []
        self._wire()

    def _wire(self) -> None:
        for event_type, handler_name in _EVENT_TYPE_TO_HANDLER.items():
            handler = getattr(self.extension, handler_name, None)
            if handler is None:
                continue
            # Skip if the subclass inherited a no-op (just ``...`` or
            # ``pass``); we want the *override* signal, not the base.
            if handler.__qualname__.startswith("Extension."):
                continue
            unsub = self.bus.subscribe(self._make_dispatcher(event_type, handler))
            self._unsubscribers.append(unsub)

        # Always subscribe the catch-all on_event hook.
        if self.extension.on_event.__qualname__ != "Extension.on_event":
            unsub = self.bus.subscribe(self.extension.on_event)
            self._unsubscribers.append(unsub)

    def _make_dispatcher(
        self,
        event_type: str,
        handler: Callable[[Event], None],
    ) -> Callable[[Event], None]:
        def dispatch(event: Event) -> None:
            if event.type != event_type:
                return
            try:
                handler(event)
            except Exception:
                logger.exception(
                    "Extension %r handler for %s failed",
                    self.extension.name,
                    event_type,
                )

        return dispatch

    def shutdown(self) -> None:
        """Unsubscribe from the bus.  Useful in tests."""
        for unsub in self._unsubscribers:
            unsub()
        self._unsubscribers.clear()


# Track all runners that are currently *active* (subscribed to the bus).
# Tests use this to clean up; M5+ uses it to toggle extensions at runtime.
_active_runners: list[ExtensionRunner] = []

# Track every Extension instance that has been registered, even if
# it's currently disabled.  This is what M5+ ``apply_config_overrides``
# iterates to flip a previously-disabled extension back on (or vice
# versa) without re-instantiating the Extension class.
_all_extensions: list[Extension] = []


def register_extensions(
    extensions: list[Extension],
    bus: EventBus | None = None,
) -> list[ExtensionRunner]:
    """Create a runner per extension and return them.

    Disabled extensions (``ext.enabled = False``) are still tracked in
    the global list — M5+ uses this to toggle them on at runtime via
    :func:`apply_config_overrides`.  They are simply not subscribed to
    the bus on this call.

    Call :func:`shutdown_all_extensions` to clean up (mostly for tests).
    """
    runners: list[ExtensionRunner] = []
    for ext in extensions:
        # Always remember the instance, even if disabled.
        if ext not in _all_extensions:
            _all_extensions.append(ext)
        if not ext.enabled:
            logger.debug("Extension %r disabled — skipping subscription", ext.name)
            continue
        runners.append(ExtensionRunner(ext, bus=bus))
        logger.info("Extension registered: %s", ext.name)
    _active_runners.extend(runners)
    return runners


def shutdown_all_extensions() -> None:
    """Shut down every active runner and forget all registered
    extensions.  Mostly for tests — production code should use
    :func:`apply_config_overrides` to toggle individual extensions.
    """
    for runner in _active_runners:
        runner.shutdown()
    _active_runners.clear()
    _all_extensions.clear()


def list_all_extensions() -> list[Extension]:
    """Snapshot of every :class:`Extension` instance ever registered.
    Includes both active and disabled.  Order matches insertion order
    (first registered → first in list)."""
    return list(_all_extensions)


def list_active_extensions() -> list[Extension]:
    """Snapshot of currently subscribed extensions (those with an active
    runner).  Derived from :func:`list_all_extensions` by checking
    ``enabled`` — the runner is the source of truth."""
    return [ext for ext in _all_extensions if ext.enabled]


def apply_config_overrides(
    disabled_names: set[str] | list[str],
    bus: EventBus | None = None,
) -> tuple[list[Extension], list[Extension]]:
    """Reconcile the live extension set with the persisted config.

    Given the set of *disabled* extension names (from
    ``config_manager``), flip ``Extension.enabled`` on each registered
    instance and rewire the bus.  Returns ``(now_active, now_disabled)``
    so callers (e.g. the M5+ REST API) can report what changed.

    Algorithm
    ---------
    * If an extension's name is in *disabled_names* and is currently
      active → flip to disabled, shut its runner down.
    * If an extension's name is NOT in *disabled_names* and is
      currently disabled → flip to enabled, create a new runner.

    The matching is by ``ext.name``.  Two extensions with the same
    name both get toggled (the registry does not enforce uniqueness;
    that's the installer's job).
    """
    bus = bus or event_bus
    disabled_set = set(disabled_names)
    now_active: list[Extension] = []
    now_disabled: list[Extension] = []

    # 1. Shut down any active runner whose extension should be disabled.
    for ext in list(_all_extensions):
        if ext.name in disabled_set and ext.enabled:
            ext.enabled = False
            now_disabled.append(ext)
        elif ext.name not in disabled_set and not ext.enabled:
            ext.enabled = True
            now_active.append(ext)

    # 2. Rewire: tear down all active runners, then re-subscribe the
    #    still-enabled ones.  Simpler than tracking per-runner state.
    for runner in _active_runners:
        runner.shutdown()
    _active_runners.clear()
    for ext in _all_extensions:
        if not ext.enabled:
            continue
        _active_runners.append(ExtensionRunner(ext, bus=bus))
        logger.info("Extension re-registered: %s", ext.name)
    return now_active, now_disabled


__all__ = [
    "Extension",
    "ExtensionRunner",
    "register_extensions",
    "shutdown_all_extensions",
    "list_all_extensions",
    "list_active_extensions",
    "apply_config_overrides",
]
