"""Memory management for ZLink Agent.

Stores conversation summaries and extracted key facts
for context injection in future conversations.
"""

import json
import logging
import os

from agent.utils import DATA_DIR, atomic_json_write

logger = logging.getLogger(__name__)

MEMORY_FILE = DATA_DIR / "memory" / "memory.json"
LOCK_FILE = MEMORY_FILE.with_suffix(MEMORY_FILE.suffix + ".lock")
MAX_SUMMARIES = 100

_fcntl = None
try:
    import fcntl as _fcntl_mod

    _fcntl = _fcntl_mod
except ImportError:
    pass


def _ensure_dirs():
    MEMORY_FILE.parent.mkdir(parents=True, exist_ok=True)


def _lock():
    """File lock context manager."""

    class _LockCtx:
        def __enter__(self):
            if _fcntl:
                self._fd = os.open(str(LOCK_FILE), os.O_CREAT | os.O_RDWR)
                _fcntl.flock(self._fd, _fcntl.LOCK_EX)
            return self

        def __exit__(self, *args):
            if hasattr(self, "_fd") and self._fd is not None and _fcntl:
                _fcntl.flock(self._fd, _fcntl.LOCK_UN)
                os.close(self._fd)
                self._fd = None

    return _LockCtx()


def _load() -> dict:
    _ensure_dirs()
    if not MEMORY_FILE.exists():
        return {"version": 1, "conversations": [], "facts": []}
    try:
        return json.loads(MEMORY_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {"version": 1, "conversations": [], "facts": []}


def _save(data: dict):
    _ensure_dirs()
    atomic_json_write(MEMORY_FILE, data)


def store_conversation_summary(session_id: str, title: str, messages: list[dict], summary: str | None = None):
    """Persist a conversation summary with file locking and eviction."""
    with _lock():
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

        # Evict oldest entries beyond the limit
        if len(memory["conversations"]) > MAX_SUMMARIES:
            excess = len(memory["conversations"]) - MAX_SUMMARIES
            memory["conversations"] = memory["conversations"][excess:]
            logger.info("Evicted %d oldest conversation summaries (limit=%d)", excess, MAX_SUMMARIES)

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
    parts.append("## 近期对话摘要（历史记录，不反映当前系统状态）")
    for conv in recent:
        parts.append(f"- {conv['title']}: {conv['summary'][:80]}")

    return "\n".join(parts)


def clear_all():
    """Wipe all stored memory."""
    with _lock():
        _save({"version": 1, "conversations": [], "facts": []})
