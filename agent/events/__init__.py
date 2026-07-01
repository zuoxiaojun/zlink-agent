"""Event system for YS-Agent.

Hierarchy
---------
* :mod:`agent.events.bus`     — :class:`Event`, :class:`EventBus`, the
  module-level singleton.
* :mod:`agent.events.types`   — concrete event classes
  (:class:`BeforeToolCallEvent` etc.) and the cancellation contract.
* :mod:`agent.events.extensions` — :class:`Extension` base + the
  :class:`ExtensionRunner` that wires typed methods to events.
"""

from agent.events.bus import Event, EventBus, event_bus
from agent.events.extensions import (
    Extension,
    ExtensionRunner,
    register_extensions,
    shutdown_all_extensions,
)
from agent.events.types import (
    AfterLLMCallEvent,
    AfterToolCallEvent,
    BeforeLLMCallEvent,
    BeforeToolCallEvent,
    PhaseChangeEvent,
    SessionBeforeCompactEvent,
    SessionEndEvent,
    SessionStartEvent,
    UserMessageEvent,
)

__all__ = [
    "Event",
    "EventBus",
    "event_bus",
    "SessionStartEvent",
    "SessionEndEvent",
    "UserMessageEvent",
    "BeforeLLMCallEvent",
    "AfterLLMCallEvent",
    "BeforeToolCallEvent",
    "AfterToolCallEvent",
    "PhaseChangeEvent",
    "SessionBeforeCompactEvent",
    "Extension",
    "ExtensionRunner",
    "register_extensions",
    "shutdown_all_extensions",
]
