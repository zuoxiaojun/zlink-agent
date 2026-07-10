"""Shared utility functions for YS-Agent."""

import json
import os
import tempfile
from pathlib import Path
from typing import Any

# ── Data directory 解析 ─────────────────────────────────────────────────────
# v1.5.0 规则 (双兼容):
# 1. ZLINK_DATA_DIR / YS_DATA_DIR 环境变量 (后者兼容老用法)
# 2. ~/.zlink-agent/data/ (新默认)
# 3. ~/.ys-agent/data/ (兼容 v1.4.x, 自动 fallback)
# 4. 都不存在时返回 ~/.zlink-agent/data/ (新用户首次启动会创建)
DEFAULT_DATA_DIR = Path.home() / ".zlink-agent" / "data"


def _resolve_data_dir() -> Path:
    """v1.5.0: 解析运行时数据目录 (双兼容)
    优先级: ZLINK_DATA_DIR > YS_DATA_DIR > ~/.zlink-agent/data/ > ~/.ys-agent/data/ > ~/.zlink-agent/data/
    """
    env = os.environ.get("ZLINK_DATA_DIR") or os.environ.get("YS_DATA_DIR")
    if env:
        return Path(env).expanduser().resolve()
    new = Path.home() / ".zlink-agent" / "data"
    if new.exists():
        return new
    old = Path.home() / ".ys-agent" / "data"
    if old.exists():
        return old
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
