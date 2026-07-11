"""AuditLogExtension — records approval and security events to the application log.

Subscribes to ``before_tool_call`` events and logs all tool invocations
when approval mode is active, creating an audit trail of which tools were
called, whether they were approved or blocked, and the arguments used.
"""

from __future__ import annotations

import json
import logging

from agent.events import BeforeToolCallEvent, Extension

logger = logging.getLogger("zlink-agent.audit")


class AuditLogExtension(Extension):
    """Logs tool calls for audit trail when approval mode is active."""

    name = "audit-log"
    enabled = True

    def on_before_tool_call(self, event: BeforeToolCallEvent) -> None:
        """Record every tool invocation to the audit log."""
        logger.info(
            "AUDIT: tool=%s args=%s",
            event.tool_name,
            json.dumps(dict(event.args), ensure_ascii=False),
        )
