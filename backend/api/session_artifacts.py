"""会话产物只读 API —— 列表 / 文件 / zip / 在 Finder 显示。

安全模型（spec §4.5）：不用 StaticFiles 挂载（那会把含 ERP 数据的
``session.json`` 暴露给本机任意页面），改为显式路由 + 单一校验入口
``_resolve_in_artifacts``，作用域严格限定在 ``<sessions>/<sid>/artifacts/``。
"""

from __future__ import annotations

import logging
import mimetypes
import os
import subprocess
import sys
import zipfile
from datetime import datetime
from io import BytesIO
from pathlib import Path
from urllib.parse import quote

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse, Response

from agent import session_manager
from agent.tools.session_artifact_hook import read_external_entries
from backend.schemas.session_artifact import (
    ArtifactItem,
    ArtifactListResponse,
    ExternalArtifact,
    RevealRequest,
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


def _quote_filename(name: str) -> str:
    return quote(name, safe="")


@router.get("/api/session-files/{sid}/{rel:path}")
def get_artifact_file(sid: str, rel: str, download: bool = Query(False)) -> FileResponse:
    """产物内容的唯一出口：iframe 预览与前端 fetch 文本共用。

    同源是这套设计成立的前提 —— 报告里的 ``src="chart.js"`` 顺同一前缀
    命中本端点。
    """
    _safe_sid(sid)
    target = _resolve_in_artifacts(sid, rel)
    if target is None:
        raise HTTPException(status_code=404, detail="artifact not found")

    media_type, _ = mimetypes.guess_type(target.name)
    media_type = media_type or "application/octet-stream"
    disposition = "attachment" if download else "inline"
    headers = {
        "Content-Disposition": f"{disposition}; filename*=UTF-8''{_quote_filename(target.name)}",
        "X-Content-Type-Options": "nosniff",
    }
    if media_type == "text/html":
        # 「在浏览器打开」时产物 JS 必须以独立源运行，否则它能 fetch /api/sessions
        # 拖走全部会话内容（后端无鉴权）。iframe 侧再叠一个 sandbox 属性。
        headers["Content-Security-Policy"] = "sandbox allow-scripts;"
    # filename=None 是有意为之：传 filename 会让 Starlette 自生成 Content-Disposition，
    # 覆盖上面要控制的 inline/attachment 语义。
    return FileResponse(path=str(target), media_type=media_type, headers=headers, filename=None)


@router.get("/api/sessions/{sid}/artifacts/zip")
def download_artifacts_zip(sid: str) -> Response:
    """把整个 artifacts/ 打包（保留相对目录结构、跳过软链接）。"""
    _require_session(sid)
    root = session_manager.ensure_artifacts_dir(sid)
    files = list(_iter_artifact_files(root))
    total = 0
    for p in files:
        try:
            total += p.stat().st_size
        except OSError:
            continue
    if total > MAX_ZIP_BYTES:
        raise HTTPException(status_code=413, detail="产物总体积超过打包上限")

    buf = BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for p in files:
            try:
                zf.write(p, arcname=p.relative_to(root).as_posix())
            except OSError:
                logger.warning("zip 跳过不可读产物: %s", p)
    name = f"session-{sid}-artifacts.zip"
    return Response(
        content=buf.getvalue(),
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{name}"'},
    )


def _reveal_in_file_manager(target: Path) -> None:
    """跨平台在文件管理器中定位（不 wait，失败只记日志）。"""
    if sys.platform == "darwin":
        cmd: list[str] = ["open", "-R", str(target)]
    elif os.name == "nt":  # pragma: no cover - 非 macOS/Linux
        cmd = ["explorer", f"/select,{target}"]
    else:  # pragma: no cover
        cmd = ["xdg-open", str(target.parent)]
    try:
        subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except OSError as e:  # pragma: no cover
        logger.warning("reveal 失败 %s: %s", target, e)


@router.post("/api/sessions/{sid}/artifacts/reveal")
def reveal_artifact(sid: str, body: RevealRequest) -> dict:
    """在系统文件管理器里定位产物。入参只能是会话内 rel 或已登记的 abs_path。"""
    _require_session(sid)
    if body.rel:
        target = _resolve_in_artifacts(sid, body.rel)
        if target is None:
            raise HTTPException(status_code=404, detail="artifact not found")
    elif body.abs_path:
        registered = {e["path"] for e in read_external_entries(sid)}
        candidate = os.path.realpath(os.path.expanduser(body.abs_path))
        if candidate not in {os.path.realpath(p) for p in registered}:
            raise HTTPException(status_code=403, detail="未登记的绝对路径不允许 reveal")
        if not os.path.isfile(candidate):
            raise HTTPException(status_code=404, detail="文件已不存在")
        target = Path(candidate)
    else:
        raise HTTPException(status_code=422, detail="需要 rel 或 abs_path")

    _reveal_in_file_manager(target)
    return {"success": True}
