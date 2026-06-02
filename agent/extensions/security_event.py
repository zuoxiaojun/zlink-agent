"""SecurityEventExtension — event-bus version of the same checks
``agent/tools/security_hooks.py`` performs at the registry layer.

M5+ ships both layers side-by-side.  Each one blocks dangerous
operations independently; the user can disable the event layer from
the M5+ settings page (and the registry hooks keep working as a
defence-in-depth backstop).

Why both?  Three reasons:

1. **Migration path.**  Users who already trust the registry hooks
   don't lose anything when M5+ lands.  M6+ will consolidate.
2. **Exercising the event system.**  Without an always-on
   security extension, the M5+ settings page has nothing visible to
   toggle.  This class gives the UI a real, observable target.
3. **Demonstrating the cancellation contract.**  ``BeforeToolCallEvent``
   has the cleanest cancel API in the system.  A security extension
   is the canonical "block dangerous operations" use case in Pi, so
   duplicating it here makes the docs concrete.

The lists of denied paths / shell patterns are imported from
``security_hooks`` so we have a single source of truth.  When the
M6+ consolidation lands, this module will become the only
implementation and ``security_hooks`` will delegate to it.
"""
from __future__ import annotations

import logging
import os
from pathlib import Path

from agent.events import Extension, BeforeToolCallEvent

logger = logging.getLogger(__name__)


# Re-use the deny lists from the registry hooks.  If you change them
# there, this extension picks them up on next import.
from agent.tools.security_hooks import (  # noqa: E402
    _DENY_WRITE_PATHS,
    _DENY_SHELL_PATTERNS,
)


class SecurityEventExtension(Extension):
    """Block obviously dangerous tool calls via the event bus.

    Identical semantics to ``agent.tools.security_hooks``:

    * ``write_file`` / ``patch`` to a denied path → cancel.
    * ``terminal`` with a denied shell pattern → cancel.
    """

    name = "security-event"
    enabled = True

    def on_before_tool_call(self, event: BeforeToolCallEvent) -> None:
        if event.cancelled:
            return  # someone else already blocked it

        # Path-based blocks (write_file / patch)
        if event.tool_name in ("write_file", "patch"):
            path = event.args.get("path", "")
            if path:
                try:
                    resolved = os.path.abspath(os.path.expanduser(path))
                except (OSError, ValueError):
                    return
                for denied in _DENY_WRITE_PATHS:
                    try:
                        denied_expanded = os.path.abspath(os.path.expanduser(denied))
                    except (OSError, ValueError):
                        continue
                    if resolved.startswith(denied_expanded):
                        event.cancel(reason=f"拒绝写入受保护路径: {denied}")
                        return

        # Shell-pattern blocks (terminal)
        if event.tool_name == "terminal":
            command = event.args.get("command", "")
            cmd_lower = command.lower().replace(" ", "")
            for pattern in _DENY_SHELL_PATTERNS:
                if pattern.lower().replace(" ", "") in cmd_lower:
                    event.cancel(reason=f"拒绝危险命令: {pattern}")
                    return
