"""Shared utility functions for ZLink Agent."""

import json
import os
import tempfile
from pathlib import Path
from typing import Any

# ── Data directory 解析 ─────────────────────────────────────────────────────
# v1.5.2 规则 (破坏式清理, 老用户数据目录已物理 rename):
# 1. ZLINK_DATA_DIR 环境变量
# 2. ~/.zlink-agent/data/ (默认)
DEFAULT_DATA_DIR = Path.home() / ".zlink-agent" / "data"


def _resolve_data_dir() -> Path:
    """v1.5.2: 解析运行时数据目录
    优先级: ZLINK_DATA_DIR > ~/.zlink-agent/data/
    """
    env = os.environ.get("ZLINK_DATA_DIR")
    if env:
        return Path(env).expanduser().resolve()
    new = Path.home() / ".zlink-agent" / "data"
    if new.exists():
        return new
    return new


DATA_DIR = _resolve_data_dir()
DATA_DIR.mkdir(parents=True, exist_ok=True)


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
