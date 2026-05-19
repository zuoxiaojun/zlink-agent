"""File manipulation tools for YS-Agent.

Port of Hermes file_tools.py — simplified to direct filesystem operations.
"""

import fnmatch
import os
import re
import json
from pathlib import Path

from agent.tools.registry import registry, tool_result, tool_error

# Sensitive paths that tools should never write to
_DENY_PATHS = [
    "/etc", "/sys", "/proc", "/dev", "/boot",
    "/usr/lib", "/usr/bin", "/usr/sbin",
    "/System", "/Library",
]

_MAX_READ_CHARS = 100_000
_MAX_LS_ENTRIES = 500


def _expand_path(path: str) -> str:
    """Expand ~ and ~user in path before passing to Path."""
    # Path.resolve() does NOT expand ~, only os.path.expanduser does
    return os.path.expanduser(path)


def _is_safe_path(path: str) -> bool:
    """Check that the resolved path is not a sensitive system path."""
    try:
        resolved = Path(_expand_path(path)).resolve()
        for denied in _DENY_PATHS:
            if str(resolved).startswith(denied):
                return False
        return True
    except (OSError, ValueError):
        return False


def _handle_read_file(args: dict) -> str:
    path = _expand_path(args.get("path", ""))
    offset = int(args.get("offset", 1))
    limit = int(args.get("limit", 500))

    if not path:
        return tool_error("path is required")

    try:
        p = Path(path)
        if not p.exists():
            return tool_error(f"File not found: {path}")
        if not p.is_file():
            return tool_error(f"Not a file: {path}")

        content = p.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return tool_error("File is binary or not UTF-8 encoded")
    except (OSError, ValueError) as e:
        return tool_error(f"Cannot read file: {e}")

    lines = content.splitlines(keepends=True)
    total_lines = len(lines)

    if total_lines == 0:
        return tool_result(data="", total_lines=0, file_size=0)

    start = max(0, offset - 1)
    end = min(total_lines, start + limit)
    selected = "".join(lines[start:end])
    truncated = end < total_lines

    # Truncate content if too large
    if len(selected) > _MAX_READ_CHARS:
        selected = selected[:_MAX_READ_CHARS] + "\n... [truncated]"
        truncated = True

    return tool_result(
        data=selected,
        total_lines=total_lines,
        file_size=p.stat().st_size,
        truncated=truncated,
        hint=f"Showing lines {offset}-{end} of {total_lines}" if truncated else None,
    )


def _handle_write_file(args: dict) -> str:
    path = args.get("path", "")
    content = args.get("content", "")

    if not path:
        return tool_error("path is required")
    if not _is_safe_path(path):
        return tool_error(f"Cannot write to protected system path: {path}")

    try:
        p = Path(_expand_path(path))
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")
        return tool_result(data=f"Written {len(content)} chars to {p}")
    except (OSError, ValueError) as e:
        return tool_error(f"Cannot write file: {e}")


def _handle_patch(args: dict) -> str:
    path = args.get("path", "")
    old_string = args.get("old_string", "")
    new_string = args.get("new_string", "")
    replace_all = args.get("replace_all", False)
    edits = args.get("edits", None)

    if not path:
        return tool_error("path is required")

    if not _is_safe_path(path):
        return tool_error(f"Cannot modify protected system path: {path}")

    try:
        p = Path(_expand_path(path))
        if not p.exists():
            return tool_error(f"File not found: {path}")
        content = p.read_text(encoding="utf-8")
    except (OSError, ValueError) as e:
        return tool_error(f"Cannot read file: {e}")

    # --- multi-edit batching ---
    if edits:
        if not isinstance(edits, list):
            return tool_error("edits must be a list of {old_string, new_string} objects")
        applied = 0
        for i, edit in enumerate(edits):
            if not isinstance(edit, dict) or "old_string" not in edit or "new_string" not in edit:
                return tool_error(f"edit[{i}] missing old_string or new_string")
            old = edit["old_string"]
            new = edit["new_string"]
            if old not in content:
                return tool_error(
                    f"edit[{i}]: old_string not found in {path}",
                    hint="Check exact whitespace/indentation",
                )
            content = content.replace(old, new, 1)
            applied += 1
        try:
            p.write_text(content, encoding="utf-8")
            return tool_result(
                data=f"Applied {applied} edit(s) to {path}",
                applied=applied,
            )
        except (OSError, ValueError) as e:
            return tool_error(f"Cannot write file: {e}")

    # --- single-edit path ---
    if not old_string:
        return tool_error("old_string is required (or use edits for batch mode)")

    if old_string not in content:
        return tool_error(
            f"old_string not found in {path}",
            hint="Check exact whitespace/indentation",
        )

    if replace_all:
        new_content = content.replace(old_string, new_string)
    else:
        new_content = content.replace(old_string, new_string, 1)

    try:
        p.write_text(new_content, encoding="utf-8")
        return tool_result(
            data=f"Patched {path}",
            diff={
                "old_len": len(old_string),
                "new_len": len(new_string),
            },
        )
    except (OSError, ValueError) as e:
        return tool_error(f"Cannot write file: {e}")


def _handle_search_files(args: dict) -> str:
    pattern = args.get("pattern", "")
    search_path = args.get("path", ".")
    file_glob = args.get("file_glob", None)
    limit = int(args.get("limit", 50))
    context_lines = int(args.get("context_lines", 0))
    ignore_case = args.get("ignore_case", False)

    if not pattern:
        return tool_error("pattern is required")

    flags = re.IGNORECASE if ignore_case else 0
    try:
        compiled = re.compile(pattern, flags)
    except re.error as e:
        return tool_error(f"Invalid regex pattern: {e}")

    matches = []
    root = Path(_expand_path(search_path)).resolve()

    try:
        for fpath in root.rglob("*"):
            if not fpath.is_file():
                continue
            if file_glob and not fnmatch.fnmatch(fpath.name, file_glob):
                continue

            try:
                all_lines = fpath.read_text(encoding="utf-8").splitlines()
                for i, line in enumerate(all_lines):
                    if compiled.search(line):
                        ctx_before = all_lines[max(0, i - context_lines):i]
                        ctx_after = all_lines[i + 1:i + 1 + context_lines]
                        matches.append({
                            "path": str(fpath.relative_to(root)),
                            "line": i + 1,
                            "content": line.strip(),
                            "context_before": ctx_before if context_lines else None,
                            "context_after": ctx_after if context_lines else None,
                        })
                        if len(matches) >= limit:
                            break
            except (UnicodeDecodeError, OSError):
                continue

            if len(matches) >= limit:
                break
    except (OSError, ValueError) as e:
        return tool_error(f"Search failed: {e}")

    return tool_result(
        data=matches,
        total=len(matches),
        truncated=len(matches) >= limit,
    )


def _handle_ls(args: dict) -> str:
    path = _expand_path(args.get("path", "."))
    limit = int(args.get("limit", 200))

    try:
        p = Path(path).resolve()
        if not p.exists():
            return tool_error(f"Path not found: {path}")
        if not p.is_dir():
            return tool_error(f"Not a directory: {path}")
    except (OSError, ValueError) as e:
        return tool_error(f"Cannot access path: {e}")

    try:
        entries = sorted(p.iterdir(), key=lambda e: (not e.is_dir(), e.name.lower()))
    except (OSError, PermissionError) as e:
        return tool_error(f"Cannot list directory: {e}")

    result = []
    for entry in entries[:min(limit, _MAX_LS_ENTRIES)]:
        try:
            info = {
                "name": entry.name,
                "is_dir": entry.is_dir(),
                "size": entry.stat().st_size if entry.is_file() else 0,
            }
        except OSError:
            info = {"name": entry.name, "is_dir": False, "size": 0, "error": "stat failed"}
        result.append(info)

    truncated = len(entries) > limit
    return tool_result(
        data=result,
        total=len(entries),
        truncated=truncated,
    )


READ_FILE_SCHEMA = {
    "name": "read_file",
    "description": "Read the contents of a file. Supports line offset and limit for large files.",
    "parameters": {
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "Path to the file to read"},
            "offset": {"type": "integer", "description": "Starting line number (1-based)", "default": 1},
            "limit": {"type": "integer", "description": "Number of lines to read", "default": 500},
        },
        "required": ["path"],
    },
}

WRITE_FILE_SCHEMA = {
    "name": "write_file",
    "description": "Write content to a file. Creates parent directories if needed.",
    "parameters": {
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "Path to the file to write"},
            "content": {"type": "string", "description": "Content to write"},
        },
        "required": ["path", "content"],
    },
}

PATCH_SCHEMA = {
    "name": "patch",
    "description": (
        "Edit a file by replacing text. Supports two modes:\n"
        "- Single edit: provide old_string + new_string + optional replace_all\n"
        "- Batch edit: provide edits=[{old_string, new_string}, ...] for multiple changes in one call\n"
        "Use this instead of write_file for targeted changes."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "Path to the file to edit"},
            "old_string": {"type": "string", "description": "Text to replace (single-edit mode)"},
            "new_string": {"type": "string", "description": "Replacement text (single-edit mode)"},
            "replace_all": {"type": "boolean", "description": "Replace all occurrences", "default": False},
            "edits": {
                "type": "array",
                "description": "Batch: array of {old_string, new_string} objects applied in order",
                "items": {
                    "type": "object",
                    "properties": {
                        "old_string": {"type": "string", "description": "Text to replace"},
                        "new_string": {"type": "string", "description": "Replacement text"},
                    },
                    "required": ["old_string", "new_string"],
                },
            },
        },
        "required": ["path"],
    },
}

SEARCH_FILES_SCHEMA = {
    "name": "search_files",
    "description": "Search for a regex pattern in files with optional context lines. Supports file glob and case-insensitive search.",
    "parameters": {
        "type": "object",
        "properties": {
            "pattern": {"type": "string", "description": "Regex pattern to search for"},
            "path": {"type": "string", "description": "Directory to search in", "default": "."},
            "file_glob": {"type": "string", "description": "Optional file glob filter (e.g. '*.py')"},
            "context_lines": {"type": "integer", "description": "Lines of context around matches", "default": 0},
            "ignore_case": {"type": "boolean", "description": "Case-insensitive matching", "default": False},
            "limit": {"type": "integer", "description": "Max results", "default": 50},
        },
        "required": ["pattern"],
    },
}

LS_SCHEMA = {
    "name": "ls",
    "description": "List directory contents. Directories are listed first, sorted alphabetically.",
    "parameters": {
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "Directory to list", "default": "."},
            "limit": {"type": "integer", "description": "Max entries to return", "default": 200},
        },
        "required": [],
    },
}

registry.register(name="read_file", toolset="file", schema=READ_FILE_SCHEMA, handler=_handle_read_file, emoji="📖")
registry.register(name="write_file", toolset="file", schema=WRITE_FILE_SCHEMA, handler=_handle_write_file, emoji="✏️")
registry.register(name="patch", toolset="file", schema=PATCH_SCHEMA, handler=_handle_patch, emoji="🔧")
registry.register(name="search_files", toolset="file", schema=SEARCH_FILES_SCHEMA, handler=_handle_search_files, emoji="🔍")
registry.register(name="ls", toolset="file", schema=LS_SCHEMA, handler=_handle_ls, emoji="📂")
