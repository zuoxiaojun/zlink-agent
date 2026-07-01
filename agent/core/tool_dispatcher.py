"""Tool dispatch — run a tool through the registry, apply truncation.

Extracted from the inline ``registry.dispatch(...); truncate(...)`` block
in the original ``run_conversation``.

M1: 1:1 port.  M2 will add an event-publish around the dispatch so
extensions can cancel/modify the call.
"""

from __future__ import annotations

import json
import sys
from typing import Any

from agent.tools.registry import registry


def _truncate(content: Any, limit: int) -> str:
    if isinstance(content, str) and len(content) > limit:
        return content[:limit] + "\n\n..."
    return content if isinstance(content, str) else str(content)


def dispatch_tool(
    name: str,
    args: dict,
    *,
    max_result_length: int = sys.maxsize,
    preview_length: int = 200,
) -> tuple[str, str]:
    """Execute *name* through the global registry.

    Returns ``(full_result, preview)`` — the full result is appended to
    the message list (possibly truncated at *max_result_length*), the
    preview is what we stream back to the client for display.

    Truncation is a safety net (preventing runaway data).  Use
    ``sys.maxsize`` to effectively disable it.
    """
    result = registry.dispatch(name, args)
    if not isinstance(result, str):
        result = json.dumps(result, ensure_ascii=False)
    truncated = _truncate(result, max_result_length)
    preview = _truncate(truncated, preview_length)
    return truncated, preview


__all__ = ["dispatch_tool"]
