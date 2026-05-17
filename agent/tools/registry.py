"""Central registry for all YS-Agent tools.

Each tool file calls ``registry.register()`` at module level to declare its
schema, handler, and toolset membership.  ``agent.py`` queries the registry
to build OpenAI-format tool definitions and dispatch tool calls.
"""

import ast
import importlib
import json
import logging
from pathlib import Path
from typing import Any, Callable

logger = logging.getLogger(__name__)


def discover_tools(tools_dir: Path | None = None) -> list[str]:
    """Import self-registering tool modules and return their module names."""
    tools_path = tools_dir or Path(__file__).resolve().parent
    module_names = []
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
        "name", "toolset", "schema", "handler", "check_fn", "description", "emoji",
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
    ):
        self.name = name
        self.toolset = toolset
        self.schema = schema
        self.handler = handler
        self.check_fn = check_fn
        self.description = description
        self.emoji = emoji


class ToolRegistry:
    """Singleton registry for tool definitions and handlers."""

    def __init__(self):
        self._entries: dict[str, ToolEntry] = {}

    def register(
        self,
        name: str,
        toolset: str,
        schema: dict,
        handler: Callable,
        check_fn: Callable | None = None,
        description: str = "",
        emoji: str = "",
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
        )

    def deregister(self, name: str) -> None:
        """Remove a tool from the registry."""
        self._entries.pop(name, None)

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
            definitions.append({
                "type": "function",
                "function": entry.schema,
            })
        return definitions

    def dispatch(self, name: str, args: dict) -> str:
        """Execute a tool by name with the given args. Returns JSON string."""
        entry = self._entries.get(name)
        if entry is None:
            return tool_error(f"Unknown tool: {name}")
        try:
            result = entry.handler(args)
            if isinstance(result, str):
                return result
            return json.dumps(result, ensure_ascii=False)
        except Exception as e:
            logger.exception("Tool %s failed", name)
            return tool_error(str(e))

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
