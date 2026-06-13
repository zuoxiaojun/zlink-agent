"""Shared utility functions for YS-Agent."""

import json
import os
import tempfile
from pathlib import Path
from typing import Any

# Project-local data directory (ys-agent project root / .ys-agent)
DATA_DIR = Path(__file__).resolve().parent.parent / "data"


def atomic_json_write(path: str | Path, data: Any, *, indent: int = 2) -> None:
    """Write JSON data to a file atomically.

    Uses temp file + os.replace to ensure the target file is never
    left in a partially-written state.
    """
    tmp_path = None
    try:
        fd, tmp_path = tempfile.mkstemp(suffix=".tmp", dir=Path(path).parent)
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=indent, ensure_ascii=False)
            f.flush()
            os.fsync(fd)
        os.replace(tmp_path, str(path))
        tmp_path = None
    finally:
        if tmp_path is not None:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
