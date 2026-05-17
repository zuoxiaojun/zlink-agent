"""Conversation session management for YS-Agent.

Persists conversations to disk as JSON files and maintains a session index.
"""

import json
import uuid
from datetime import datetime
from pathlib import Path

from agent.utils import atomic_json_write, DATA_DIR
from agent import search_index

SESSIONS_DIR = DATA_DIR / "sessions"
INDEX_FILE = SESSIONS_DIR / "index.json"


def _ensure_dirs():
    SESSIONS_DIR.mkdir(parents=True, exist_ok=True)


def _load_index() -> list[dict]:
    _ensure_dirs()
    if not INDEX_FILE.exists():
        return []
    try:
        return json.loads(INDEX_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return []


def _save_index(index: list[dict]):
    _ensure_dirs()
    atomic_json_write(INDEX_FILE, index)


def list_sessions() -> list[dict]:
    """Return sorted session list (newest first)."""
    sessions = _load_index()
    sessions.sort(key=lambda s: s.get("updated_at", ""), reverse=True)
    return sessions


def create_session(title: str = "") -> str:
    """Create a new session and return its ID."""
    session_id = uuid.uuid4().hex[:8]
    now = datetime.now().isoformat()
    entry = {
        "id": session_id,
        "title": title or "新对话",
        "created_at": now,
        "updated_at": now,
        "message_count": 0,
    }
    index = _load_index()
    index.append(entry)
    _save_index(index)

    session_file = SESSIONS_DIR / f"{session_id}.json"
    atomic_json_write(session_file, {"id": session_id, "title": entry["title"], "messages": []})
    return session_id


def save_session(session_id: str, messages: list[dict], title: str = ""):
    """Persist session messages and update index."""
    _ensure_dirs()
    if not session_id:
        return

    session_file = SESSIONS_DIR / f"{session_id}.json"
    atomic_json_write(session_file, {
        "id": session_id,
        "title": title,
        "messages": messages,
    })

    index = _load_index()
    for entry in index:
        if entry["id"] == session_id:
            entry["updated_at"] = datetime.now().isoformat()
            entry["message_count"] = len(messages)
            if title:
                entry["title"] = title
            break
    _save_index(index)

    search_index.index_session(session_id, messages, title)


def load_session(session_id: str) -> list[dict]:
    """Load messages for a session. Returns empty list if not found."""
    session_file = SESSIONS_DIR / f"{session_id}.json"
    if not session_file.exists():
        return []
    try:
        data = json.loads(session_file.read_text(encoding="utf-8"))
        return data.get("messages", [])
    except (json.JSONDecodeError, OSError):
        return []


def delete_session(session_id: str):
    """Remove a session from index and disk."""
    index = _load_index()
    index = [e for e in index if e["id"] != session_id]
    _save_index(index)

    session_file = SESSIONS_DIR / f"{session_id}.json"
    if session_file.exists():
        session_file.unlink()

    search_index.delete_session(session_id)



def auto_title(messages: list[dict]) -> str:
    """Generate a title from the first user message."""
    for m in messages:
        if m.get("role") == "user":
            content = m.get("content", "")
            if isinstance(content, str) and content.strip():
                text = content.strip().replace("\n", " ")
                return text[:28] + "…" if len(text) > 28 else text
    return "新对话"
