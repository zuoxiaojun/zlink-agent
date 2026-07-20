"""Central registry for all ZLink Agent tools.

Each tool file calls ``registry.register()`` at module level to declare its
schema, handler, and toolset membership.  ``agent.py`` queries the registry
to build OpenAI-format tool definitions and dispatch tool calls.

Hooks
-----
Before-hooks run before a tool executes.  They receive ``(tool_name, args)``
and return modified args.  To block execution, return a dict with
``__block__: True`` and ``__reason__``.

After-hooks run after a tool executes.  They receive
``(tool_name, args, result)`` and return a (possibly modified) result string.
"""

import ast
import importlib
import json
import logging
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# Hook type aliases
BeforeHook = Callable[[str, dict], dict]
AfterHook = Callable[[str, dict, str], str]


def discover_tools(tools_dir: Path | None = None) -> list[str]:
    """Import self-registering tool modules and return their module names.

    In normal (source) mode, this scans the filesystem for ``.py`` files
    that contain a ``registry.register()`` call.  In PyInstaller frozen mode
    the files are compressed inside PYZ, so we use a known list of tool
    module names as fallback.
    """
    tools_path = tools_dir or Path(__file__).resolve().parent
    module_names: list[str] = []

    # ── PyInstaller frozen mode: use known tool list ──
    # sys.frozen is set by PyInstaller at runtime
    if getattr(sys, "frozen", False):
        known_tools = [
            "clarify_tool", "code_execution_tool",
            "cronjob_tools", "delegate_tool", "erp_nc_tools",
            "erp_ys_tools", "file_mutation_queue", "file_tools",
            "mcp_management_tool", "mcp_manager", "memory_tool",
            "process_tool", "project_tools", "security_hooks",
            "session_search_tool", "skills_tool", "terminal_tool",
            "todo_tool", "vision_tool", "web_extract_tool", "web_tools",
        ]
        module_names = [f"agent.tools.{name}" for name in known_tools]
    else:
        # ── Normal mode: scan filesystem ──
        for path in sorted(tools_path.glob("*.py")):
            if path.name in {"__init__.py", "registry.py"}:
                continue
            try:
                source = path.read_text(encoding="utf-8")
                tree = ast.parse(source, filename=str(path))
            except (OSError, SyntaxError):
                continue
            has_register = any(
                isinstance(stmt, ast.Expr)
                and isinstance(stmt.value, ast.Call)
                and isinstance(stmt.value.func, ast.Attribute)
                and stmt.value.func.attr == "register"
                and isinstance(stmt.value.func.value, ast.Name)
                and stmt.value.func.value.id == "registry"
                for stmt in tree.body
            )
            if has_register:
                module_names.append(f"agent.tools.{path.stem}")

    imported = []
    for mod_name in module_names:
        try:
            importlib.import_module(mod_name)
            imported.append(mod_name)
        except Exception as e:
            logger.warning("Could not import tool module %s: %s", mod_name, e)
    return imported


class ToolEntry:
    """Metadata for a single registered tool."""

    __slots__ = (
        "name",
        "toolset",
        "schema",
        "handler",
        "check_fn",
        "description",
        "emoji",
        "risk_level",
    )

    def __init__(
        self,
        name: str,
        toolset: str,
        schema: dict,
        handler: Callable,
        check_fn: Callable | None = None,
        description: str = "",
        emoji: str = "",
        risk_level: str = "low",
    ):
        self.name = name
        self.toolset = toolset
        self.schema = schema
        self.handler = handler
        self.check_fn = check_fn
        self.description = description
        self.emoji = emoji
        self.risk_level = risk_level


class ToolRegistry:
    """Singleton registry for tool definitions and handlers."""

    def __init__(self):
        self._entries: dict[str, ToolEntry] = {}
        self._before_hooks: list[BeforeHook] = []
        self._after_hooks: list[AfterHook] = []

    def register(
        self,
        name: str,
        toolset: str,
        schema: dict,
        handler: Callable,
        check_fn: Callable | None = None,
        description: str = "",
        emoji: str = "",
        risk_level: str = "low",
    ) -> None:
        """Register a tool."""
        self._entries[name] = ToolEntry(
            name=name,
            toolset=toolset,
            schema=schema,
            handler=handler,
            check_fn=check_fn,
            description=description,
            emoji=emoji,
            risk_level=risk_level,
        )

    def deregister(self, name: str) -> None:
        """Remove a tool from the registry."""
        self._entries.pop(name, None)

    def add_before_hook(self, hook: BeforeHook) -> None:
        """Register a before-tool-call hook.  Hooks run in registration order."""
        self._before_hooks.append(hook)

    def add_after_hook(self, hook: AfterHook) -> None:
        """Register an after-tool-call hook.  Hooks run in registration order."""
        self._after_hooks.append(hook)

    def remove_before_hook(self, hook: BeforeHook) -> None:
        """Remove a previously registered before-hook."""
        try:
            self._before_hooks.remove(hook)
        except ValueError:
            pass

    def remove_after_hook(self, hook: AfterHook) -> None:
        """Remove a previously registered after-hook."""
        try:
            self._after_hooks.remove(hook)
        except ValueError:
            pass

    def get_entry(self, name: str) -> ToolEntry | None:
        """Get a tool entry by name."""
        return self._entries.get(name)

    def get_all_tool_names(self) -> list[str]:
        """Return all registered tool names."""
        return list(self._entries.keys())

    def get_definitions(
        self,
        tool_names: list[str] | None = None,
        disabled_tools: set[str] | None = None,
    ) -> list[dict]:
        """Return OpenAI-format tool definitions.

        If *tool_names* is None, all registered tools are included.
        Tools in *disabled_tools* are excluded.
        """
        disabled = disabled_tools or set()
        definitions = []
        for name, entry in self._entries.items():
            if tool_names is not None and name not in tool_names:
                continue
            if name in disabled:
                continue
            if entry.check_fn is not None:
                try:
                    if not entry.check_fn():
                        continue
                except Exception:
                    continue
            definitions.append(
                {
                    "type": "function",
                    "function": entry.schema,
                }
            )
        return definitions

    def dispatch(self, name: str, args: dict) -> str:
        """Execute a tool by name with the given args. Returns JSON string.

        Before-hooks run first and may modify args or block execution.
        After-hooks run after the tool and may modify the result.
        """
        entry = self._entries.get(name)
        if entry is None:
            return tool_error(f"Unknown tool: {name}")

        # --- before hooks ---
        for hook in self._before_hooks:
            try:
                args = hook(name, args)
                if args.get("__block__"):
                    return tool_error(args.get("__reason__", "Blocked by hook"))
            except Exception as e:
                # Let ApprovalBlockedError propagate through
                if type(e).__name__ == "ApprovalBlockedError":
                    raise
                logger.warning("Before-hook failed for tool %s: %s", name, e)
                return tool_error(f"Hook blocked execution: {e}")

        # --- execute ---
        try:
            result = entry.handler(args)
            if not isinstance(result, str):
                result = json.dumps(result, ensure_ascii=False)
        except Exception as e:
            if type(e).__name__ == "ApprovalBlockedError":
                raise
            logger.exception("Tool %s failed", name)
            return tool_error(str(e))

        # --- after hooks ---
        for hook in self._after_hooks:
            try:
                result = hook(name, args, result)
            except Exception as e:
                logger.warning("After-hook failed for tool %s: %s", name, e)

        return result

    @property
    def entries(self) -> dict[str, ToolEntry]:
        return self._entries


# Module-level singleton
registry = ToolRegistry()


def tool_result(data: Any = None, **kwargs) -> str:
    """Return a successful tool result as JSON string."""
    payload = {"success": True}
    if data is not None:
        payload["data"] = data
    payload.update(kwargs)
    return json.dumps(payload, ensure_ascii=False)


def tool_error(message: str, **extra) -> str:
    """Return a failed tool result as JSON string."""
    payload = {"success": False, "error": message}
    payload.update(extra)
    return json.dumps(payload, ensure_ascii=False)
