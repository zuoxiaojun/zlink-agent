"""Memory management for YS-Agent.

Stores conversation summaries and extracted key facts
for context injection in future conversations.
"""

from pathlib import Path

from agent.utils import atomic_json_write, DATA_DIR

MEMORY_FILE = DATA_DIR / "memory" / "memory.json"


def _ensure_dirs():
    MEMORY_FILE.parent.mkdir(parents=True, exist_ok=True)


def _load() -> dict:
    _ensure_dirs()
    if not MEMORY_FILE.exists():
        return {"version": 1, "conversations": [], "facts": []}
    try:
        import json
        return json.loads(MEMORY_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {"version": 1, "conversations": [], "facts": []}


def _save(data: dict):
    _ensure_dirs()
    atomic_json_write(MEMORY_FILE, data)


def store_conversation_summary(session_id: str, title: str, messages: list[dict], summary: str | None = None):
    """Persist a conversation summary. If summary is None, falls back to user message snippets."""
    memory = _load()

    if summary is None:
        user_msgs = [m for m in messages if m.get("role") == "user"]
        summary_parts = []
        for m in user_msgs[-5:]:
            content = m.get("content", "")
            if isinstance(content, str) and content:
                summary_parts.append(content[:100])
        summary = " | ".join(summary_parts) if summary_parts else title
    else:
        summary = summary[:200]

    entry = {
        "session_id": session_id,
        "title": title,
        "summary": summary,
    }

    for i, conv in enumerate(memory["conversations"]):
        if conv["session_id"] == session_id:
            memory["conversations"][i] = entry
            break
    else:
        memory["conversations"].append(entry)

    _save(memory)


def get_session_summary(session_id: str) -> str | None:
    """Return the summary for a given session_id, or None."""
    memory = _load()
    for conv in memory.get("conversations", []):
        if conv["session_id"] == session_id:
            return conv.get("summary")
    return None


def get_context() -> str:
    """Build a memory context string for prompt injection (conversation summaries only)."""
    memory = _load()
    if not memory.get("conversations"):
        return ""

    parts = []
    recent = memory["conversations"][-3:]
    parts.append("## 近期对话摘要")
    for conv in recent:
        parts.append(f"- {conv['title']}: {conv['summary'][:80]}")

    return "\n".join(parts)


def clear_all():
    """Wipe all stored memory."""
    _save({"version": 1, "conversations": [], "facts": []})
