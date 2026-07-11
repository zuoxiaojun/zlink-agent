"""Default security hooks registered on the tool registry.

These hooks run before/after every tool call and provide a defence-in-depth
layer on top of each tool's own input validation.
"""

import json
import logging
import threading
import time

from agent import config_manager as _cm
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


# ── Approval system ─────────────────────────────────────────────

# Cache of approved tool calls: key="tool_name:json_args" → timestamp
_APPROVED_CALLS: dict[str, float] = {}
_APPROVAL_TTL = 60.0  # seconds before an approval expires
_approval_lock = threading.Lock()


def _get_tool_risk_level(tool_name: str) -> str:
    """Get the risk_level of a registered tool. Defaults to 'low'."""
    entry = registry.get_entry(tool_name)
    if entry is None:
        return "low"
    return entry.risk_level


def approval_hook(tool_name: str, args: dict) -> dict:
    """BeforeHook that checks approval_mode before executing medium/high risk tools.

    Three modes:
    - ``allow_all`` (default): pass through, no blocking.
    - ``reject_all``: block all medium and high risk tools.
    - ``approve``: block high-risk tools unless pre-approved via ``record_approval()``.
    """
    try:
        config = _cm.load()
        mode = getattr(config, "approval_mode", "allow_all")
    except Exception:
        return args

    risk = _get_tool_risk_level(tool_name)

    if mode == "allow_all":
        return args

    if mode == "reject_all" and risk in ("medium", "high"):
        return {
            "__block__": True,
            "__reason__": f"工具 {tool_name} 已被管理员禁用（当前审批模式: 全部拒绝）",
        }

    if mode == "approve" and risk == "high":
        with _approval_lock:
            # 优先检查精确匹配（tool_name + args）
            key = f"{tool_name}:{json.dumps(args, ensure_ascii=False, sort_keys=True)}"
            ts = _APPROVED_CALLS.get(key)
            if ts is not None and (time.monotonic() - ts) < _APPROVAL_TTL:
                return args
            # 其次检查通配匹配（仅 tool_name, 由 confirm_tool_execution 写入）
            wild_key = f"{tool_name}:*"
            ts = _APPROVED_CALLS.get(wild_key)
            if ts is not None and (time.monotonic() - ts) < _APPROVAL_TTL:
                # 通配 key 使用后立即消耗，防止同一审批重复执行
                del _APPROVED_CALLS[wild_key]
                return args
        return {
            "__block__": True,
            "__reason__": (
                f"⚠️ 需要你的确认才能执行以下操作：\n"
                f"工具: {tool_name}\n"
                f"参数: {json.dumps(dict(args), ensure_ascii=False)}\n"
                f"请在聊天中回复「批准」或「拒绝」。"
            ),
        }

    return args


def record_approval(tool_name: str, args: dict) -> None:
    """Record user approval for a specific tool call."""
    now = time.monotonic()
    with _approval_lock:
        # 精确匹配 key
        key = f"{tool_name}:{json.dumps(args, ensure_ascii=False, sort_keys=True)}"
        _APPROVED_CALLS[key] = now
        # 通配 key — 忽略 args 差异，匹配该工具任何调用
        wild_key = f"{tool_name}:*"
        _APPROVED_CALLS[wild_key] = now


def clear_approvals() -> None:
    """Clear all recorded approvals (e.g. on session end)."""
    with _approval_lock:
        _APPROVED_CALLS.clear()


def register_default_hooks():
    """Install the built-in security hooks.  Idempotent — safe to call multiple times."""
    # Remove first to avoid duplicates on reload
    registry.remove_before_hook(_security_before_hook)
    registry.remove_after_hook(_security_after_hook)
    registry.remove_before_hook(approval_hook)
    registry.add_before_hook(approval_hook)
    registry.add_before_hook(_security_before_hook)
    registry.add_after_hook(_security_after_hook)
    logger.info("Default security hooks registered")


# Auto-register on import
register_default_hooks()
