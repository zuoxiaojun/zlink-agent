"""File manipulation tools for YS-Agent.

Port of Hermes file_tools.py — simplified to direct filesystem operations.
"""

import fnmatch
import os
import re
from pathlib import Path

from agent.tools.registry import registry, tool_result, tool_error

# Sensitive paths that tools should never write to
_DENY_PATHS = [
    "/etc", "/sys", "/proc", "/dev", "/boot",
    "/usr/lib", "/usr/bin", "/usr/sbin",
    "/System", "/Library",
]

_MAX_READ_CHARS = 100_000


def _is_safe_path(path: str) -> bool:
    """Check that the resolved path is not a sensitive system path."""
    try:
        resolved = Path(path).resolve()
        for denied in _DENY_PATHS:
            if str(resolved).startswith(denied):
                return False
        return True
    except (OSError, ValueError):
        return False


def _handle_read_file(args: dict) -> str:
    path = args.get("path", "")
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
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")
        return tool_result(data=f"Written {len(content)} chars to {path}")
    except (OSError, ValueError) as e:
        return tool_error(f"Cannot write file: {e}")


def _handle_patch(args: dict) -> str:
    mode = args.get("mode", "replace")
    path = args.get("path", "")
    old_string = args.get("old_string", "")
    new_string = args.get("new_string", "")
    replace_all = args.get("replace_all", False)

    if not path or not old_string:
        return tool_error("path and old_string are required")

    if not _is_safe_path(path):
        return tool_error(f"Cannot modify protected system path: {path}")

    try:
        p = Path(path)
        if not p.exists():
            return tool_error(f"File not found: {path}")

        content = p.read_text(encoding="utf-8")
    except (OSError, ValueError) as e:
        return tool_error(f"Cannot read file: {e}")

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

    if not pattern:
        return tool_error("pattern is required")

    matches = []
    root = Path(search_path).resolve()

    try:
        for fpath in root.rglob("*"):
            if not fpath.is_file():
                continue
            if file_glob and not fnmatch.fnmatch(fpath.name, file_glob):
                continue

            try:
                for i, line in enumerate(fpath.read_text(encoding="utf-8").splitlines(), 1):
                    if re.search(pattern, line):
                        matches.append({
                            "path": str(fpath.relative_to(root)),
                            "line": i,
                            "content": line.strip(),
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
    "description": "Replace text in an existing file. Use instead of write_file for small changes.",
    "parameters": {
        "type": "object",
        "properties": {
            "mode": {"type": "string", "enum": ["replace"], "default": "replace"},
            "path": {"type": "string", "description": "Path to the file to edit"},
            "old_string": {"type": "string", "description": "Text to replace"},
            "new_string": {"type": "string", "description": "Replacement text"},
            "replace_all": {"type": "boolean", "description": "Replace all occurrences", "default": False},
        },
        "required": ["path", "old_string", "new_string"],
    },
}

SEARCH_FILES_SCHEMA = {
    "name": "search_files",
    "description": "Search for a pattern in files. Supports regex and file glob filtering.",
    "parameters": {
        "type": "object",
        "properties": {
            "pattern": {"type": "string", "description": "Regex pattern to search for"},
            "path": {"type": "string", "description": "Directory to search in", "default": "."},
            "file_glob": {"type": "string", "description": "Optional file glob filter (e.g. '*.py')"},
            "limit": {"type": "integer", "description": "Max results", "default": 50},
        },
        "required": ["pattern"],
    },
}

registry.register(name="read_file", toolset="file", schema=READ_FILE_SCHEMA, handler=_handle_read_file, emoji="📖")
registry.register(name="write_file", toolset="file", schema=WRITE_FILE_SCHEMA, handler=_handle_write_file, emoji="✏️")
registry.register(name="patch", toolset="file", schema=PATCH_SCHEMA, handler=_handle_patch, emoji="🔧")
registry.register(name="search_files", toolset="file", schema=SEARCH_FILES_SCHEMA, handler=_handle_search_files, emoji="🔍")
