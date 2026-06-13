"""Default security hooks registered on the tool registry.

These hooks run before/after every tool call and provide a defence-in-depth
layer on top of each tool's own input validation.
"""

import logging

from agent.tools.registry import registry

logger = logging.getLogger(__name__)

# Paths that no tool should write to under any circumstances
_DENY_WRITE_PATHS = [
    "/etc",
    "/sys",
    "/proc",
    "/dev",
    "/boot",
    "/usr/lib",
    "/usr/bin",
    "/usr/sbin",
    "/System",
    "/Library",
    "~/.ssh",
    "~/.gnupg",
]

# Dangerous shell patterns (defence-in-depth; terminal_tool has its own list)
_DENY_SHELL_PATTERNS = [
    "rm -rf /",
    "mkfs.",
    "dd if=",
    ":(){ :|:& };:",  # fork bomb
    "chmod 777 /",
    "> /dev/sda",
]


def _security_before_hook(tool_name: str, args: dict) -> dict:
    """Block obviously dangerous operations before they reach the handler."""

    # --- path-based tools: reject writes to system directories ---
    path = args.get("path", "")
    if path and tool_name in ("write_file", "patch"):
        import os

        resolved = os.path.abspath(os.path.expanduser(path))
        for denied in _DENY_WRITE_PATHS:
            denied_expanded = os.path.abspath(os.path.expanduser(denied))
            if resolved.startswith(denied_expanded):
                return {"__block__": True, "__reason__": f"拒绝写入受保护路径: {denied}"}

    # --- terminal: reject known-dangerous patterns ---
    if tool_name == "terminal":
        command = args.get("command", "")
        cmd_lower = command.lower().replace(" ", "")
        for pattern in _DENY_SHELL_PATTERNS:
            if pattern.lower().replace(" ", "") in cmd_lower:
                return {"__block__": True, "__reason__": f"拒绝危险命令: {pattern}"}

    return args


def _security_after_hook(tool_name: str, args: dict, result: str) -> str:
    """Log tool results for audit trail (no modification)."""
    logger.debug("Tool %s completed (args=%s)", tool_name, args)
    return result


def register_default_hooks():
    """Install the built-in security hooks.  Idempotent — safe to call multiple times."""
    # Remove first to avoid duplicates on reload
    registry.remove_before_hook(_security_before_hook)
    registry.remove_after_hook(_security_after_hook)
    registry.add_before_hook(_security_before_hook)
    registry.add_after_hook(_security_after_hook)
    logger.info("Default security hooks registered")


# Auto-register on import
register_default_hooks()
