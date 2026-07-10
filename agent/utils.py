"""Shared utility functions for YS-Agent."""

import json
import logging
import os
import shutil
import sys
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any

# ── Data directory 解析 (v1.4.0: 统一路径) ──────────────────────────────────
# 唯一规则: YS_DATA_DIR 环境变量 > ~/.ys-agent/data/
# 不再有"项目 data/"或"~/YS-Agent/data/"等多级 fallback,源码与 .app 行为完全一致。
#
# 历史:
#   v1.3.3 之前: .app 强制走 ~/.ys-agent/data/,源码走 <项目>/data/,两边数据分散
#   v1.3.3:     5 级 fallback (YS_DATA_DIR > .app 旁边 data/ > Resources/data/ > ~/YS-Agent/data/ > ~/.ys-agent/data/)
#   v1.4.0:     砍到 2 级 (YS_DATA_DIR > ~/.ys-agent/data/),新位置为空时自动迁移一次
DEFAULT_DATA_DIR = Path.home() / ".ys-agent" / "data"


def _resolve_data_dir() -> Path:
    env_dir = os.environ.get("YS_DATA_DIR")
    if env_dir:
        return Path(env_dir).expanduser().resolve()
    return DEFAULT_DATA_DIR


DATA_DIR = _resolve_data_dir()
DATA_DIR.mkdir(parents=True, exist_ok=True)


# ── 一次性自动迁移 (v1.4.0+) ───────────────────────────────────────────────
# 仅当"新位置完全为空" + "旧位置有真实数据"时,自动复制。
# 检测到的旧位置(按优先级尝试,找到第一个有数据的就提示):
#   1. <项目根>/data/                          (源码模式旧行为)
#   2. ~/YS-Agent/data/                        (v1.3 早期 macOS 友好路径)
#   3. .app 旁边的项目 data/ (sibling of dist/) (v1.3.3 探测)
#
# 迁移规则(保守):
#   - 新位置无 config.json 也无 sessions/ → 自动复制旧位置
#   - 新位置有任一内容 → 跳过(不擅自覆盖),打印提示让用户用 `ys-agent migrate-data-path` 显式合并
#   - 迁移前把旧位置完整备份到新位置的 backups/migration-<timestamp>/
#   - 完成后写 .migrated 标记,避免重复
_LEGACY_DATA_CANDIDATES_ENV = "YS_AGENT_LEGACY_DATA_DIRS"


def _find_legacy_data_dirs() -> list[Path]:
    """列出所有可能存在旧数据的目录(不含新位置)。"""
    candidates: list[Path] = []

    env_extra = os.environ.get(_LEGACY_DATA_CANDIDATES_ENV)
    if env_extra:
        for p in env_extra.split(","):
            p = p.strip()
            if p:
                candidates.append(Path(p).expanduser().resolve())

    if not getattr(sys, "frozen", False):
        project_root = Path(__file__).resolve().parent.parent
        project_data = project_root / "data"
        if project_data.resolve() != DATA_DIR.resolve():
            candidates.append(project_data)

    candidates.append(Path.home() / "YS-Agent" / "data")

    if getattr(sys, "frozen", False):
        exe_dir = Path(sys.executable).resolve().parent
        project_root = exe_dir.parent.parent.parent.parent
        candidates.append(project_root / "data")

    # 去重 + 排除新位置
    seen: set[Path] = set()
    out: list[Path] = []
    for c in candidates:
        try:
            c = c.resolve()
        except OSError:
            continue
        if c in seen or c == DATA_DIR:
            continue
        seen.add(c)
        out.append(c)
    return out


def _has_real_data(d: Path) -> bool:
    """判断目录里是否有真实数据(config.json 或 sessions/ 视为强信号)。"""
    if not d.is_dir():
        return False
    if (d / "config.json").exists():
        return True
    if (d / "sessions").is_dir() and any((d / "sessions").iterdir()):
        return True
    if (d / "fact_memory.json").exists():
        return True
    return False


def _do_migrate(src: Path) -> Path:
    """执行迁移,返回备份目录路径。失败抛异常。"""
    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    backup_root = DATA_DIR / "backups" / f"migration-{ts}-from-{src.name}"
    backup_root.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(src, backup_root)

    for item in src.iterdir():
        target = DATA_DIR / item.name
        if item.is_dir():
            shutil.copytree(item, target)
        else:
            shutil.copy2(item, target)

    (DATA_DIR / ".migrated").write_text(
        f"migrated_from={src}\ntimestamp={ts}\nbackup={backup_root}\n",
        encoding="utf-8",
    )
    return backup_root


def _maybe_migrate_from_legacy() -> None:
    """首次启动时把旧位置的数据复制到新位置(仅当新位置完全为空)。"""
    logger = logging.getLogger(__name__)

    if (DATA_DIR / ".migrated").exists():
        return

    # 任何 config.json / sessions/ / fact_memory.json / memory/ 存在都视为"非空"
    new_has_data = (
        (DATA_DIR / "config.json").exists()
        or (DATA_DIR / "sessions").is_dir()
        or (DATA_DIR / "fact_memory.json").exists()
        or (DATA_DIR / "memory").is_dir()
    )

    for src in _find_legacy_data_dirs():
        if not _has_real_data(src):
            continue

        if new_has_data:
            # 新位置已有数据 → 不自动迁移,启动时由 backend/main.py 打印提示
            logger.info(
                "检测到旧数据目录 %s,但新数据目录 %s 已有内容,跳过自动迁移。"
                "如需合并,请运行 `ys-agent migrate-data-path`",
                src,
                DATA_DIR,
            )
            continue

        # 新位置为空 → 自动迁移
        try:
            backup = _do_migrate(src)
            logger.info(
                "已从旧位置自动迁移数据: %s → %s (备份: %s)",
                src,
                DATA_DIR,
                backup,
            )
        except Exception as e:
            logger.warning("从 %s 自动迁移失败: %s", src, e)
        return  # 只处理第一个有数据的旧位置


_maybe_migrate_from_legacy()


# ── 暴露给 CLI 的合并迁移 API ───────────────────────────────────────────────


def detect_legacy_data_dirs() -> list[Path]:
    """返回所有存在真实数据的旧位置。供 `ys-agent migrate-data-path` 使用。"""
    return [d for d in _find_legacy_data_dirs() if _has_real_data(d)]


def migrate_from(src: Path, *, merge: bool = False) -> Path:
    """从 src 迁移数据到 DATA_DIR。返回备份目录路径。

    merge=False (默认): 新位置必须为空,否则抛 FileExistsError。
    merge=True:          把 src 的内容追加到新位置(同名的 file/dir 不覆盖)。
    """
    src = src.resolve()
    if not _has_real_data(src):
        raise ValueError(f"{src} 不包含可迁移数据")

    if not merge:
        new_has_data = (
            (DATA_DIR / "config.json").exists()
            or (DATA_DIR / "sessions").is_dir()
            or (DATA_DIR / "fact_memory.json").exists()
            or (DATA_DIR / "memory").is_dir()
        )
        if new_has_data:
            raise FileExistsError(f"新数据目录 {DATA_DIR} 已有内容,设置 merge=True 以追加(同名词不覆盖)")

    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    backup_root = DATA_DIR / "backups" / f"migration-{ts}-from-{src.name}"
    backup_root.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(src, backup_root)

    for item in src.iterdir():
        target = DATA_DIR / item.name
        if target.exists():
            if merge:
                # merge 模式: 同名词不覆盖,搬去 backups/merge-skipped-<ts>/
                skipped_root = DATA_DIR / "backups" / f"merge-skipped-{ts}" / item.name
                if item.is_dir():
                    shutil.copytree(item, skipped_root)
                else:
                    shutil.copy2(item, skipped_root)
                continue
            else:
                # 非 merge 模式(理论上新位置为空,不会走到这里)
                raise FileExistsError(f"{target} 已存在")
        if item.is_dir():
            shutil.copytree(item, target)
        else:
            shutil.copy2(item, target)

    (DATA_DIR / ".migrated").write_text(
        f"migrated_from={src}\ntimestamp={ts}\nbackup={backup_root}\nmerge={merge}\n",
        encoding="utf-8",
    )
    return backup_root


def atomic_json_write(path: str | Path, data: Any, *, indent: int = 2) -> None:
    """Write JSON data to a file atomically."""
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
