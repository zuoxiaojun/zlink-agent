"""agent.node_env —— 打包版 node 可达性（补 PATH + Electron-as-node shim）。

背景：GUI 启动的进程 PATH 是最小集，/opt/homebrew/bin/node 看不见；依赖
"node xxx.js" 的内置技能（china-hotdata / anysearch / minimax-pdf /
pptx-generator）在客户端里一律 exit 127。
"""

import os
import subprocess
import sys
from pathlib import Path

import pytest

from agent import node_env


def _touch_exe(path: Path) -> Path:
    """造一个可执行的假 node（内容无关紧要，只看得到不存在、能不能执行）。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("#!/bin/sh\nexit 0\n")
    path.chmod(0o755)
    return path


def _path_head() -> str:
    return os.environ.get("PATH", "").split(os.pathsep)[0]


def test_node_already_on_path_changes_nothing(tmp_path, monkeypatch):
    real = _touch_exe(tmp_path / "keep" / "node")
    monkeypatch.setenv("PATH", str(real.parent))
    before = os.environ["PATH"]

    rep = node_env.ensure_node_on_path(candidates=[], electron_path="")

    assert rep["source"] == "path"
    assert rep["node"] == str(real)
    assert os.environ["PATH"] == before  # 不重复前置


def test_local_node_dir_is_prepended(tmp_path, monkeypatch):
    monkeypatch.setenv("PATH", str(tmp_path / "empty"))
    found = _touch_exe(tmp_path / "brew" / "bin" / "node")

    rep = node_env.ensure_node_on_path(candidates=[found.parent], electron_path="")

    assert rep["source"] == "system"
    assert rep["node"] == str(found)
    assert _path_head() == str(found.parent)


def test_candidates_take_priority_order(tmp_path, monkeypatch):
    """本机探测按候选顺序取第一个命中的，所以排在前面的目录赢。"""
    monkeypatch.setenv("PATH", str(tmp_path / "empty"))
    first = _touch_exe(tmp_path / "a" / "node")
    second = _touch_exe(tmp_path / "b" / "node")

    rep = node_env.ensure_node_on_path(candidates=[first.parent, second.parent], electron_path="")

    assert rep["node"] == str(first)


def test_falls_back_to_electron_shim(tmp_path, monkeypatch):
    monkeypatch.setenv("PATH", str(tmp_path / "empty"))
    # 路径带空格是 macOS app 的常态，shim 必须能扛住
    electron = _touch_exe(tmp_path / "ZLink Agent.app" / "Contents" / "MacOS" / "ZLink Agent")
    bin_dir = tmp_path / "data" / "bin"

    rep = node_env.ensure_node_on_path(candidates=[], electron_path=str(electron), bin_dir=bin_dir)

    shim = bin_dir / node_env._SHIM_NAME
    assert rep["source"] == "electron-shim"
    assert shim.is_file() and os.access(shim, os.X_OK)
    assert _path_head() == str(bin_dir)
    body = shim.read_text()
    assert "ELECTRON_RUN_AS_NODE=1" in body
    assert str(electron).replace('"', '\\"') in body


@pytest.mark.skipif(sys.platform == "win32", reason="shim 是 /bin/sh 脚本")
def test_shim_exports_run_as_node_and_forwards_args(tmp_path, monkeypatch):
    """shim 要真的把 ELECTRON_RUN_AS_NODE 设上、参数原样传下去 —— 否则 Electron 会再开一个 app 实例"""
    monkeypatch.setenv("PATH", str(tmp_path / "empty"))
    fake = tmp_path / "fake electron" / "ZLink Agent"
    fake.parent.mkdir(parents=True)
    fake.write_text('#!/bin/sh\necho "as=$ELECTRON_RUN_AS_NODE args=$*"\n')
    fake.chmod(0o755)
    bin_dir = tmp_path / "bin"

    node_env.ensure_node_on_path(candidates=[], electron_path=str(fake), bin_dir=bin_dir)
    out = subprocess.run([str(bin_dir / "node"), "-e", "1", "--x=1"], capture_output=True, text=True)

    assert out.stdout.strip() == "as=1 args=-e 1 --x=1"


@pytest.mark.skipif(sys.platform == "win32", reason="shim 是 /bin/sh 脚本")
def test_run_as_node_not_leaked_into_process_env(tmp_path, monkeypatch):
    """ELECTRON_RUN_AS_NODE 只能活在 shim 里 —— 泄进本进程环境会让被 spawn 的 Electron 应用不开界面"""
    monkeypatch.delenv("ELECTRON_RUN_AS_NODE", raising=False)
    monkeypatch.setenv("PATH", str(tmp_path / "empty"))
    electron = _touch_exe(tmp_path / "App" / "MacOS" / "ZLink Agent")

    node_env.ensure_node_on_path(candidates=[], electron_path=str(electron), bin_dir=tmp_path / "bin")

    assert "ELECTRON_RUN_AS_NODE" not in os.environ


def test_shim_rewritten_every_start(tmp_path, monkeypatch):
    """app 被移动 / 升级后旧路径失效，所以每次启动都重写，不能 setdefault"""
    monkeypatch.setenv("PATH", str(tmp_path / "empty"))
    old = _touch_exe(tmp_path / "old" / "ZLink Agent")
    new = _touch_exe(tmp_path / "new" / "ZLink Agent")
    bin_dir = tmp_path / "bin"

    node_env.ensure_node_on_path(candidates=[], electron_path=str(old), bin_dir=bin_dir)
    # 第二次调用模拟「下一次进程启动」：PATH 回到最小集，否则第一步就会命中
    # 「PATH 里已有 node」而直接早退（那正是期望行为，见上面的 no-op 用例）
    monkeypatch.setenv("PATH", str(tmp_path / "empty"))
    node_env.ensure_node_on_path(candidates=[], electron_path=str(new), bin_dir=bin_dir)

    body = (bin_dir / node_env._SHIM_NAME).read_text()
    assert str(new) in body and str(old) not in body


def test_no_node_and_no_electron_reports_none(tmp_path, monkeypatch):
    monkeypatch.setenv("PATH", str(tmp_path / "empty"))
    monkeypatch.delenv("ELECTRON_NODE_PATH", raising=False)
    before = os.environ["PATH"]

    rep = node_env.ensure_node_on_path(candidates=[])

    assert rep["source"] == "none"
    assert rep["node"] is None
    assert os.environ["PATH"] == before


def test_shim_not_written_when_electron_missing(tmp_path, monkeypatch):
    monkeypatch.setenv("PATH", str(tmp_path / "empty"))
    ghost = tmp_path / "gone" / "ZLink Agent"
    bin_dir = tmp_path / "bin"

    rep = node_env.ensure_node_on_path(candidates=[], electron_path=str(ghost), bin_dir=bin_dir)

    assert rep["source"] == "none"
    assert not bin_dir.exists()


def test_candidate_dirs_order_and_version_manager_resolution(tmp_path):
    for v in ("v9.11.2", "v18.20.4", "v22.9.0"):
        (tmp_path / ".nvm" / "versions" / "node" / v / "bin").mkdir(parents=True)
    (tmp_path / ".volta" / "bin").mkdir(parents=True)

    dirs = [str(d) for d in node_env.candidate_dirs(home=tmp_path)]

    assert dirs[0] == "/opt/homebrew/bin"  # 真实安装在最前，版本管理器排在后面
    nvm = [d for d in dirs if "/.nvm/" in d]
    assert nvm[:3] == [
        str(tmp_path / ".nvm/versions/node/v22.9.0/bin"),
        str(tmp_path / ".nvm/versions/node/v18.20.4/bin"),
        str(tmp_path / ".nvm/versions/node/v9.11.2/bin"),
    ]
    assert str(tmp_path / ".volta/bin") in dirs


def test_version_key_rejects_non_numeric():
    assert node_env._version_key("current") == (-1,)
    assert node_env._version_key("v24.18.1") > node_env._version_key("v9.0.0")
