"""Fact-level persistent memory for the agent.

Two stores:
  - "memory": agent's personal notes (environment facts, conventions, lessons learned)
  - "user": what the agent knows about the user (preferences, habits, workflow)

Design (from Hermes Agent):
- Frozen snapshot pattern: captured at load_from_disk(), injected into system prompt.
  Mid-session writes update disk but do NOT change the snapshot, keeping the
  system prompt prefix cache stable. Refreshes on next session start.
- File locking for concurrent access safety.
- Atomic rename for write safety.
- Injection/exfiltration scanning on entry content.
"""

import json
import logging
import os
import re
from pathlib import Path

from agent.utils import DATA_DIR, atomic_json_write

logger = logging.getLogger(__name__)

MEMORY_FILE = DATA_DIR / "fact_memory.json"
ENTRY_DELIMITER = "\n§\n"
CHAR_LIMITS = {"memory": 2200, "user": 1375}

# Threat patterns for injection/exfiltration scanning (from Hermes skills_guard)
_THREAT_PATTERNS = [
    # ── Prompt injection ──
    (r"ignore\s+(?:\w+\s+)*(previous|all|above|prior)\s+instructions", "ignore_instructions"),
    (
        r"disregard\s+(?:\w+\s+)*(your|all|any)\s+(?:\w+\s+)*(instructions|rules|guidelines)",
        "disregard_rules",
    ),
    (r"system\s+prompt\s+override", "sys_prompt_override"),
    (r"you\s+are\s+(?:\w+\s+)*now\s+", "role_hijack"),
    (r"do\s+not\s+(?:\w+\s+)*tell\s+(?:\w+\s+)*the\s+user", "deception_hide"),
    (r"pretend\s+(?:\w+\s+)*(you\s+are|to\s+be)\s+", "role_pretend"),
    (r"output\s+(?:\w+\s+)*(system|initial)\s+prompt", "leak_system_prompt"),
    (
        r"(respond|answer|reply)\s+without\s+(?:\w+\s+)*(restrictions|limitations|filters|safety)",
        "remove_filters",
    ),
    (
        r"act\s+as\s+(if|though)\s+(?:\w+\s+)*you\s+(?:\w+\s+)*(have\s+no|don['’]t\s+have)\s+(?:\w+\s+)*(restrictions|limits|rules)",
        "bypass_restrictions",
    ),
    (r"you\s+have\s+been\s+(?:\w+\s+)*(updated|upgraded|patched)\s+to", "fake_update"),
    (r"new\s+policy|updated\s+guidelines|revised\s+instructions", "fake_policy"),
    (r"\bDAN\s+mode\b|Do\s+Anything\s+Now", "jailbreak_dan"),
    (r"\bdeveloper\s+mode\b.*\benabled?\b", "jailbreak_dev_mode"),
    (r"<!--[^>]*(?:ignore|override|system|secret|hidden)[^>]*-->", "html_comment_injection"),
    # ── Context exfiltration ──
    (r"(send|post|upload|transmit)\s+.*\s+(to|at)\s+https?://", "send_to_url"),
    (
        r"(include|output|print|send|share)\s+(?:\w+\s+)*(conversation|chat\s+history|previous\s+messages|context)",
        "context_exfil",
    ),
    # ── Credential exfiltration ──
    (r"cat\s+[^\n]*(\.env|credentials|\.netrc|\.pgpass|\.npmrc|\.pypirc)", "read_secrets"),
    (r"base64[^\n]*env", "encoded_exfil_env"),
    (r"os\.environ\b(?!\s*\.get\s*\(\s*[\"']PATH)", "python_os_environ"),
    (r"printenv|env\s*\|", "dump_all_env"),
    (r"authorized_keys", "ssh_backdoor"),
    (r"-----BEGIN\s+(RSA\s+)?PRIVATE\s+KEY-----", "embedded_private_key"),
    (r"sk-[A-Za-z0-9]{20,}", "openai_key_leaked"),
    (r"sk-ant-[A-Za-z0-9_-]{90,}", "anthropic_key_leaked"),
    (r"AKIA[0-9A-Z]{16}", "aws_access_key_leaked"),
    # ── Destructive ──
    (r"rm\s+-rf\s+/", "destructive_root_rm"),
    (r">\s*/etc/", "system_overwrite"),
    (r"\bmkfs\b", "format_filesystem"),
]


# ── Module-level singleton ─────────────────────────────────────────────

_store: "MemoryStore | None" = None


def get_store() -> "MemoryStore | None":
    return _store


def init_store() -> "MemoryStore":
    global _store
    _store = MemoryStore()
    _store.load_from_disk()
    return _store


# ── File lock helpers ─────────────────────────────────────────────────

_fcntl = None
try:
    import fcntl as _fcntl_mod

    _fcntl = _fcntl_mod
except ImportError:
    pass


def _acquire_lock(lock_path: Path):
    if _fcntl:
        fd = os.open(str(lock_path), os.O_CREAT | os.O_RDWR)
        _fcntl.flock(fd, _fcntl.LOCK_EX)
        return fd
    return None


def _release_lock(fd):
    if fd is not None and _fcntl:
        _fcntl.flock(fd, _fcntl.LOCK_UN)
        os.close(fd)


def _atomic_write(path: Path, content: str):
    """Write to a temp file and atomically rename into place."""
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(content, encoding="utf-8")
    tmp.replace(path)


# ── Scanner ────────────────────────────────────────────────────────────


def _scan_content(content: str) -> str | None:
    """Scan content for injection/exfil patterns. Returns error message or None."""
    for pattern, pid in _THREAT_PATTERNS:
        if re.search(pattern, content, re.IGNORECASE):
            return f"内容包含可疑模式「{pid}」。记忆内容会注入到系统提示中，禁止包含注入或泄露载荷。"
    return None


# ── MemoryStore ────────────────────────────────────────────────────────


class MemoryStore:
    """Bounded curated memory with file persistence.

    Parallel states:
      - _snapshot: frozen at load_from_disk() time, for system prompt. Never mutated.
      - entries: live state, mutated by tools, persisted to disk.
    """

    def __init__(self, memory_char_limit: int = 2200, user_char_limit: int = 1375):
        self.memory_entries: list[str] = []
        self.user_entries: list[str] = []
        self.memory_char_limit = memory_char_limit
        self.user_char_limit = user_char_limit
        self._snapshot: dict[str, str] = {"memory": "", "user": ""}

    # ── Load / Snapshot ───────────────────────────────────────

    def load_from_disk(self):
        """Load entries from disk, deduplicate, capture frozen snapshot."""
        raw = self._read_file()
        self.memory_entries = raw.get("memory", [])
        self.user_entries = raw.get("user", [])
        # Deduplicate (preserve order, keep first)
        self.memory_entries = list(dict.fromkeys(self.memory_entries))
        self.user_entries = list(dict.fromkeys(self.user_entries))
        # Capture frozen snapshot
        self._snapshot = {
            "memory": self._render_block("memory"),
            "user": self._render_block("user"),
        }

    def format_for_system_prompt(self, target: str) -> str | None:
        """Return the frozen snapshot. None if empty."""
        block = self._snapshot.get(target, "")
        return block if block else None

    # ── CRUD ──────────────────────────────────────────────────

    def list_entries(self, target: str) -> list[str]:
        """Return a shallow copy of entries for the given target."""
        return list(self._entries(target))

    def add(self, target: str, content: str) -> dict:
        content = content.strip()
        if not content:
            return {"success": False, "error": "内容不能为空。"}

        err = _scan_content(content)
        if err:
            return {"success": False, "error": err}

        with self._lock(target):
            self._reload(target)
            entries = self._entries(target)
            limit = self._limit(target)

            if content in entries:
                return self._ok(target, "条目已存在，未重复添加。")

            new_entries = entries + [content]
            new_total = len(ENTRY_DELIMITER.join(new_entries))
            if new_total > limit:
                current = self._char_count(target)
                return {
                    "success": False,
                    "error": (f"已达字符上限 ({current:,}/{limit:,})。请先移除不需要的条目。"),
                    "usage": f"{current:,}/{limit:,}",
                }

            entries.append(content)
            self._save(target)

        return self._ok(target, "条目已添加。")

    def replace(self, target: str, old_text: str, new_content: str) -> dict:
        old_text = old_text.strip()
        new_content = new_content.strip()
        if not old_text:
            return {"success": False, "error": "old_text 不能为空。"}
        if not new_content:
            return {"success": False, "error": "new_content 不能为空。"}

        err = _scan_content(new_content)
        if err:
            return {"success": False, "error": err}

        with self._lock(target):
            self._reload(target)
            entries = self._entries(target)
            matches = [(i, e) for i, e in enumerate(entries) if old_text in e]

            if not matches:
                return {"success": False, "error": f"未找到包含「{old_text}」的条目。"}
            if len(matches) > 1:
                unique = {e for _, e in matches}
                if len(unique) > 1:
                    previews = [e[:60] + ("…" if len(e) > 60 else "") for _, e in matches]
                    return {
                        "success": False,
                        "error": f"多个条目匹配「{old_text}」，请更精确。",
                        "matches": previews,
                    }

            idx = matches[0][0]
            test = entries.copy()
            test[idx] = new_content
            new_total = len(ENTRY_DELIMITER.join(test))
            if new_total > self._limit(target):
                return {
                    "success": False,
                    "error": "替换后超出字符上限，请精简内容。",
                }

            entries[idx] = new_content
            self._save(target)

        return self._ok(target, "条目已替换。")

    def remove(self, target: str, old_text: str) -> dict:
        old_text = old_text.strip()
        if not old_text:
            return {"success": False, "error": "old_text 不能为空。"}

        with self._lock(target):
            self._reload(target)
            entries = self._entries(target)
            matches = [(i, e) for i, e in enumerate(entries) if old_text in e]

            if not matches:
                return {"success": False, "error": f"未找到包含「{old_text}」的条目。"}
            if len(matches) > 1:
                unique = {e for _, e in matches}
                if len(unique) > 1:
                    previews = [e[:60] + ("…" if len(e) > 60 else "") for _, e in matches]
                    return {
                        "success": False,
                        "error": f"多个条目匹配「{old_text}」，请更精确。",
                        "matches": previews,
                    }

            idx = matches[0][0]
            entries.pop(idx)
            self._save(target)

        return self._ok(target, "条目已移除。")

    # ── Internal helpers ──────────────────────────────────────

    def _entries(self, target: str) -> list[str]:
        return self.user_entries if target == "user" else self.memory_entries

    def _limit(self, target: str) -> int:
        return self.user_char_limit if target == "user" else self.memory_char_limit

    def _char_count(self, target: str) -> int:
        entries = self._entries(target)
        return len(ENTRY_DELIMITER.join(entries)) if entries else 0

    def _render_block(self, target: str) -> str:
        entries = self._entries(target)
        if not entries:
            return ""
        label = "用户画像" if target == "user" else "持久记忆（Agent 笔记）"
        current = self._char_count(target)
        limit = self._limit(target)
        pct = min(100, int((current / limit) * 100)) if limit else 0
        header = f"## {label} [{pct}% — {current:,}/{limit:,} 字符]"
        return header + "\n" + "\n".join(f"- {e}" for e in entries)

    def _read_file(self) -> dict:
        if not MEMORY_FILE.exists():
            return {"memory": [], "user": []}
        try:
            data = json.loads(MEMORY_FILE.read_text(encoding="utf-8"))
            return {
                "memory": data.get("memory", []),
                "user": data.get("user", []),
            }
        except (json.JSONDecodeError, OSError):
            return {"memory": [], "user": []}

    def _write_file(self, data: dict):
        MEMORY_FILE.parent.mkdir(parents=True, exist_ok=True)
        atomic_json_write(MEMORY_FILE, data)

    def _lock(self, target: str):
        """Context manager for file-level locking."""
        lock_path = MEMORY_FILE.with_suffix(MEMORY_FILE.suffix + ".lock")
        return _FileLock(lock_path)

    def _reload(self, target: str):
        """Re-read entries from disk under lock."""
        raw = self._read_file()
        if target == "user":
            self.user_entries = list(dict.fromkeys(raw.get("user", [])))
        else:
            self.memory_entries = list(dict.fromkeys(raw.get("memory", [])))

    def _save(self, target: str):
        """Persist entries to disk (caller must hold lock)."""
        raw = self._read_file()
        raw[target] = self._entries(target)
        self._write_file(raw)

    def _ok(self, target: str, message: str) -> dict:
        entries = self._entries(target)
        current = self._char_count(target)
        limit = self._limit(target)
        pct = min(100, int((current / limit) * 100)) if limit else 0
        return {
            "success": True,
            "target": target,
            "entry_count": len(entries),
            "usage": f"{pct}% — {current:,}/{limit:,} 字符",
            "message": message,
        }


class _FileLock:
    """Simple file lock context manager."""

    def __init__(self, lock_path: Path):
        self.lock_path = lock_path
        self._fd = None

    def __enter__(self):
        if _fcntl:
            self.lock_path.parent.mkdir(parents=True, exist_ok=True)
            self._fd = os.open(str(self.lock_path), os.O_CREAT | os.O_RDWR)
            _fcntl.flock(self._fd, _fcntl.LOCK_EX)
        return self

    def __exit__(self, *args):
        if self._fd is not None and _fcntl:
            _fcntl.flock(self._fd, _fcntl.LOCK_UN)
            os.close(self._fd)
            self._fd = None
