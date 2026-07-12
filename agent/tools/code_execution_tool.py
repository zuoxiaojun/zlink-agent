"""Code Execution Tool — sandboxed Python execution for data analysis.

Lets the LLM write and execute Python one-liners or scripts to perform
calculations, transform data, or generate charts inline. Runs in a restricted
environment with a 30-second timeout and no network/filesystem access.

Security: exec() runs in an isolated namespace with only safe builtins.
No import of os, subprocess, shutil, socket, ctypes, or similar.
"""

import json
import logging
import math
import statistics
import textwrap
import threading
from datetime import datetime, timedelta, timezone

from agent.tools.registry import registry

logger = logging.getLogger(__name__)

_SAFE_MODULES = {
    "json": json,
    "math": math,
    "statistics": statistics,
    "datetime": datetime,
    "timedelta": timedelta,
    "timezone": timezone,
}


def _safe_import(name: str, *args, **kwargs):
    """Restricted import: only allow explicitly listed safe modules."""
    if name in _SAFE_MODULES:
        return _SAFE_MODULES[name]
    raise ImportError(f"module '{name}' is not allowed in the sandbox. Allowed: {', '.join(_SAFE_MODULES)}")


_SAFE_BUILTINS = {
    "abs": abs,
    "all": all,
    "any": any,
    "bool": bool,
    "chr": chr,
    "complex": complex,
    "dict": dict,
    "divmod": divmod,
    "enumerate": enumerate,
    "filter": filter,
    "float": float,
    "format": format,
    "frozenset": frozenset,
    "hash": hash,
    "hex": hex,
    "id": id,
    "int": int,
    "isinstance": isinstance,
    "issubclass": issubclass,
    "iter": iter,
    "len": len,
    "list": list,
    "map": map,
    "max": max,
    "min": min,
    "next": next,
    "oct": oct,
    "ord": ord,
    "pow": pow,
    "print": print,
    "range": range,
    "repr": repr,
    "reversed": reversed,
    "round": round,
    "set": set,
    "slice": slice,
    "sorted": sorted,
    "str": str,
    "sum": sum,
    "tuple": tuple,
    "type": type,
    "zip": zip,
    "True": True,
    "False": False,
    "None": None,
    "math": math,
    "__import__": _safe_import,
}

# Additional safe modules for namespace
_SAFE_NAMESPACE = dict(_SAFE_MODULES)


def code_execution_tool(code: str, timeout: int = 30) -> str:
    """Execute Python code in a sandboxed environment and return the output.

    Args:
        code: Python code to execute (one-liner or multi-line script).
        timeout: Maximum execution time in seconds (default 30, max 60).

    Returns:
        JSON string with {"stdout": "...", "stderr": "..."} or error.
    """
    if not code or not code.strip():
        return json.dumps({"error": "code parameter is required"})

    timeout = min(max(timeout, 5), 60)  # clamp 5-60s

    # Dedent so indented code blocks work
    clean = textwrap.dedent(code.strip())

    # Build isolated namespace
    namespace = {
        "__builtins__": _SAFE_BUILTINS,
        **_SAFE_NAMESPACE,
    }

    stdout_lines: list[str] = []
    stderr_lines: list[str] = []

    # Capture print output
    def _captured_print(*args, **kwargs):
        sep = kwargs.get("sep", " ")
        end = kwargs.get("end", "\n")
        text = sep.join(str(a) for a in args)
        if end:
            text += end
        stdout_lines.append(text)

    namespace["print"] = _captured_print

    result = {"stdout": "", "stderr": ""}
    done_event = threading.Event()

    def run_code():
        try:
            # Try eval first (single expression)
            compiled = compile(clean, "<sandbox>", "eval")
            val = eval(compiled, namespace)
            if val is not None:
                stdout_lines.append(repr(val) + "\n")
        except SyntaxError:
            # Fall back to exec (statement)
            try:
                compiled = compile(clean, "<sandbox>", "exec")
                exec(compiled, namespace)
            except Exception as e:
                stderr_lines.append(f"{type(e).__name__}: {e}\n")
        except Exception as e:
            stderr_lines.append(f"{type(e).__name__}: {e}\n")
        finally:
            done_event.set()

    thread = threading.Thread(target=run_code, daemon=True)
    thread.start()
    thread.join(timeout=timeout)

    if thread.is_alive():
        stderr_lines.append(f"TimeoutError: execution exceeded {timeout}s\n")

    result["stdout"] = "".join(stdout_lines)
    result["stderr"] = "".join(stderr_lines)
    return json.dumps(result, ensure_ascii=False)


CODE_EXECUTION_SCHEMA = {
    "name": "execute_code",
    "description": (
        "Execute Python code for data analysis, calculations, or transformations. "
        "The environment has access to math, json, and standard Python builtins. "
        "NO network, filesystem, or subprocess access. "
        "Output is returned as JSON with 'stdout' and 'stderr' fields."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "code": {
                "type": "string",
                "description": (
                    "Python code to execute. Can be a one-liner or multi-line script. "
                    "Use print() to output results. Single expressions (e.g., '2+2') "
                    "are evaluated and their result is auto-printed."
                ),
            },
            "timeout": {
                "type": "integer",
                "description": "Max execution time in seconds (5-60, default 30).",
                "default": 30,
            },
        },
        "required": ["code"],
    },
}


registry.register(
    name="execute_code",
    toolset="code",
    schema=CODE_EXECUTION_SCHEMA,
    handler=lambda args, **kw: code_execution_tool(
        code=args.get("code", ""),
        timeout=args.get("timeout", 30),
    ),
    description="Execute Python code in a sandboxed environment for data analysis",
    emoji="💻",
    risk_level="medium",
)
