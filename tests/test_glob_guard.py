"""Tests for the glob tool's filesystem-root guard.

A recursive ``**`` pattern anchored at a filesystem root (``/``, ``C:\\``)
or the user's home directory would walk the whole disk and hang for
minutes — the guard must refuse it up front, while normal subdirectory
globs keep working.  No network, no LLM, no MCP servers.
"""

from __future__ import annotations

import json
from pathlib import Path

from agent.tools.file_tools import _handle_glob, _is_root_scope

# ────────────────────────────────────────────────────────────────────
# 1) _is_root_scope — path classification
# ────────────────────────────────────────────────────────────────────


def test_is_root_scope_posix_root():
    assert _is_root_scope("/") is True


def test_is_root_scope_windows_drive_root():
    assert _is_root_scope("C:\\") is True
    assert _is_root_scope("C:/") is True


def test_is_root_scope_home_tilde():
    assert _is_root_scope("~") is True


def test_is_root_scope_explicit_home_path():
    assert _is_root_scope(str(Path.home())) is True


def test_is_root_scope_regular_subdir(tmp_path: Path):
    assert _is_root_scope(str(tmp_path)) is False


def test_is_root_scope_system_subdir():
    assert _is_root_scope("/usr") is False


# ────────────────────────────────────────────────────────────────────
# 2) _handle_glob — guard behaviour
# ────────────────────────────────────────────────────────────────────


def test_glob_rejects_root_path_with_recursive_pattern():
    result = json.loads(_handle_glob({"pattern": "**/xxx", "path": "/"}))
    assert result["success"] is False
    assert "路径范围过大" in result["error"]


def test_glob_rejects_home_with_recursive_pattern():
    result = json.loads(_handle_glob({"pattern": "**/*.py", "path": "~"}))
    assert result["success"] is False
    assert "路径范围过大" in result["error"]


def test_glob_rejects_explicit_home_path_with_recursive_pattern():
    result = json.loads(_handle_glob({"pattern": "**/*.py", "path": str(Path.home())}))
    assert result["success"] is False
    assert "路径范围过大" in result["error"]


def test_glob_allows_subdirectory_recursive_pattern(tmp_path: Path):
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "main.py").write_text("x = 1")
    result = json.loads(_handle_glob({"pattern": "**/*.py", "path": str(tmp_path)}))
    assert result["success"] is True
    assert any(m["path"].endswith("main.py") for m in result["data"])


def test_glob_allows_non_recursive_pattern(tmp_path: Path):
    (tmp_path / "notes.txt").write_text("x")
    result = json.loads(_handle_glob({"pattern": "*.txt", "path": str(tmp_path)}))
    assert result["success"] is True
    assert len(result["data"]) >= 1


def test_glob_recursive_pattern_on_subdir_not_blocked(tmp_path: Path):
    """The incident pattern (**/xxx) on a normal directory must still run."""
    result = json.loads(_handle_glob({"pattern": "**/xxx", "path": str(tmp_path)}))
    assert result["success"] is True
    assert result["data"] == []
