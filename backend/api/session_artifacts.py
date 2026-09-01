"""会话产物只读 API —— 列表 / 文件 / zip / 在 Finder 显示。

安全模型（spec §4.5）：不用 StaticFiles 挂载（那会把含 ERP 数据的
``session.json`` 暴露给本机任意页面），改为显式路由 + 单一校验入口
``_resolve_in_artifacts``，作用域严格限定在 ``<sessions>/<sid>/artifacts/``。
"""

from __future__ import annotations

import logging
import os
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, HTTPException

from agent import session_manager
from agent.tools.session_artifact_hook import read_external_entries
from backend.schemas.session_artifact import (
    ArtifactItem,
    ArtifactListResponse,
    ExternalArtifact,
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["session-artifacts"])

MAX_LIST_ITEMS = 300
MAX_SCAN_DEPTH = 6
MAX_INLINE_BYTES = 5_000_000
MAX_ZIP_BYTES = 200_000_000

#: 永不可通过文件端点读出的名字（双保险，它们本就不在 artifacts/ 下）
_DENY_NAMES = frozenset({"session.json", "external.jsonl"})

KIND_BY_EXT: dict[str, str] = {
    ".html": "html",
    ".htm": "html",
    ".md": "md",
    ".markdown": "md",
    ".png": "image",
    ".jpg": "image",
    ".jpeg": "image",
    ".gif": "image",
    ".webp": "image",
    ".bmp": "image",
    ".svg": "image",
    ".pdf": "pdf",
    ".txt": "text",
    ".log": "text",
    ".json": "text",
    ".csv": "text",
    ".js": "text",
    ".ts": "text",
    ".py": "text",
    ".css": "text",
    ".xml": "text",
    ".yml": "text",
    ".yaml": "text",
    ".sql": "text",
}


def _kind_of(name: str) -> str:
    return KIND_BY_EXT.get(Path(name).suffix.lower(), "other")


def _safe_sid(sid: str) -> str:
    if not session_manager.is_valid_session_id(sid):
        raise HTTPException(status_code=404, detail="session not found")
    return sid


def _require_session(sid: str) -> str:
    _safe_sid(sid)
    if not session_manager.session_dir(sid).is_dir():
        raise HTTPException(status_code=404, detail="session not found")
    return sid


def _norm_rel(rel: str) -> list[str]:
    """反斜杠归一 + 分段，绝不接受 ``..``。返回空列表表示非法。"""
    unified = (rel or "").replace("\\", "/")
    if unified.startswith("/"):
        return []
    parts = [p for p in unified.split("/") if p not in ("", ".")]
    if not parts or any(p == ".." for p in parts):
        return []
    if parts[-1].lower() in _DENY_NAMES:
        return []
    return parts


def _resolve_in_artifacts(sid: str, rel: str) -> Path | None:
    """把 ``rel`` 解析成 ``<sid>/artifacts/`` 内的真实文件；非法/越界返回 None。"""
    if not session_manager.is_valid_session_id(sid):
        return None
    parts = _norm_rel(rel)
    if not parts:
        return None
    root = session_manager.artifacts_dir(sid)
    candidate = root.joinpath(*parts)
    try:
        resolved = candidate.resolve()
        resolved.relative_to(root.resolve())
    except (OSError, ValueError):
        return None  # 越界（含软链接逃逸）或无法解析
    if not resolved.is_file():
        return None
    return resolved


def _iter_artifact_files(root: Path):
    """深度受限的产物文件遍历（跳过软链接与不可读目录）。"""
    try:
        root_r = root.resolve()
    except OSError:  # pragma: no cover
        return
    for dirpath, dirnames, filenames in os.walk(root, topdown=True):
        base = Path(dirpath)
        try:
            depth = len(base.resolve().relative_to(root_r).parts)
        except ValueError:
            dirnames[:] = []
            continue
        if depth >= MAX_SCAN_DEPTH:
            dirnames[:] = []
        dirnames[:] = [d for d in dirnames if not (base / d).is_symlink()]
        for fn in filenames:
            p = base / fn
            if p.is_symlink():
                continue
            yield p


def _scan_artifacts(sid: str) -> tuple[list[ArtifactItem], bool]:
    root = session_manager.ensure_artifacts_dir(sid)
    items: list[ArtifactItem] = []
    truncated = False
    for p in _iter_artifact_files(root):
        try:
            st = p.stat()
        except OSError:
            continue
        items.append(
            ArtifactItem(
                name=p.name,
                rel=p.relative_to(root).as_posix(),
                size=st.st_size,
                mtime=datetime.fromtimestamp(st.st_mtime).isoformat(timespec="seconds"),
                kind=_kind_of(p.name),
            )
        )
        if len(items) >= MAX_LIST_ITEMS:
            truncated = True
            break
    items.sort(key=lambda i: i.mtime, reverse=True)
    return items, truncated


@router.get("/api/sessions/{sid}/artifacts", response_model=ArtifactListResponse)
def list_artifacts(sid: str) -> ArtifactListResponse:
    """列出本会话产物 + 已登记的会话外写出。"""
    _require_session(sid)
    items, truncated = _scan_artifacts(sid)
    external = [
        ExternalArtifact(
            abs_path=e["path"],
            tool=e["tool"],
            ts=e["ts"],
            exists=os.path.isfile(e["path"]),
        )
        for e in read_external_entries(sid)
    ]
    return ArtifactListResponse(
        items=items,
        external=external,
        count=len(items),
        truncated=truncated,
        root=f"/api/session-files/{sid}/",
    )
