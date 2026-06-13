"""Terminal command execution tool.

Simplified from Hermes Agent's terminal_tool.py — local bash execution
with timeout and basic dangerous-command detection.
"""

import logging
import os
import re
import shutil
import signal
import subprocess

from agent.tools.registry import registry, tool_error, tool_result

logger = logging.getLogger(__name__)

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


def _find_bash() -> str:
    return shutil.which("bash") or shutil.which("sh") or "bash"


def _execute(command: str, timeout: int, workdir: str | None) -> dict:
    """Execute a shell command and return result dict."""
    # Check for dangerous patterns
    danger = _check_dangerous(command)
    if danger:
        return {
            "success": False,
            "error": f"命令被拒绝: {danger}。如需执行，请手动在终端中运行。",
            "stdout": "",
            "stderr": "",
            "exit_code": -1,
        }

    bash = _find_bash()
    cwd = workdir or os.getcwd()

    try:
        proc = subprocess.Popen(
            [bash, "-c", command],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=cwd,
            env=os.environ,
            preexec_fn=os.setsid,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
    except FileNotFoundError:
        return {
            "success": False,
            "error": f"Shell not found: {bash}",
            "stdout": "",
            "stderr": "",
            "exit_code": -1,
        }
    except Exception as e:
        return {
            "success": False,
            "error": f"Failed to start process: {e}",
            "stdout": "",
            "stderr": "",
            "exit_code": -1,
        }

    try:
        stdout, stderr = proc.communicate(timeout=timeout)
        exit_code = proc.returncode
    except subprocess.TimeoutExpired:
        # Kill the entire process tree
        try:
            os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
        except Exception:
            proc.kill()
        stdout, stderr = proc.communicate(timeout=5)
        return {
            "success": False,
            "error": f"命令执行超时（{timeout}秒）",
            "stdout": stdout[:MAX_OUTPUT_CHARS] if stdout else "",
            "stderr": stderr[:MAX_OUTPUT_CHARS] if stderr else "",
            "exit_code": -1,
        }
    except Exception as e:
        return {
            "success": False,
            "error": f"执行异常: {e}",
            "stdout": "",
            "stderr": "",
            "exit_code": -1,
        }

    # Truncate output
    if stdout and len(stdout) > MAX_OUTPUT_CHARS:
        stdout = stdout[:MAX_OUTPUT_CHARS] + f"\n\n...（已截断 {len(stdout) - MAX_OUTPUT_CHARS} 字符）"
    if stderr and len(stderr) > MAX_OUTPUT_CHARS:
        stderr = stderr[:MAX_OUTPUT_CHARS] + f"\n\n...（已截断 {len(stderr) - MAX_OUTPUT_CHARS} 字符）"

    return {
        "success": exit_code == 0,
        "stdout": stdout or "",
        "stderr": stderr or "",
        "exit_code": exit_code,
    }


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


# ── Schema ──────────────────────────────────────────────────────────────

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

registry.register(
    name="terminal",
    toolset="terminal",
    schema=TERMINAL_SCHEMA,
    handler=_handle_terminal,
    emoji="💻",
)
