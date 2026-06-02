"""Tool dispatch — run a tool through the registry, apply truncation.

Extracted from the inline ``registry.dispatch(...); truncate(...)`` block
in the original ``run_conversation``.

M1: 1:1 port.  M2 will add an event-publish around the dispatch so
extensions can cancel/modify the call.
"""
from __future__ import annotations

import json
from typing import Any

from agent.tools.registry import registry


def _truncate(content: Any, limit: int) -> str:
    if isinstance(content, str) and len(content) > limit:
        return content[:limit] + f"\n\n... (已截断 {len(content) - limit} 字符)"
    return content if isinstance(content, str) else str(content)


def dispatch_tool(
    name: str,
    args: dict,
    *,
    max_result_length: int = 5000,
    preview_length: int = 200,
) -> tuple[str, str]:
    """Execute *name* through the global registry.

    Returns ``(full_result, preview)`` — the full result is appended to
    the message list (possibly truncated), the preview is what we stream
    back to the client for display.

    Truncation is applied to the full result; the preview is then
    derived from the already-truncated full result so the user sees what
    the model actually sees.
    """
    result = registry.dispatch(name, args)
    if not isinstance(result, str):
        result = json.dumps(result, ensure_ascii=False)
    truncated = _truncate(result, max_result_length)
    preview = _truncate(truncated, preview_length)
    return truncated, preview


__all__ = ["dispatch_tool"]
