"""Conversation session management for ZLink Agent.

Persists conversations to disk as JSON files and maintains a session index.
"""

import json
import logging
import re
import shutil
import uuid
from datetime import datetime
from pathlib import Path

from agent import search_index
from agent.utils import DATA_DIR, atomic_json_write

logger = logging.getLogger(__name__)

SESSIONS_DIR = DATA_DIR / "sessions"
INDEX_FILE = SESSIONS_DIR / "index.json"

# 会话 id 来自客户端（WS URL），必须挡住 ../ 之类的路径穿越。
_SAFE_ID_RE = re.compile(r"^[A-Za-z0-9_-]{1,64}$")


def is_valid_session_id(session_id: str) -> bool:
    return bool(session_id) and _SAFE_ID_RE.match(session_id) is not None


def session_dir(session_id: str) -> Path:
    """``data/sessions/<sid>/`` —— 一次会话的全部物理归属。"""
    return SESSIONS_DIR / session_id


def session_file(session_id: str) -> Path:
    return session_dir(session_id) / "session.json"


def artifacts_dir(session_id: str) -> Path:
    return session_dir(session_id) / "artifacts"


def ensure_artifacts_dir(session_id: str) -> Path:
    d = artifacts_dir(session_id)
    d.mkdir(parents=True, exist_ok=True)
    return d


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

    session_dir(session_id).mkdir(parents=True, exist_ok=True)
    ensure_artifacts_dir(session_id)
    atomic_json_write(
        session_file(session_id),
        {"id": session_id, "title": entry["title"], "messages": []},
    )
    return session_id


def _writable_session_file(session_id: str) -> Path | None:
    """会话消息文件路径。非法 id 返回 None（拒写盘）。"""
    if not is_valid_session_id(session_id):
        logger.warning("忽略非法 session_id，未写盘: %r", session_id)
        return None
    d = session_dir(session_id)
    if not d.exists():
        d.mkdir(parents=True, exist_ok=True)
        ensure_artifacts_dir(session_id)
    return session_file(session_id)


def save_session(session_id: str, messages: list[dict], title: str = ""):
    """Persist session messages and update index."""
    _ensure_dirs()
    if not session_id:
        return
    target = _writable_session_file(session_id)
    if target is None:
        return
    atomic_json_write(target, {"id": session_id, "title": title, "messages": messages})

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
    """Load messages for a session. Returns empty list if not found.

    先读目录版 ``<sid>/session.json``，回退旧的扁平 ``<sid>.json``（应对
    迁移被跳过、或用户手工塞回的备份文件）。
    """
    if not is_valid_session_id(session_id):
        return []
    for candidate in (session_file(session_id), SESSIONS_DIR / f"{session_id}.json"):
        if candidate.is_file():
            try:
                data = json.loads(candidate.read_text(encoding="utf-8"))
                return data.get("messages", [])
            except (json.JSONDecodeError, OSError):
                return []
    return []


def delete_session(session_id: str):
    """Remove session from index and wipe its directory (artifacts included)."""
    index = _load_index()
    index = [e for e in index if e["id"] != session_id]
    _save_index(index)

    if is_valid_session_id(session_id):
        try:
            shutil.rmtree(session_dir(session_id), ignore_errors=True)
            legacy = SESSIONS_DIR / f"{session_id}.json"
            if legacy.exists():
                legacy.unlink()
        except OSError as e:  # pragma: no cover - 权限/占用异常不阻断删除
            logger.warning("删除会话目录失败 %s: %s", session_id, e)

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


def migrate_session_layout() -> int:
    """一次性把扁平 ``<sid>.json`` 搬进 ``<sid>/session.json``。幂等。

    在 ``backend/main.py`` lifespan 里调用。单个会话失败只记日志，经不抛出
    —— 后端必须能在半成品布局下正常启动。返回实际处理条数。
    """
    _ensure_dirs()
    moved = 0
    for legacy in sorted(SESSIONS_DIR.glob("*.json")):
        sid = legacy.stem
        if sid == "index" or not is_valid_session_id(sid):
            if sid != "index":
                logger.warning("跳过非法会话文件名: %s", legacy.name)
            continue
        target_dir = session_dir(sid)
        try:
            target_dir.mkdir(parents=True, exist_ok=True)
            ensure_artifacts_dir(sid)
            if not legacy.exists():
                continue
            target = target_dir / "session.json"
            if target.exists():
                # 目录版已有数据 → 扁平文件是陈旧副本
                legacy.unlink()
            else:
                legacy.rename(target)
            moved += 1
        except OSError as e:
            logger.warning("会话布局迁移失败 %s: %s", sid, e)
    return moved
