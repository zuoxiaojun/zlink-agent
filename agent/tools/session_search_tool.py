"""Session search tool — long-term conversation recall for the agent.

Lets the agent search past conversations by keyword, or browse recent sessions.
Uses SQLite FTS5 for fast full-text search (via search_index module).
Reference: Hermes Agent's session_search_tool + hermes_state FTS5 pattern.
"""

import json
import logging
from datetime import datetime

from agent import memory_manager, search_index
from agent.tools.registry import registry

logger = logging.getLogger(__name__)


def _format_time(iso_str: str) -> str:
    """Convert ISO timestamp to a short readable format."""
    if not iso_str:
        return "未知"
    try:
        dt = datetime.fromisoformat(iso_str)
        return dt.strftime("%m-%d %H:%M")
    except (ValueError, TypeError):
        return iso_str


def _handle_session_search(args: dict) -> str:
    """Search past conversations or list recent sessions via FTS5."""
    query = args.get("query", "").strip()
    limit = args.get("limit", 5)

    try:
        limit = max(1, min(int(limit), 10))
    except (TypeError, ValueError):
        limit = 5

    if not query:
        # Mode 1: recent sessions via FTS5 sessions table
        results = search_index.search("", limit)
        if not results:
            return json.dumps(
                {
                    "success": True,
                    "mode": "recent",
                    "results": [],
                    "count": 0,
                    "message": "暂无历史对话。",
                },
                ensure_ascii=False,
            )
        out = []
        for r in results:
            out.append(
                {
                    "session_id": r["session_id"],
                    "title": r.get("title", "新对话"),
                    "updated_at": _format_time(r.get("updated_at", "")),
                    "message_count": r.get("message_count", 0),
                }
            )
        return json.dumps(
            {
                "success": True,
                "mode": "recent",
                "results": out,
                "count": len(out),
                "message": f"最近 {len(out)} 条对话。使用关键词搜索可查找具体内容。",
            },
            ensure_ascii=False,
        )

    # Mode 2: keyword search via FTS5
    results = search_index.search(query, limit)
    if not results:
        return json.dumps(
            {
                "success": True,
                "mode": "search",
                "query": query,
                "results": [],
                "count": 0,
                "message": "未找到匹配的对话。",
            },
            ensure_ascii=False,
        )

    out = []
    for r in results:
        sid = r["session_id"]
        summary = memory_manager.get_session_summary(sid)
        out.append(
            {
                "session_id": sid,
                "title": r.get("title", "新对话"),
                "updated_at": _format_time(r.get("updated_at", "")),
                "message_count": r.get("message_count", 0),
                "summary": summary or "",
                "excerpt": r.get("excerpt", ""),
            }
        )

    return json.dumps(
        {
            "success": True,
            "mode": "search",
            "query": query,
            "results": out,
            "count": len(out),
            "message": f"找到 {len(out)} 条相关对话。",
        },
        ensure_ascii=False,
    )


SESSION_SEARCH_SCHEMA = {
    "name": "session_search",
    "description": (
        "搜索历史对话内容，或浏览最近会话。"
        "两种模式："
        "1. 最近会话（不传 query）：返回最近对话列表，零成本。"
        "2. 关键词搜索（传 query）：使用 FTS5 全文索引在所有历史对话中搜索，支持中文和英文。"
        "当用户提到之前聊过的事情、或者你需要回顾上下文时使用此工具。"
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "搜索关键词。不传此参数则返回最近会话列表。",
            },
            "limit": {
                "type": "integer",
                "description": "最多返回结果数（默认 5，最大 10）",
                "default": 5,
            },
        },
        "required": [],
    },
}

registry.register(
    name="session_search",
    toolset="session_search",
    schema=SESSION_SEARCH_SCHEMA,
    handler=_handle_session_search,
    emoji="🔍",
)
