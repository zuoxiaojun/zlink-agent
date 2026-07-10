"""ZLink Agent 数据迁移框架。

在升级代码后，如果数据格式发生变化，通过此模块安全地迁移用户数据。
所有迁移均向前兼容，可重复执行，且不会丢失数据。

实现方式：
  - 迁移版本号存储在 data/.schema_version 中
  - 每个迁移函数按版本号升序执行，已执行的版本跳过
  - 所有操作先备份后修改，保证可回滚

用法：
  python -m scripts.migrate            # 执行所有待处理的迁移
  python -m scripts.migrate --check    # 仅检查当前版本
  python -m scripts.migrate --version  # 显示项目期望的版本号
"""

from __future__ import annotations

import argparse
import logging
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("migrate")

# ── 项目当前期望的数据 schema 版本号 ────────────────────────────────────────
# 每次对数据存储格式有向后兼容但需要迁移的变更时，递增此值。
# 格式：整数，从 0 开始（0 表示初始版本，无迁移）。
SCHEMA_VERSION = 0

# ── 获取数据目录 ────────────────────────────────────────────────────────────
# 复用 agent.utils.DATA_DIR 的逻辑
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_DATA_DIR_ENV = __import__("os").environ.get("YS_DATA_DIR")
DATA_DIR = Path(_DATA_DIR_ENV) if _DATA_DIR_ENV else (_PROJECT_ROOT / "data")
VERSION_FILE = DATA_DIR / ".schema_version"


# ── 版本管理 ────────────────────────────────────────────────────────────────


def _read_version() -> int:
    """读取数据目录当前 schema 版本号。"""
    if not VERSION_FILE.exists():
        return 0
    try:
        return int(VERSION_FILE.read_text().strip())
    except (ValueError, OSError):
        return 0


def _write_version(version: int):
    """写入 schema 版本号。"""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    VERSION_FILE.write_text(str(version))


# ── 迁移注册表 ──────────────────────────────────────────────────────────────
# 每个迁移是一个 (版本号, 名称, 迁移函数) 元组。
# 版本号必须严格递增。
# 函数签名：def migrate(data_dir: Path) -> None


_MIGRATIONS: list[tuple[int, str, callable]] = []


def _register(version: int, name: str):
    """装饰器：注册一个迁移函数。"""

    def decorator(func: callable):
        _MIGRATIONS.append((version, name, func))
        return func

    return decorator


# ── 在这里添加后续迁移 ──────────────────────────────────────────────────────
# 示例：
#
# @_register(1, "将 config.json 的 api_key 字段迁移到新格式")
# def _migrate_v1(data_dir: Path):
#     import json
#     config_file = data_dir / "config.json"
#     if not config_file.exists():
#         return
#     # 先备份
#     backup = config_file.with_suffix(".json.bak.v1")
#     if not backup.exists():
#         import shutil
#         shutil.copy2(config_file, backup)
#         logger.info("已备份 config.json → config.json.bak.v1")
#     # 执行迁移
#     config = json.loads(config_file.read_text())
#     # ... 迁移逻辑 ...
#     atomic_json_write(config_file, config)
#     logger.info("config.json 迁移完成")


# ── 执行迁移 ────────────────────────────────────────────────────────────────


def run_migrations(dry_run: bool = False) -> int:
    """执行所有待处理的迁移，返回执行的迁移数。"""
    _MIGRATIONS.sort(key=lambda x: x[0])
    current = _read_version()
    executed = 0

    for version, name, func in _MIGRATIONS:
        if version > current and version <= SCHEMA_VERSION:
            if dry_run:
                logger.info("[DRY-RUN] 待执行迁移 v%s: %s", version, name)
                executed += 1
            else:
                logger.info("执行迁移 v%s: %s", version, name)
                try:
                    func(DATA_DIR)
                    _write_version(version)
                    logger.info("迁移 v%s 完成 ✅", version)
                    executed += 1
                except Exception:
                    logger.exception("迁移 v%s 失败 ❌", version)
                    raise

    if executed == 0:
        if dry_run:
            logger.info("没有待执行的迁移")
        else:
            logger.info("当前已是最新版本 v%s，无需迁移 ✅", current)

    return executed


# ── CLI ─────────────────────────────────────────────────────────────────────


def main():
    parser = argparse.ArgumentParser(description="ZLink Agent 数据迁移工具")
    parser.add_argument("--check", action="store_true", help="仅检查当前版本")
    parser.add_argument("--version", action="store_true", help="显示项目期望版本号")
    parser.add_argument("--dry-run", action="store_true", help="模拟运行，不实际修改")
    args = parser.parse_args()

    if args.version:
        print(SCHEMA_VERSION)
        return

    current = _read_version()
    if args.check:
        print(f"当前数据版本: v{current}")
        print(f"项目期望版本: v{SCHEMA_VERSION}")
        if current < SCHEMA_VERSION:
            pending = SCHEMA_VERSION - current
            print(f"待执行迁移: {pending} 个")
        else:
            print("已是最新版本 ✅")
        return

    run_migrations(dry_run=args.dry_run)


if __name__ == "__main__":
    main()
