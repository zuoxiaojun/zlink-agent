"""打包版 node 可达性修复 —— 启动时把 node 补进 PATH。

为什么需要这个模块：从 Finder / Dock 启动的 macOS GUI 进程不读 ~/.zshrc，
也不读 /etc/paths.d。实测打包后 Electron 后端进程的环境里
PATH=/usr/bin:/bin:/usr/sbin:/sbin —— brew 装的 /opt/homebrew/bin/node 因此完全
不可见，terminal 里跑 "node xxx.js" 一律 exit 127。受影响的是四个依赖 node 脚本的
内置技能（china-hotdata / anysearch / minimax-pdf / pptx-generator）。dev 模式
（./start.sh 从登录 shell 起）PATH 正常，所以这个洞只在客户端里出现。

策略（本机优先，探不到落预置）：

1. PATH 里已经有 node → 什么都不做（dev 模式、以及自己配过 PATH 的用户）
2. 按候选目录探测真实 node → 探到就把「那个目录」前置进 PATH，连带 npm/npx 可用
3. 一个都没探到、但 Electron 注入了 ELECTRON_NODE_PATH → 在 DATA_DIR/bin 生成一个
   node shim（exec 那个二进制 + ELECTRON_RUN_AS_NODE=1）并把该目录前置进 PATH。
   用户没装 node 也能跑技能，只是没有 npm/npx

ELECTRON_RUN_AS_NODE=1 只在 shim 脚本内部设置，绝不写进本进程环境 —— 否则会污染
所有被 spawn 的 Electron 应用（它们会以为自己是纯 node，不再开界面）。
"""

from __future__ import annotations

import logging
import os
import stat
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from agent.utils import DATA_DIR

_logger = logging.getLogger("zlink.node_env")

_IS_WINDOWS = sys.platform == "win32"
_SHIM_NAME = "node.cmd" if _IS_WINDOWS else "node"

# 静态安装位置：真实 node 优先、常用安装在前
_STATIC_DIRS: tuple[str, ...] = (
    "/opt/homebrew/bin",  # Apple Silicon Homebrew
    "/usr/local/bin",  # Intel Homebrew / nodejs.org 安装包
    "/usr/bin",
    "/bin",
)

# 用户目录下的安装位置（相对 home）
_HOME_DIRS: tuple[str, ...] = (
    ".volta/bin",
    ".asdf/shims",
    ".mise/shims",
    ".pyenv/shims",
    "Library/pnpm",  # pnpm 自带 node 的常见落点（macOS）
    ".local/share/pnpm",
    ".local/share/pi-node/current/bin",  # pi 分发的 node
    ".local/bin",
)


def _version_key(name: str) -> tuple[int, ...]:
    """v22.9.0 -> (22, 9, 0)；解析不出来的排到最后（返回 (-1,)）。"""
    parts = name.lstrip("vV").split(".")
    out: list[int] = []
    for part in parts:
        digits = ""
        for ch in part:
            if not ch.isdigit():
                break
            digits += ch
        if not digits:
            return (-1,)
        out.append(int(digits))
    return tuple(out) if out else (-1,)


def candidate_dirs(home: Path | None = None) -> list[Path]:
    """按优先级返回可能装着 node 的目录，含版本管理器的解析结果。"""
    home = home or Path.home()
    dirs: list[Path] = [Path(p) for p in _STATIC_DIRS]

    if not _IS_WINDOWS:
        dirs.extend(home / rel for rel in _HOME_DIRS)

    # nvm / fnm 一个版本一个目录 —— 版本号最大的排前面
    for root, sub in (
        (home / ".nvm" / "versions" / "node", "bin"),
        (home / "Library" / "Application Support" / "fnm" / "node-versions", "installation/bin"),
        (home / ".local" / "share" / "fnm" / "node-versions", "installation/bin"),
    ):
        if not root.is_dir():
            continue
        try:
            vers = sorted((p for p in root.iterdir() if p.is_dir()), key=lambda p: _version_key(p.name), reverse=True)
        except OSError:
            continue
        dirs.extend(v / sub for v in vers)

    if _IS_WINDOWS:
        pf = Path(os.environ.get("ProgramFiles", r"C:\Program Files"))
        pf86 = Path(os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)"))
        appdata = Path(os.environ.get("APPDATA", str(home / "AppData" / "Roaming")))
        local = Path(os.environ.get("LOCALAPPDATA", str(home / "AppData" / "Local")))
        dirs.extend([pf / "nodejs", pf86 / "nodejs", appdata / "npm", local / "fnm", home / "scoop" / "shims"])

    return dirs


def find_node_in(dirs: Sequence[Path]) -> Path | None:
    """返回第一个真正可执行 node 的路径。"""
    name = "node.exe" if _IS_WINDOWS else "node"
    for d in dirs:
        cand = Path(d) / name
        try:
            if cand.is_file() and os.access(cand, os.X_OK):
                return cand
        except OSError:
            continue
    return None


def _prepend_path(directory: Path) -> None:
    parts = [p for p in os.environ.get("PATH", "").split(os.pathsep) if p]
    s = str(directory)
    os.environ["PATH"] = os.pathsep.join([s] + [p for p in parts if p != s])


def _shim_body(electron: str) -> str:
    """生成 shim 内容。路径里的引号转义掉（macOS 上 app 名带空格是常态）。"""
    esc = electron.replace('"', '\\"')
    if _IS_WINDOWS:
        lines = ["@echo off", "set ELECTRON_RUN_AS_NODE=1", f'"{esc}" %*']
        return "\r\n".join(lines) + "\r\n"
    lines = [
        "#!/bin/sh",
        "# zlink-agent 自动生成，每次启动重写 —— 用 Electron 自带的 Node 运行时",
        "export ELECTRON_RUN_AS_NODE=1",
        f'exec "{esc}" "$@"',
    ]
    return "\n".join(lines) + "\n"


def ensure_node_on_path(
    *,
    candidates: Sequence[Path] | None = None,
    electron_path: str | None = None,
    bin_dir: Path | None = None,
) -> dict[str, Any]:
    """确保子进程里 node 可用，返回一份诊断报告（写进 app.log 便于排查）。

    只在启动时调一次。candidates / electron_path / bin_dir 供单测注入。
    """
    report: dict[str, Any] = {"node": None, "source": None, "bin_dir": None}

    # 1) PATH 里本来就有 —— 不改任何东西
    existing = find_node_in([Path(p) for p in os.environ.get("PATH", "").split(os.pathsep) if p])
    if existing is not None:
        report.update(node=str(existing), source="path")
        return report

    # 2) 探测本机安装
    hit = find_node_in(list(candidates) if candidates is not None else candidate_dirs())
    if hit is not None:
        _prepend_path(hit.parent)
        report.update(node=str(hit), source="system", bin_dir=str(hit.parent))
        _logger.info("node 可达性：用本机 node %s（目录已前置进 PATH）", hit)
        return report

    # 3) 落包内预置的 Electron 运行时
    electron = electron_path if electron_path is not None else os.environ.get("ELECTRON_NODE_PATH", "")
    if electron and Path(electron).is_file():
        target = bin_dir or (DATA_DIR / "bin")
        try:
            target.mkdir(parents=True, exist_ok=True)
            if not _IS_WINDOWS:
                target.chmod(0o700)
            shim = target / _SHIM_NAME
            shim.write_text(_shim_body(electron), encoding="utf-8")
            shim.chmod(shim.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
            _prepend_path(target)
            report.update(node=str(shim), source="electron-shim", bin_dir=str(target))
            _logger.info("node 可达性：本机未装 node，改用包内 Electron 运行时 shim %s", shim)
        except OSError as exc:
            _logger.warning("node 可达性：生成 shim 失败，依赖 node 的内置技能会不可用：%s", exc)
            report["source"] = "none"
        return report

    _logger.warning("node 可达性：既没探到本机 node，也没有可用的 ELECTRON_NODE_PATH —— 依赖 node 的内置技能将不可用")
    report["source"] = "none"
    return report
