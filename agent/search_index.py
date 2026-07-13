"""SQLite+FTS5 full-text search index for session recall.

Keeps a separate SQLite database alongside the existing JSON session files.
The JSON files remain the source of truth for session loading; this index
is write-only on save and read-only for search queries.
"""

import logging
import sqlite3
import threading
from datetime import datetime

from agent.utils import DATA_DIR

logger = logging.getLogger(__name__)

DB_PATH = DATA_DIR / "search_index.db"
_local = threading.local()
_all_connections: list[sqlite3.Connection] = []
_all_connections_lock = threading.Lock()


def _get_db() -> sqlite3.Connection:
    """Get thread-local database connection."""
    conn = getattr(_local, "conn", None)
    if conn is None:
        conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=OFF")
        conn.execute("PRAGMA busy_timeout=5000")
        _local.conn = conn
        with _all_connections_lock:
            _all_connections.append(conn)
    return conn


def close_all_connections():
    """Close all tracked database connections across threads. Used in tests."""
    with _all_connections_lock:
        for conn in _all_connections:
            try:
                conn.close()
            except Exception:
                pass
        _all_connections.clear()
    _local.conn = None


def init_db():
    """Create schema if not exists."""
    conn = _get_db()
    conn.execute("""CREATE TABLE IF NOT EXISTS sessions (
        id TEXT PRIMARY KEY,
        title TEXT,
        updated_at TEXT,
        message_count INTEGER DEFAULT 0
    )""")
    conn.execute("""CREATE TABLE IF NOT EXISTS messages (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        session_id TEXT NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
        role TEXT,
        content TEXT,
        msg_order INTEGER
    )""")
    conn.execute("""CREATE INDEX IF NOT EXISTS idx_messages_session
        ON messages(session_id)""")
    conn.execute("""CREATE VIRTUAL TABLE IF NOT EXISTS messages_fts
        USING fts5(content, session_id UNINDEXED, role UNINDEXED, tokenize='unicode61')""")
    conn.commit()


def _has_cjk(text: str) -> bool:
    """Check if text contains CJK characters."""
    for ch in text:
        if "一" <= ch <= "鿿" or "　" <= ch <= "〿" or "＀" <= ch <= "￯":
            return True
    return False


def _prepare_fts5_query(query: str) -> str:
    """Convert a user query into an FTS5-safe MATCH expression.

    For CJK queries, individual characters are joined with AND so that
    "工具" becomes "工 AND 具" — both characters must appear.
    For non-CJK, the query is used as-is with basic escaping.
    """
    query = query.strip().lower()
    if not query:
        return ""

    # Escape FTS5 special characters
    special = r"^" + "*" + "?" + "-" + "!" + "(" + ")" + "+" + "&" + "|" + "<" + ">" + "~" + "@"
    for ch in special:
        query = query.replace(ch, " ")

    query = " ".join(query.split())  # collapse whitespace

    if _has_cjk(query):
        # For CJK: join individual non-space characters with AND
        chars = [c for c in query if c.strip()]
        if len(chars) >= 3:
            # For 3+ chars, try phrase match first, then AND fallback
            return f'"{query}" OR {" AND ".join(chars)}'
        elif chars:
            return " AND ".join(chars)
        return query
    else:
        # For non-CJK: wrap space-separated terms with AND
        terms = query.split()
        if len(terms) > 1:
            return f"{' AND '.join(terms)}"
        return query


def index_session(session_id: str, messages: list[dict], title: str = ""):
    """Index a session's messages into the FTS5 search index.

    Called from session_manager.save_session(). Idempotent — re-indexes
    the entire session on each call.
    """
    try:
        conn = _get_db()
        init_db()

        # Upsert session metadata
        now = datetime.now().isoformat()
        conn.execute(
            """INSERT OR REPLACE INTO sessions (id, title, updated_at, message_count)
               VALUES (?, ?, ?, ?)""",
            (session_id, title, now, len(messages)),
        )

        # Delete old messages for this session
        conn.execute("DELETE FROM messages WHERE session_id = ?", (session_id,))
        conn.execute("DELETE FROM messages_fts WHERE session_id = ?", (session_id,))

        # Insert messages into both the messages table and FTS5
        cur = conn.cursor()
        for i, msg in enumerate(messages):
            role = msg.get("role", "")
            content = msg.get("content", "")
            if not isinstance(content, str) or not content:
                continue

            cur.execute(
                "INSERT INTO messages (session_id, role, content, msg_order) VALUES (?, ?, ?, ?)",
                (session_id, role, content, i),
            )
            cur.execute(
                "INSERT INTO messages_fts (rowid, content, session_id, role) VALUES (?, ?, ?, ?)",
                (cur.lastrowid, content, session_id, role),
            )

        conn.commit()
    except Exception as e:
        logger.warning("Search index write failed for session %s: %s", session_id, e)


def delete_session(session_id: str):
    """Remove a session from the search index."""
    try:
        conn = _get_db()
        conn.execute("DELETE FROM messages WHERE session_id = ?", (session_id,))
        conn.execute("DELETE FROM messages_fts WHERE session_id = ?", (session_id,))
        conn.execute("DELETE FROM sessions WHERE id = ?", (session_id,))
        conn.commit()
    except Exception as e:
        logger.warning("Search index delete failed for %s: %s", session_id, e)


def search(query: str, limit: int = 10) -> list[dict]:
    """Search session messages using FTS5.

    Returns list of dicts with keys: session_id, title, updated_at,
    message_count, role, excerpt.
    """
    if not query or not query.strip():
        # Recent sessions (no search)
        try:
            conn = _get_db()
            rows = conn.execute(
                "SELECT id, title, updated_at, message_count FROM sessions ORDER BY updated_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
            return [
                {
                    "session_id": r[0],
                    "title": r[1] or "",
                    "updated_at": r[2] or "",
                    "message_count": r[3] or 0,
                    "role": "",
                    "excerpt": "",
                }
                for r in rows
            ]
        except Exception as e:
            logger.warning("Search index query failed: %s", e)
            return []

    try:
        conn = _get_db()
        fts5_query = _prepare_fts5_query(query)
        if not fts5_query:
            return []

        rows = conn.execute(
            """SELECT DISTINCT m.session_id, s.title, s.updated_at, s.message_count,
                      m.role, substr(m.content, 1, 200)
               FROM messages_fts f
               JOIN messages m ON m.rowid = f.rowid
               LEFT JOIN sessions s ON s.id = m.session_id
               WHERE messages_fts MATCH ?
               ORDER BY rank
               LIMIT ?""",
            (fts5_query, limit * 2),  # fetch extra for dedup
        ).fetchall()

        # Deduplicate by session_id
        seen = set()
        results = []
        for r in rows:
            sid = r[0]
            if sid in seen:
                continue
            seen.add(sid)
            results.append(
                {
                    "session_id": sid,
                    "title": r[1] or "",
                    "updated_at": r[2] or "",
                    "message_count": r[3] or 0,
                    "role": r[4] or "",
                    "excerpt": r[5] or "",
                }
            )
            if len(results) >= limit:
                break

        # If FTS5 returned nothing and query has short CJK, fall back to LIKE
        if not results and _has_cjk(query) and len(query.strip()) <= 4:
            return _like_fallback(query, limit)

        return results

    except Exception as e:
        logger.warning("FTS5 search failed for %r: %s", query, e)
        # Fallback: use LIKE
        return _like_fallback(query, limit)


def _like_fallback(query: str, limit: int = 10) -> list[dict]:
    """Fallback search for short CJK queries that FTS5 trigram can't handle well."""
    try:
        conn = _get_db()
        like_pattern = f"%{query.strip()}%"
        rows = conn.execute(
            """SELECT DISTINCT m.session_id, s.title, s.updated_at, s.message_count,
                      m.role, substr(m.content, 1, 200)
               FROM messages m
               LEFT JOIN sessions s ON s.id = m.session_id
               WHERE m.content LIKE ?
               ORDER BY m.msg_order DESC
               LIMIT ?""",
            (like_pattern, limit),
        ).fetchall()

        seen = set()
        results = []
        for r in rows:
            sid = r[0]
            if sid in seen:
                continue
            seen.add(sid)
            results.append(
                {
                    "session_id": sid,
                    "title": r[1] or "",
                    "updated_at": r[2] or "",
                    "message_count": r[3] or 0,
                    "role": r[4] or "",
                    "excerpt": r[5] or "",
                }
            )
            if len(results) >= limit:
                break
        return results
    except Exception as e:
        logger.warning("LIKE fallback search failed: %s", e)
        return []


def migrate_from_json():
    """One-time migration: index all existing JSON session files."""
    from agent import session_manager

    sessions = session_manager.list_sessions()
    indexed = 0
    for s in sessions:
        sid = s["id"]
        title = s.get("title", "")
        messages = session_manager.load_session(sid)
        if messages:
            index_session(sid, messages, title)
            indexed += 1

    logger.info("Migration complete: indexed %d sessions", indexed)
    return indexed


def count_indexed() -> int:
    """Return count of indexed sessions."""
    try:
        conn = _get_db()
        row = conn.execute("SELECT COUNT(*) FROM sessions").fetchone()
        return row[0] if row else 0
    except Exception:
        return 0
