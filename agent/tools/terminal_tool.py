"""Terminal command execution tool.

Cross-platform shell execution with timeout and dangerous-command detection.
Supports bash (Unix) and cmd.exe / PowerShell (Windows).

Also provides:
- read_terminal: read recent command execution history
- close_terminal: kill running processes started by the terminal tool
"""

import json
import logging
import os
import re
import shutil
import signal
import subprocess
import sys
import threading
from collections import deque

from agent.tools.registry import registry, tool_error, tool_result

logger = logging.getLogger(__name__)

_IS_WINDOWS = sys.platform == "win32"

# ── Terminal execution history (for read_terminal) ───────────────────────
_MAX_HISTORY = 50
_terminal_history: deque[dict] = deque(maxlen=_MAX_HISTORY)
_history_lock = threading.Lock()

# Track running processes (for close_terminal)
_running_procs: dict[int, subprocess.Popen] = {}
_running_lock = threading.Lock()

# ── Dangerous command patterns (simplified from Hermes approval.py) ──────

_HARDLINE_PATTERNS = [
    (r"\brm\s+(-[^\s]*\s+)*(/|/\*)(\s|$)", "recursive delete of root"),
    (r"\brm\s+(-[^\s]*\s+)*(~|\$HOME)(/?|/\*)?(\s|$)", "recursive delete of home"),
    (r"\bmkfs(\.[a-z0-9]+)?\b", "format filesystem"),
    (r"\bdd\b[^\n]*\bof=/dev/", "dd to block device"),
    (r"\bkill\s+(-[^\s]+\s+)*-1\b", "kill all processes"),
    (r"^(shutdown|reboot|halt|poweroff)\b", "system shutdown/reboot"),
    (r"^init\s+[06]\b", "init 0/6"),
]

_RE_FLAGS = re.IGNORECASE | re.DOTALL
_HARDLINE_RE = [(re.compile(p, _RE_FLAGS), d) for p, d in _HARDLINE_PATTERNS]

_DANGEROUS_PATTERNS = [
    (r"\brm\s+(-[^\s]+\s+)*-rf\b", "recursive force delete"),
    (r"\bchmod\s+(-[^\s]*\s+)*777\b", "chmod 777"),
    (r"\bchown\b", "change ownership"),
    (r"\bsudo\b", "sudo command"),
    (r"\bpasswd\b", "change password"),
    (r"\bwget[^\n]*\|", "wget pipe to shell"),
    (r"\bcurl[^\n]*\|", "curl pipe to shell"),
    (r">\s*/dev/", "write to block device"),
    (r":\(\)\s*\{", "fork bomb"),
]

_DANGEROUS_RE = [(re.compile(p, _RE_FLAGS), d) for p, d in _DANGEROUS_PATTERNS]


def _check_dangerous(command: str) -> str | None:
    """Check if command is dangerous. Returns description if so, else None."""
    for pattern, desc in _HARDLINE_RE:
        if pattern.search(command):
            return desc
    for pattern, desc in _DANGEROUS_RE:
        if pattern.search(command):
            return desc
    return None


# ── Core execution ──────────────────────────────────────────────────────

DEFAULT_TIMEOUT = 120
MAX_OUTPUT_CHARS = 50_000


def _find_shell() -> str:
    """Find a usable shell — bash on Unix, cmd.exe on Windows."""
    if _IS_WINDOWS:
        comspec = os.environ.get("COMSPEC", "")
        if comspec:
            return comspec
        for candidate in ["cmd.exe", "powershell.exe", "pwsh.exe"]:
            found = shutil.which(candidate)
            if found:
                return found
        return "cmd.exe"
    return shutil.which("bash") or shutil.which("sh") or "bash"


def _make_popen_args(command: str) -> list[str]:
    """Build subprocess args for the current platform."""
    if _IS_WINDOWS:
        shell = _find_shell()
        name = os.path.basename(shell).lower()
        if "powershell" in name or "pwsh" in name:
            return [shell, "-NoProfile", "-Command", command]
        return [shell, "/c", command]
    return [_find_shell(), "-c", command]


def _kill_process_tree(proc: subprocess.Popen) -> None:
    """Kill a process and its children, cross-platform."""
    if _IS_WINDOWS:
        subprocess.run(
            ["taskkill", "/F", "/T", "/PID", str(proc.pid)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    else:
        try:
            os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
        except Exception:
            proc.kill()


def _record_history(command: str, result: dict):
    """Record a terminal execution result in the history buffer."""
    with _history_lock:
        _terminal_history.append({
            "command": command,
            "timestamp": __import__("datetime").datetime.now().isoformat(),
            "stdout": result.get("stdout", ""),
            "stderr": result.get("stderr", ""),
            "exit_code": result.get("exit_code", -1),
            "success": result.get("success", False),
        })


def _track_process(proc: subprocess.Popen) -> int:
    """Track a running process so close_terminal can kill it later."""
    pid = proc.pid
    with _running_lock:
        _running_procs[pid] = proc
    return pid


def _untrack_process(pid: int):
    """Remove a finished process from the tracking dict."""
    with _running_lock:
        _running_procs.pop(pid, None)


def _execute(command: str, timeout: int, workdir: str | None) -> dict:
    """Execute a shell command and return result dict."""
    # Result accumulator — always passed through _record_history before return
    res: dict = {}

    danger = _check_dangerous(command)
    if danger:
        res = {
            "success": False,
            "error": f"命令被拒绝: {danger}。如需执行，请手动在终端中运行。",
            "stdout": "",
            "stderr": "",
            "exit_code": -1,
        }
        _record_history(command, res)
        return res

    shell_args = _make_popen_args(command)
    cwd = workdir or os.getcwd()

    try:
        popen_kwargs: dict = {
            "stdin": subprocess.DEVNULL,
            "stdout": subprocess.PIPE,
            "stderr": subprocess.PIPE,
            "cwd": cwd,
            "env": os.environ,
            "text": True,
            "encoding": "utf-8",
            "errors": "replace",
        }
        if not _IS_WINDOWS:
            popen_kwargs["preexec_fn"] = os.setsid
        proc = subprocess.Popen(shell_args, **popen_kwargs)
    except FileNotFoundError:
        res = {
            "success": False,
            "error": f"Shell not found: {shell_args[0]}",
            "stdout": "",
            "stderr": "",
            "exit_code": -1,
        }
        _record_history(command, res)
        return res
    except Exception as e:
        res = {
            "success": False,
            "error": f"Failed to start process: {e}",
            "stdout": "",
            "stderr": "",
            "exit_code": -1,
        }
        _record_history(command, res)
        return res

    _track_process(proc)

    try:
        stdout, stderr = proc.communicate(timeout=timeout)
        exit_code = proc.returncode
        _untrack_process(proc.pid)

        # Truncate output
        if stdout and len(stdout) > MAX_OUTPUT_CHARS:
            stdout = stdout[:MAX_OUTPUT_CHARS] + f"\n\n...（已截断 {len(stdout) - MAX_OUTPUT_CHARS} 字符）"
        if stderr and len(stderr) > MAX_OUTPUT_CHARS:
            stderr = stderr[:MAX_OUTPUT_CHARS] + f"\n\n...（已截断 {len(stderr) - MAX_OUTPUT_CHARS} 字符）"

        res = {
            "success": exit_code == 0,
            "stdout": stdout or "",
            "stderr": stderr or "",
            "exit_code": exit_code,
        }
    except subprocess.TimeoutExpired:
        _kill_process_tree(proc)
        _out, _err = proc.communicate(timeout=5)
        _untrack_process(proc.pid)
        res = {
            "success": False,
            "error": f"命令执行超时（{timeout}秒）",
            "stdout": (_out or "")[:MAX_OUTPUT_CHARS],
            "stderr": (_err or "")[:MAX_OUTPUT_CHARS],
            "exit_code": -1,
        }
    except Exception as e:
        _untrack_process(proc.pid)
        res = {
            "success": False,
            "error": f"执行异常: {e}",
            "stdout": "",
            "stderr": "",
            "exit_code": -1,
        }

    _record_history(command, res)
    return res


def _handle_terminal(args: dict) -> str:
    """Handle terminal tool call."""
    command = args.get("command", "")
    if not command or not isinstance(command, str):
        return tool_error("command（要执行的命令）是必需的")

    timeout = int(args.get("timeout", DEFAULT_TIMEOUT))
    workdir = args.get("workdir")
    description = args.get("description", "")

    # Log what we're doing
    logger.info("终端执行: %s", description or command[:80])

    result = _execute(command, timeout, workdir)

    error = result.get("error")
    if error:
        return tool_error(
            message=error,
            stdout=result.get("stdout", ""),
            stderr=result.get("stderr", ""),
            exit_code=result["exit_code"],
        )

    if not result["success"]:
        return tool_error(
            message=f"命令返回非零退出码: {result['exit_code']}",
            stdout=result.get("stdout", ""),
            stderr=result.get("stderr", ""),
            exit_code=result["exit_code"],
        )

    # Build response
    parts = []
    if result["exit_code"] != 0:
        parts.append(f"⚠️ 命令返回非零退出码: {result['exit_code']}")
    if result["stdout"]:
        parts.append(result["stdout"])
    if result["stderr"]:
        parts.append(f"--- stderr ---\n{result['stderr']}")

    output = "\n\n".join(parts) if parts else "（命令执行成功，无输出）"
    return tool_result(
        data=output,
        exit_code=result["exit_code"],
    )


def _handle_read_terminal(args: dict) -> str:
    """Handle read_terminal tool call — read recent terminal history."""
    count = int(args.get("count", 10))
    count = max(1, min(count, _MAX_HISTORY))

    with _history_lock:
        recent = list(_terminal_history)[-count:]

    return json.dumps({"entries": recent, "total": len(recent)}, ensure_ascii=False)


def _handle_close_terminal(args: dict) -> str:
    """Handle close_terminal tool call — kill running processes."""
    pid = args.get("pid")
    killed = []

    with _running_lock:
        if pid is not None:
            # Kill specific process
            procs = {pid: _running_procs.get(int(pid))} if int(pid) in _running_procs else {}
        else:
            # Kill all running processes
            procs = dict(_running_procs)

    for p, proc in procs.items():
        if proc and proc.poll() is None:
            try:
                _kill_process_tree(proc)
                killed.append(p)
            except Exception:
                pass
            _untrack_process(p)

    return json.dumps({"killed": killed, "count": len(killed)}, ensure_ascii=False)


# ── Schemas ─────────────────────────────────────────────────────────────

TERMINAL_SCHEMA = {
    "name": "terminal",
    "description": (
        "在本地终端中执行 shell 命令。可以运行 bash 脚本、安装包、执行程序等。"
        "注意：危险命令（如 rm -rf /、格式化磁盘、关机等）会被自动拒绝。"
        "请提供 description 说明执行目的，方便日志追踪。"
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "command": {
                "type": "string",
                "description": "要执行的 shell 命令",
            },
            "description": {
                "type": "string",
                "description": "执行此命令的目的说明（如「安装依赖」「编译项目」「查看日志」）",
            },
            "timeout": {
                "type": "integer",
                "description": "超时时间（秒），默认 120",
                "default": 120,
            },
            "workdir": {
                "type": "string",
                "description": "工作目录（默认当前目录）",
            },
        },
        "required": ["command"],
    },
}

READ_TERMINAL_SCHEMA = {
    "name": "read_terminal",
    "description": (
        "读取最近的终端命令执行历史。返回最近 N 条命令的输出结果。"
        "可用于查看之前执行的命令的完整输出。"
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "count": {
                "type": "integer",
                "description": "要读取的最近执行记录数量（1-50，默认 10）",
                "default": 10,
            },
        },
    },
}

CLOSE_TERMINAL_SCHEMA = {
    "name": "close_terminal",
    "description": (
        "终止正在运行的终端进程。不传 pid 则终止所有由 terminal 工具启动的进程。"
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "pid": {
                "type": "integer",
                "description": "要终止的进程 PID（不传则终止所有）",
            },
        },
    },
}

registry.register(
    name="terminal",
    toolset="terminal",
    schema=TERMINAL_SCHEMA,
    handler=_handle_terminal,
    emoji="💻",
    risk_level="high",
)

registry.register(
    name="read_terminal",
    toolset="terminal",
    schema=READ_TERMINAL_SCHEMA,
    handler=_handle_read_terminal,
    description="读取最近的终端命令执行历史",
    emoji="📜",
)

registry.register(
    name="close_terminal",
    toolset="terminal",
    schema=CLOSE_TERMINAL_SCHEMA,
    handler=_handle_close_terminal,
    description="终止正在运行的终端进程",
    emoji="⏹️",
    risk_level="medium",
)
