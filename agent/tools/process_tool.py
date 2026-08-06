"""Process management tool — list running processes and kill them.

Uses `ps` and `kill` system commands. Cross-platform (Unix/macOS/Windows).
"""

import json
import logging
import os
import platform
import signal
import subprocess
import sys

from agent.tools.registry import registry, tool_error, tool_result

logger = logging.getLogger(__name__)

_IS_WINDOWS = sys.platform == "win32"


def _list_processes() -> str:
    """List running processes."""
    if _IS_WINDOWS:
        args = ["tasklist", "/FO", "CSV", "/NH"]
    else:
        args = ["ps", "aux", "--no-headers"] if platform.system() != "Darwin" else ["ps", "aux"]

    try:
        result = subprocess.run(args, capture_output=True, text=True, timeout=10)
        if result.returncode != 0:
            return json.dumps({"error": f"ps failed: {result.stderr.strip()}"})
        return result.stdout
    except subprocess.TimeoutExpired:
        return json.dumps({"error": "ps timed out"})
    except FileNotFoundError:
        return json.dumps({"error": "ps not found on this system"})


def _kill_process(pid: int, force: bool = False) -> dict:
    """Kill a process by PID."""
    try:
        if _IS_WINDOWS:
            sig = signal.SIGTERM
            cmd = ["taskkill", "/PID", str(pid), "/F"] if force else ["taskkill", "/PID", str(pid)]
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
            if proc.returncode != 0:
                return {"success": False, "error": proc.stderr.strip()}
            return {"success": True}
        else:
            sig = signal.SIGKILL if force else signal.SIGTERM
            os.kill(pid, sig)
            return {"success": True}
    except ProcessLookupError:
        return {"success": False, "error": f"PID {pid} not found"}
    except PermissionError:
        return {"success": False, "error": f"Permission denied to kill PID {pid}"}
    except Exception as e:
        return {"success": False, "error": str(e)}


def process_tool(action: str, pid: int | None = None, force: bool = False) -> str:
    """Manage system processes.

    Args:
        action: "list" to list processes, "kill" to kill a process.
        pid: Process ID (required for "kill").
        force: Use SIGKILL instead of SIGTERM (Unix) or /F (Windows).

    Returns:
        JSON string.
    """
    action = (action or "list").strip().lower()

    if action == "list":
        output = _list_processes()
        return tool_result(data=output)

    elif action == "kill":
        if pid is None:
            return tool_error("pid is required for kill action")
        result = _kill_process(pid, force=force)
        if result.get("success"):
            return tool_result(data=f"Process {pid} terminated.")
        return tool_error(result.get("error", f"Failed to kill PID {pid}"))

    else:
        return tool_error(f"Unknown action: {action}. Supported: list, kill")


PROCESS_SCHEMA = {
    "name": "process",
    "description": (
        "管理系统进程。支持两个操作：\\n"
        "1. `list` — 列出所有正在运行的进程（含 PID、CPU、内存、命令）\\n"
        "2. `kill` — 终止指定 PID 的进程（先尝试 SIGTERM，force=true 则 SIGKILL）"
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["list", "kill"],
                "description": "操作类型: list=列出进程, kill=终止进程",
            },
            "pid": {
                "type": "integer",
                "description": "要终止的进程 PID（action=kill 时必需）",
            },
            "force": {
                "type": "boolean",
                "description": "是否强制终止（Unix: SIGKILL, Windows: /F）",
                "default": False,
            },
        },
        "required": ["action"],
    },
}

registry.register(
    name="process",
    execution_mode="sequential",
    toolset="system",
    schema=PROCESS_SCHEMA,
    handler=lambda args, **kw: process_tool(
        action=args.get("action", "list"),
        pid=args.get("pid"),
        force=args.get("force", False),
    ),
    description="管理系统进程（列出/终止）",
    emoji="⚙️",
    risk_level="medium",
)
