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

import os
from pathlib import Path

from agent.session_context import ensure_current_artifacts_dir
from agent.tools.registry import registry

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


def install_session_artifact_hooks() -> None:
    """幂等安装 before-hook（T4 会补上 after-hook）。不读 registry 私有字段。"""
    global _installed
    if _installed:
        return
    registry.add_before_hook(artifact_before_hook)
    _installed = True


__all__ = [
    "MUTATING_TOOLS",
    "PATH_ARGS",
    "artifact_before_hook",
    "install_session_artifact_hooks",
    "is_within",
]
