"""System management REST API — version check, update, migration.

Endpoints
---------
* ``GET  /api/system/version``         — 当前/最新版本信息
* ``POST /api/system/update``          — 触发升级（后台异步执行）
* ``GET  /api/system/update/status``   — 查看升级状态
* ``POST /api/system/migrate``         — 手动触发数据迁移
"""

from __future__ import annotations

import asyncio
import logging
import subprocess
import sys
import time
from pathlib import Path

from fastapi import APIRouter

logger = logging.getLogger(__name__)

router = APIRouter(tags=["system"])

# ── 项目根目录 ──────────────────────────────────────────────────────────────
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent

# ── 更新状态跟踪 ────────────────────────────────────────────────────────────
_update_task: asyncio.Task | None = None
_update_status: dict = {
    "running": False,
    "started_at": None,
    "finished_at": None,
    "success": None,
    "output": "",
    "error": "",
}


def _get_version() -> str:
    """读取版本号: 优先级 VERSION 文件 > pyproject.toml > unknown."""
    # 1. 优先读 VERSION 文件 (源码/frozen 都行)
    candidates = [_PROJECT_ROOT / "VERSION", Path(__file__).resolve().parent.parent.parent / "VERSION"]
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        candidates.append(Path(meipass) / "VERSION")
    for candidate in candidates:
        try:
            if candidate.exists():
                return candidate.read_text().strip()
        except Exception:
            pass
    # 2. 退化: 从 pyproject.toml 解析
    try:
        pyproject = _PROJECT_ROOT / "pyproject.toml"
        if pyproject.exists():
            for line in pyproject.read_text().splitlines():
                line = line.strip()
                if line.startswith("version"):
                    return line.split("=")[1].strip().strip('"').strip("'")
    except Exception:
        pass
    return "unknown"


def _get_git_info() -> dict:
    """获取 git 版本信息。"""
    info = {
        "commit": "unknown",
        "tag": "unknown",
        "branch": "unknown",
    }
    try:
        import subprocess

        info["commit"] = (
            subprocess.check_output(
                ["git", "rev-parse", "--short", "HEAD"],
                cwd=_PROJECT_ROOT,
                stderr=subprocess.DEVNULL,
                timeout=5,
            )
            .decode()
            .strip()
        )
        info["tag"] = (
            subprocess.check_output(
                ["git", "describe", "--tags", "--always"],
                cwd=_PROJECT_ROOT,
                stderr=subprocess.DEVNULL,
                timeout=5,
            )
            .decode()
            .strip()
        )
        info["branch"] = (
            subprocess.check_output(
                ["git", "rev-parse", "--abbrev-ref", "HEAD"],
                cwd=_PROJECT_ROOT,
                stderr=subprocess.DEVNULL,
                timeout=5,
            )
            .decode()
            .strip()
        )
    except Exception:
        pass
    return info


def _check_remote_version() -> dict:
    """检查远程是否有新版本。"""
    result = {"available": False, "latest_commit": "", "latest_tag": ""}
    try:
        # 获取远程最新 hash
        remote = (
            subprocess.check_output(
                ["git", "rev-parse", "--short", "@{upstream}"],
                cwd=_PROJECT_ROOT,
                stderr=subprocess.DEVNULL,
                timeout=5,
            )
            .decode()
            .strip()
        )
        current = _get_git_info()["commit"]
        result["latest_commit"] = remote
        result["available"] = remote != current and remote != "unknown"

        # 获取远程最新 tag
        try:
            result["latest_tag"] = (
                subprocess.check_output(
                    ["git", "describe", "--tags", "--always", "@{upstream}"],
                    cwd=_PROJECT_ROOT,
                    stderr=subprocess.DEVNULL,
                    timeout=5,
                )
                .decode()
                .strip()
            )
        except Exception:
            result["latest_tag"] = result["latest_commit"]
    except Exception:
        pass
    return result


async def _run_update():
    """后台执行 update.sh，更新 _update_status。"""
    global _update_status

    _update_status = {
        "running": True,
        "started_at": time.time(),
        "finished_at": None,
        "success": None,
        "output": "",
        "error": "",
    }

    script_path = _PROJECT_ROOT / "scripts" / "update.sh"
    try:
        proc = await asyncio.create_subprocess_exec(
            "bash",
            str(script_path),
            cwd=_PROJECT_ROOT,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()
        _update_status["output"] = stdout.decode("utf-8", errors="replace")
        _update_status["success"] = proc.returncode == 0
        if stderr:
            _update_status["error"] = stderr.decode("utf-8", errors="replace")
    except Exception as e:
        _update_status["success"] = False
        _update_status["error"] = str(e)
    finally:
        _update_status["running"] = False
        _update_status["finished_at"] = time.time()


# ── Endpoints ───────────────────────────────────────────────────────────────


@router.get("/api/system/version")
def version():
    """返回当前版本信息和远程更新状态。"""
    git = _get_git_info()
    remote = _check_remote_version()
    from scripts.migrate import SCHEMA_VERSION, _read_version

    data_schema = _read_version()

    return {
        "version": _get_version(),
        "git": git,
        "update_available": remote["available"],
        "latest_commit": remote["latest_commit"],
        "latest_tag": remote["latest_tag"],
        "data_schema_version": data_schema,
        "project_schema_version": SCHEMA_VERSION,
    }


@router.post("/api/system/update")
async def trigger_update():
    """触发后台升级。同一时间只能有一个升级任务运行。"""
    global _update_task

    if _update_status.get("running", False):
        from fastapi.responses import JSONResponse

        return JSONResponse(
            status_code=409,
            content={
                "error": "升级任务已在运行中",
                "started_at": _update_status["started_at"],
            },
        )

    # 先 fetch 最新信息
    try:
        subprocess.run(
            ["git", "fetch", "--tags", "--quiet"],
            cwd=_PROJECT_ROOT,
            timeout=30,
            stderr=subprocess.DEVNULL,
        )
    except Exception:
        pass

    _update_task = asyncio.create_task(_run_update())

    return {
        "message": "升级任务已启动，可通过 GET /api/system/update/status 查看进度",
        "started_at": time.time(),
    }


@router.get("/api/system/update/status")
def update_status():
    """查询升级任务的状态和结果。"""
    return {
        "running": _update_status.get("running", False),
        "started_at": _update_status.get("started_at"),
        "finished_at": _update_status.get("finished_at"),
        "success": _update_status.get("success"),
        "output": _update_status.get("output", ""),
        "error": _update_status.get("error", ""),
    }


@router.post("/api/system/migrate")
def run_migration():
    """手动触发数据迁移。"""
    from scripts.migrate import run_migrations

    try:
        count = run_migrations()
        return {"message": f"迁移完成，执行了 {count} 个迁移", "migrations_executed": count}
    except Exception as e:
        from fastapi.responses import JSONResponse

        logger.exception("手动迁移失败")
        return JSONResponse(
            status_code=500,
            content={"error": f"迁移失败: {str(e)}"},
        )
