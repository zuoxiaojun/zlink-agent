"""会话工作目录 —— 把文件/终端工具的相对路径归到本次会话的产物目录。

动机（见 spec §4.2）：写产物的相对路径今天落在后端进程 cwd（即源码仓库
根目录），是 ``/*.html`` gitignore 的根因；且产物没有会话归属，侧边栏无
从列起。

规则：

* 只改**相对**路径；绝对路径与 ``~`` 开头一律尊重用户/模型意图；
* 无会话上下文（单测、直接调工具、CLI）时完全不改 args —— 行为与改动前
  逐字一致；
* before-hook 只改写 args，**永不**返回 ``__block__``，不参与三层安全模型
  （注册顺序在 ``security_hooks`` 之后，先过安全再归一）。
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime
from pathlib import Path

from agent.session_context import ensure_current_artifacts_dir, get_current_session
from agent.tools.registry import registry

logger = logging.getLogger(__name__)

#: 工具名 → 承载路径的参数名。terminal 用 workdir，其余用 path。
PATH_ARGS: dict[str, str] = {
    "write_file": "path",
    "patch": "path",
    "read_file": "path",
    "ls": "path",
    "glob": "path",
    "search_files": "path",
    "terminal": "workdir",
}

#: 会写盘的工具（after-hook 登记 external.jsonl 时用）
MUTATING_TOOLS: frozenset[str] = frozenset({"write_file", "patch"})

#: 缺省即"当前目录"、需要替换成产物目录的工具
_DEFAULT_IS_CWD: frozenset[str] = frozenset({"ls", "glob", "search_files", "terminal"})


def is_within(path: Path | str, root: Path | str) -> bool:
    """*path* 解析后是否落在 *root* 子树内（含软链接解析后的真实路径）。"""
    try:
        return Path(path).resolve().is_relative_to(Path(root).resolve())
    except (OSError, ValueError):
        return False


def _should_skip(raw: object) -> bool:
    if not isinstance(raw, str):
        return True  # 非字符串 → 交给 handler 报错
    if raw.startswith("~"):
        return True  # 家目录展开：用户明确意图
    return os.path.isabs(os.path.expanduser(raw))


def artifact_before_hook(name: str, args: dict) -> dict:
    """registry before-hook：把相对路径改写成会话产物目录下的绝对路径。"""
    key = PATH_ARGS.get(name)
    if key is None:
        return args
    base = ensure_current_artifacts_dir()
    if base is None:
        return args  # 无会话上下文 → 行为不变

    raw = args.get(key)
    if raw is None or (isinstance(raw, str) and raw.strip() in ("", ".")):
        if name in _DEFAULT_IS_CWD:
            new = dict(args)
            new[key] = str(base)
            return new
        return args  # write_file/patch 空 path：让 handler 自己报错
    if _should_skip(raw):
        return args

    new = dict(args)
    new[key] = str(base / os.path.expanduser(raw))
    return new


_installed = False


EXTERNAL_FILENAME = "external.jsonl"


def record_external_write(session_id: str, abs_path: str, tool: str) -> None:
    """向 ``<sid>/external.jsonl`` 追加一行。

    单行 ``open("a")`` 写（POSIX 短追加原子），不引入锁、不碰
    ``session.json`` —— 避免与回合结束时 `chat.py` 的整份落盘抢写。
    """
    from agent import session_manager

    target = session_manager.session_dir(session_id) / EXTERNAL_FILENAME
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        line = json.dumps(
            {"path": abs_path, "tool": tool, "ts": datetime.now().isoformat()},
            ensure_ascii=False,
        )
        with open(target, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except OSError as e:  # pragma: no cover - 磁盘异常只记日志
        logger.warning("external.jsonl 写入失败 %s: %s", target, e)


def read_external_entries(session_id: str) -> list[dict]:
    """读 ``external.jsonl``：同 path 去重取最后一条，坏行跳过，按时间倒序。"""
    from agent import session_manager

    f = session_manager.session_dir(session_id) / EXTERNAL_FILENAME
    if not f.is_file():
        return []
    try:
        raw_lines = f.read_text(encoding="utf-8").splitlines()
    except OSError:
        return []
    by_path: dict[str, dict] = {}
    for line in raw_lines:
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(obj, dict):
            continue
        path = obj.get("path")
        if isinstance(path, str) and path:
            by_path[path] = {
                "path": path,
                "tool": str(obj.get("tool", "")),
                "ts": str(obj.get("ts", "")),
            }
    return sorted(by_path.values(), key=lambda e: e["ts"], reverse=True)


def artifact_after_hook(name: str, args: dict, result: str) -> str:
    """registry after-hook：写出落在会话目录外时登记一笔。

    只观察不改 result；入参 *args* 是 before-hook 改写后的（因此这里的
    path 已是绝对路径），与 ``security_hooks`` 的 before 链互不干扰。
    """
    if name not in MUTATING_TOOLS:
        return result
    sid = get_current_session()
    if not sid:
        return result
    try:
        payload = json.loads(result)
    except (json.JSONDecodeError, TypeError):
        return result
    if not isinstance(payload, dict) or not payload.get("success"):
        return result

    raw = args.get(PATH_ARGS[name])
    if not isinstance(raw, str) or not raw:
        return result
    base = ensure_current_artifacts_dir()
    if base is None:
        return result
    expanded = os.path.expanduser(raw)
    if is_within(expanded, base):
        return result

    record_external_write(sid, str(Path(expanded).resolve()), name)
    return result


def install_session_artifact_hooks() -> None:
    """幂等安装 before + after hook。不读 registry 私有字段。"""
    global _installed
    if _installed:
        return
    registry.add_before_hook(artifact_before_hook)
    registry.add_after_hook(artifact_after_hook)
    _installed = True


__all__ = [
    "EXTERNAL_FILENAME",
    "MUTATING_TOOLS",
    "PATH_ARGS",
    "artifact_after_hook",
    "artifact_before_hook",
    "install_session_artifact_hooks",
    "is_within",
    "read_external_entries",
    "record_external_write",
]
