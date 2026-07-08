"""Shared utility functions for YS-Agent."""

import json
import os
import sys
import tempfile
from pathlib import Path
from typing import Any

# ── Data directory 解析 (优先级从高到低) ──────────────────────────────────
# 1. YS_DATA_DIR 环境变量 (用户显式指定, 最高优先级)
# 2. .app 模式: 找 .app 旁边的 data/ (项目数据) > ~/YS-Agent/data/ > ~/.ys-agent/data/
# 3. 源码模式: <项目>/data/ (相对 utils.py 路径)
def _resolve_data_dir() -> Path:
    env_dir = os.environ.get("YS_DATA_DIR")
    if env_dir:
        return Path(env_dir)

    # .app 模式: sys.executable 是 <.app>/Contents/Resources/ys-agent
    if getattr(sys, "frozen", False):
        exe_dir = Path(sys.executable).resolve().parent  # Resources/
        # 从 Resources/ 往上找, 看 .app 外面有没有项目 data/
        # <project>/dist/YS-Agent.app/Contents/Resources/ys-agent
        #   ^       ^                              ^exe_dir
        #   project_root (4 个 ..)
        project_root = exe_dir.parent.parent.parent.parent
        candidates = [
            project_root / "data",                  # 源码项目 data/ (sibling of dist/)
            exe_dir / "data",                       # Resources/data/ (打包进来的, 通常没有)
            Path.home() / "YS-Agent" / "data",      # ~/YS-Agent/data (用户友好路径)
            Path.home() / ".ys-agent" / "data",     # ~/.ys-agent/data (默认)
        ]
        for c in candidates:
            if c.exists() and c.is_dir():
                return c
        # 都没找到, 创建设置默认
        default = Path.home() / ".ys-agent" / "data"
        default.mkdir(parents=True, exist_ok=True)
        return default

    # 源码模式: <项目>/data/
    return Path(__file__).resolve().parent.parent / "data"


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
