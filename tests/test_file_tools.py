"""Tests for the file manipulation tools (file_tools.py).

These tests exercise the private handler functions directly, using
``tmp_path`` for file isolation.  No network, no LLM, no MCP servers.
"""

from __future__ import annotations

import json
from pathlib import Path

from agent.tools.file_tools import (
    _handle_ls,
    _handle_patch,
    _handle_read_file,
    _handle_search_files,
    _handle_write_file,
    _is_safe_path,
)

# ────────────────────────────────────────────────────────────────────
# 1) _is_safe_path
# ────────────────────────────────────────────────────────────────────


def test_is_safe_path_allows_normal(tmp_path: Path):
    assert _is_safe_path(str(tmp_path)) is True


def test_is_safe_path_allows_tilde():
    with_tilde = "~/some_project"
    assert _is_safe_path(with_tilde) is True


def test_is_safe_path_blocks_system_library():
    """Paths under /Library should be blocked."""
    assert _is_safe_path("/Library/Preferences") is False


def test_is_safe_path_blocks_system_boot():
    assert _is_safe_path("/boot") is False


def test_is_safe_path_blocks_usr_bin():
    assert _is_safe_path("/usr/bin/sh") is False


def test_is_safe_path_blocks_usr_lib():
    assert _is_safe_path("/usr/lib/something.so") is False


def test_is_safe_path_blocks_sys():
    assert _is_safe_path("/sys/class") is False


def test_is_safe_path_blocks_proc():
    assert _is_safe_path("/proc/self") is False


def test_is_safe_path_blocks_dev():
    assert _is_safe_path("/dev/null") is False


# ────────────────────────────────────────────────────────────────────
# 2) _handle_read_file
# ────────────────────────────────────────────────────────────────────


def test_read_file_basic(tmp_path: Path):
    fp = tmp_path / "hello.txt"
    fp.write_text("hello world\nsecond line\nthird line\n")
    result = json.loads(_handle_read_file({"path": str(fp)}))
    assert result["success"] is True
    assert "hello world" in result["data"]
    assert result["total_lines"] == 3


def test_read_file_empty(tmp_path: Path):
    fp = tmp_path / "empty.txt"
    fp.write_text("")
    result = json.loads(_handle_read_file({"path": str(fp)}))
    assert result["success"] is True
    assert result["data"] == ""
    assert result["total_lines"] == 0


def test_read_file_with_offset_limit(tmp_path: Path):
    fp = tmp_path / "many_lines.txt"
    fp.write_text("\n".join(f"line {i}" for i in range(100)) + "\n")
    # Read lines 10-19 (offset=10, limit=10)
    result = json.loads(_handle_read_file({"path": str(fp), "offset": 10, "limit": 10}))
    assert result["success"] is True
    assert "line 9" in result["data"]  # 0-indexed: offset 10 → line index 9
    assert "line 18" in result["data"]
    assert result["truncated"] is True


def test_read_file_not_found(tmp_path: Path):
    result = json.loads(_handle_read_file({"path": str(tmp_path / "nope.txt")}))
    assert result["success"] is False
    assert "not found" in result["error"].lower()


def test_read_file_not_a_file(tmp_path: Path):
    result = json.loads(_handle_read_file({"path": str(tmp_path)}))
    assert result["success"] is False
    assert "not a file" in result["error"].lower()


def test_read_file_path_missing():
    result = json.loads(_handle_read_file({}))
    assert result["success"] is False
    assert "path is required" in result["error"]


def test_read_file_binary(tmp_path: Path):
    fp = tmp_path / "binary.bin"
    fp.write_bytes(b"\x00\x01\x02\xff")
    result = json.loads(_handle_read_file({"path": str(fp)}))
    assert result["success"] is False
    assert "binary" in result["error"].lower()


# ────────────────────────────────────────────────────────────────────
# 3) _handle_write_file
# ────────────────────────────────────────────────────────────────────


def test_write_file_creates_file(tmp_path: Path):
    fp = tmp_path / "out.txt"
    result = json.loads(_handle_write_file({"path": str(fp), "content": "hello from test"}))
    assert result["success"] is True
    assert "written" in result["data"].lower()
    assert fp.read_text() == "hello from test"


def test_write_file_creates_parent_dirs(tmp_path: Path):
    fp = tmp_path / "a" / "b" / "c" / "deep.txt"
    result = json.loads(_handle_write_file({"path": str(fp), "content": "deep"}))
    assert result["success"] is True
    assert fp.exists()
    assert fp.read_text() == "deep"


def test_write_file_path_missing():
    result = json.loads(_handle_write_file({"path": "", "content": "x"}))
    assert result["success"] is False
    assert "path is required" in result["error"]


def test_write_file_protected_path(tmp_path: Path):
    # /proc is a protected system path (blocked by _is_safe_path)
    result = json.loads(_handle_write_file({"path": "/proc/evil.conf", "content": "evil"}))
    assert result["success"] is False
    assert "protected system path" in result["error"].lower()


# ────────────────────────────────────────────────────────────────────
# 4) _handle_patch — single-edit mode
# ────────────────────────────────────────────────────────────────────


def test_patch_single_edit(tmp_path: Path):
    fp = tmp_path / "patch_me.txt"
    fp.write_text("hello old world")
    result = json.loads(_handle_patch({"path": str(fp), "old_string": "old", "new_string": "new"}))
    assert result["success"] is True
    assert "patched" in result["data"].lower()
    assert result["diff"]["old_len"] == 3
    assert result["diff"]["new_len"] == 3
    assert fp.read_text() == "hello new world"


def test_patch_path_missing():
    result = json.loads(_handle_patch({"old_string": "x", "new_string": "y"}))
    assert result["success"] is False
    assert "path is required" in result["error"]


def test_patch_file_not_found(tmp_path: Path):
    result = json.loads(_handle_patch({"path": str(tmp_path / "nope.txt"), "old_string": "x", "new_string": "y"}))
    assert result["success"] is False
    assert "not found" in result["error"].lower()


def test_patch_old_string_not_found(tmp_path: Path):
    fp = tmp_path / "content.txt"
    fp.write_text("some content")
    result = json.loads(_handle_patch({"path": str(fp), "old_string": "zzz", "new_string": "yyy"}))
    assert result["success"] is False
    assert "not found" in result["error"].lower()


def test_patch_requires_old_string(tmp_path: Path):
    fp = tmp_path / "content.txt"
    fp.write_text("content")
    result = json.loads(_handle_patch({"path": str(fp)}))
    assert result["success"] is False
    assert "old_string is required" in result["error"]


def test_patch_protected_path():
    result = json.loads(_handle_patch({"path": "/proc/test.txt", "old_string": "x", "new_string": "y"}))
    assert result["success"] is False
    assert "protected system path" in result["error"].lower()


def test_patch_replace_all(tmp_path: Path):
    fp = tmp_path / "replace_all.txt"
    fp.write_text("a a a a")
    result = json.loads(_handle_patch({"path": str(fp), "old_string": "a", "new_string": "b", "replace_all": True}))
    assert result["success"] is True
    assert fp.read_text() == "b b b b"


def test_patch_replace_once(tmp_path: Path):
    """With replace_all=False (default), only the first occurrence is replaced."""
    fp = tmp_path / "replace_once.txt"
    fp.write_text("a a a")
    result = json.loads(_handle_patch({"path": str(fp), "old_string": "a", "new_string": "b"}))
    assert result["success"] is True
    assert fp.read_text() == "b a a"


# ────────────────────────────────────────────────────────────────────
# 5) _handle_patch — batch-edit mode
# ────────────────────────────────────────────────────────────────────


def test_patch_batch_edits(tmp_path: Path):
    fp = tmp_path / "batch.txt"
    fp.write_text("foo bar baz")
    result = json.loads(
        _handle_patch(
            {
                "path": str(fp),
                "edits": [
                    {"old_string": "foo", "new_string": "FOO"},
                    {"old_string": "bar", "new_string": "BAR"},
                ],
            }
        )
    )
    assert result["success"] is True
    assert result["applied"] == 2
    assert fp.read_text() == "FOO BAR baz"


def test_patch_batch_not_list(tmp_path: Path):
    fp = tmp_path / "batch_err.txt"
    fp.write_text("content")
    result = json.loads(_handle_patch({"path": str(fp), "edits": "not_a_list"}))
    assert result["success"] is False
    assert "list" in result["error"].lower()


def test_patch_batch_missing_old_string(tmp_path: Path):
    fp = tmp_path / "batch_err2.txt"
    fp.write_text("content")
    result = json.loads(_handle_patch({"path": str(fp), "edits": [{"new_string": "y"}]}))
    assert result["success"] is False
    assert "missing old_string" in result["error"].lower()


def test_patch_batch_edit_not_found(tmp_path: Path):
    fp = tmp_path / "batch_err3.txt"
    fp.write_text("content")
    result = json.loads(
        _handle_patch(
            {
                "path": str(fp),
                "edits": [{"old_string": "zzz", "new_string": "yyy"}],
            }
        )
    )
    assert result["success"] is False
    assert "not found" in result["error"].lower()


# ────────────────────────────────────────────────────────────────────
# 6) _handle_search_files
# ────────────────────────────────────────────────────────────────────


def test_search_files_basic(tmp_path: Path):
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "main.py").write_text("def hello():\n    pass\n")
    (tmp_path / "src" / "util.py").write_text("def helper():\n    pass\n")

    result = json.loads(_handle_search_files({"pattern": "def ", "path": str(tmp_path)}))
    assert result["success"] is True
    assert result["total"] >= 2
    assert any("main.py" in m["path"] for m in result["data"])
    assert any("util.py" in m["path"] for m in result["data"])


def test_search_files_case_insensitive(tmp_path: Path):
    (tmp_path / "test.txt").write_text("Hello World\n")
    result = json.loads(_handle_search_files({"pattern": "hello", "path": str(tmp_path), "ignore_case": True}))
    assert result["success"] is True
    assert result["total"] >= 1


def test_search_files_case_sensitive(tmp_path: Path):
    (tmp_path / "test.txt").write_text("Hello World\n")
    result = json.loads(_handle_search_files({"pattern": "hello", "path": str(tmp_path), "ignore_case": False}))
    assert result["success"] is True
    assert result["total"] == 0


def test_search_files_file_glob(tmp_path: Path):
    (tmp_path / "data.py").write_text("x = 1")
    (tmp_path / "data.txt").write_text("x = 1")
    (tmp_path / "data.md").write_text("x = 1")
    result = json.loads(_handle_search_files({"pattern": "x = 1", "path": str(tmp_path), "file_glob": "*.py"}))
    assert result["success"] is True
    assert result["total"] == 1
    assert result["data"][0]["path"].endswith(".py")


def test_search_files_context_lines(tmp_path: Path):
    (tmp_path / "ctx.txt").write_text("before\ntarget\nafter\n")
    result = json.loads(_handle_search_files({"pattern": "target", "path": str(tmp_path), "context_lines": 1}))
    assert result["success"] is True
    assert result["total"] == 1
    match = result["data"][0]
    assert match["context_before"] == ["before"]
    assert match["context_after"] == ["after"]


def test_search_files_no_match(tmp_path: Path):
    (tmp_path / "nope.txt").write_text("nothing here")
    result = json.loads(_handle_search_files({"pattern": "zzzz", "path": str(tmp_path)}))
    assert result["success"] is True
    assert result["total"] == 0
    assert result["data"] == []


def test_search_files_empty_pattern():
    result = json.loads(_handle_search_files({"pattern": ""}))
    assert result["success"] is False
    assert "pattern is required" in result["error"]


def test_search_files_invalid_regex():
    result = json.loads(_handle_search_files({"pattern": "[invalid"}))
    assert result["success"] is False
    assert "invalid regex" in result["error"].lower()


def test_search_files_respects_limit(tmp_path: Path):
    (tmp_path / "a.txt").write_text("match\n")
    (tmp_path / "b.txt").write_text("match\n")
    (tmp_path / "c.txt").write_text("match\n")
    result = json.loads(_handle_search_files({"pattern": "match", "path": str(tmp_path), "limit": 2}))
    assert result["success"] is True
    assert result["total"] == 2
    assert result["truncated"] is True


# ────────────────────────────────────────────────────────────────────
# 7) _handle_ls
# ────────────────────────────────────────────────────────────────────


def test_ls_directory(tmp_path: Path):
    (tmp_path / "a.txt").write_text("a")
    (tmp_path / "b.txt").write_text("b")
    (tmp_path / "sub").mkdir()

    result = json.loads(_handle_ls({"path": str(tmp_path)}))
    assert result["success"] is True
    names = {e["name"] for e in result["data"]}
    assert "a.txt" in names
    assert "b.txt" in names
    assert "sub" in names
    assert result["total"] >= 3


def test_ls_directories_first(tmp_path: Path):
    (tmp_path / "a_file.txt").write_text("x")
    (tmp_path / "z_dir").mkdir()

    result = json.loads(_handle_ls({"path": str(tmp_path)}))
    assert result["success"] is True
    entries = [(e["is_dir"], e["name"]) for e in result["data"]]
    # Directories come first
    assert entries[0][0] is True  # first entry is a dir
    assert entries[0][1] == "z_dir"


def test_ls_path_not_found(tmp_path: Path):
    result = json.loads(_handle_ls({"path": str(tmp_path / "does_not_exist")}))
    assert result["success"] is False
    assert "not found" in result["error"].lower()


def test_ls_path_is_file_not_dir(tmp_path: Path):
    fp = tmp_path / "afile.txt"
    fp.write_text("x")
    result = json.loads(_handle_ls({"path": str(fp)}))
    assert result["success"] is False
    assert "not a directory" in result["error"].lower()


def test_ls_truncated(tmp_path: Path):
    for i in range(10):
        (tmp_path / f"file_{i}.txt").write_text("x")
    result = json.loads(_handle_ls({"path": str(tmp_path), "limit": 3}))
    assert result["success"] is True
    assert len(result["data"]) == 3
    assert result["truncated"] is True
