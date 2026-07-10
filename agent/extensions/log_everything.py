"""LogEverythingExtension — M2-style demo / debugging extension.

Logs every event type to the ``zlink-agent.events`` logger at DEBUG level.
Useful for tracing the event flow during development; harmless in
production (set ``enabled = False`` in the registry to silence).

This is the same pattern described in
``docs/extending-zlink-agent.md`` — the class exists so the M5+
settings page has at least one always-on, observation-only extension
that users can safely toggle to see the UI work.
"""

from __future__ import annotations

import logging

from agent.events import Event, Extension

logger = logging.getLogger("zlink-agent.events")


class LogEverythingExtension(Extension):
    """Logs every event to the ``zlink-agent.events`` logger.

    The ``on_event`` catch-all runs after the typed handlers (none of
    which this extension implements), so it sees everything.
    """

    name = "log-everything"
    enabled = True

    def on_event(self, event: Event) -> None:
        # Don't log at INFO — this can fire hundreds of times per
        # conversation.  DEBUG is the right level; the user can
        # enable it in their logging config to see the trace.
        logger.debug("event: type=%s", event.type)
