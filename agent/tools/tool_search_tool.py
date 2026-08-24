"""Tool search bridge tools — registered when tool_search is active.

Three bridge tools that replace deferred toolsets:
- tool_search: search available tools by keyword (BM25)
- tool_describe: get full schema for a tool
- tool_call: invoke a deferred tool
"""

from __future__ import annotations

import logging

from agent.tools.registry import registry, tool_error
from agent.tools.tool_search import (
    TOOL_CALL_NAME,
    TOOL_DESCRIBE_NAME,
    TOOL_SEARCH_NAME,
)

logger = logging.getLogger(__name__)

# These are registered at module-import time, but they are NOT added to the
# tool_defs list by default — they only appear when assemble_tool_defs()
# replaces deferred tools. The schemas live in tool_search.py's
# bridge_tool_schemas().

# We register them so the registry knows about them for dispatch purposes.
# The schemas here are minimal stubs — the real schemas are built dynamically
# in bridge_tool_schemas() with the correct deferred count.

_TOOL_SEARCH_STUB = {
    "name": TOOL_SEARCH_NAME,
    "description": "Search additional tools that are loaded on demand.",
    "parameters": {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "Keywords describing the capability you need."},
            "limit": {"type": "integer", "description": "Maximum results. Default 5, max 20."},
        },
        "required": ["query"],
    },
}

_TOOL_DESCRIBE_STUB = {
    "name": TOOL_DESCRIBE_NAME,
    "description": "Load the full JSON schema for a tool returned by tool_search.",
    "parameters": {
        "type": "object",
        "properties": {
            "name": {"type": "string", "description": "Exact tool name."},
        },
        "required": ["name"],
    },
}

_TOOL_CALL_STUB = {
    "name": TOOL_CALL_NAME,
    "description": "Invoke a deferred tool by name with the given arguments.",
    "parameters": {
        "type": "object",
        "properties": {
            "name": {"type": "string", "description": "Exact tool name to invoke."},
            "arguments": {"type": "object", "description": "Arguments for the tool."},
        },
        "required": ["name", "arguments"],
    },
}


def _unknown(**kwargs: object) -> str:
    """Placeholder — real dispatch happens in agent.py."""
    return tool_error("tool_search bridge not active")


registry.register(
    name=TOOL_SEARCH_NAME,
    toolset="tool_search",
    schema=_TOOL_SEARCH_STUB,
    handler=_unknown,
    emoji="🔍",
)
registry.register(
    name=TOOL_DESCRIBE_NAME,
    toolset="tool_search",
    schema=_TOOL_DESCRIBE_STUB,
    handler=_unknown,
    emoji="📖",
)
registry.register(
    name=TOOL_CALL_NAME,
    toolset="tool_search",
    schema=_TOOL_CALL_STUB,
    handler=_unknown,
    emoji="📞",
)
