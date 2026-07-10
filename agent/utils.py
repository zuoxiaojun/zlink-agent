"""Shared utility functions for YS-Agent."""

import json
import os
import tempfile
from pathlib import Path
from typing import Any

# ── Data directory 解析 ─────────────────────────────────────────────────────
# 唯一规则: YS_DATA_DIR 环境变量 > ~/.ys-agent/data/
# 不再做旧位置探测与迁移 —— v1.4.1 起项目只面向新用户,旧用户已通过 v1.4.0 完成升级。
DEFAULT_DATA_DIR = Path.home() / ".ys-agent" / "data"


def _resolve_data_dir() -> Path:
    env_dir = os.environ.get("YS_DATA_DIR")
    if env_dir:
        return Path(env_dir).expanduser().resolve()
    return DEFAULT_DATA_DIR


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
