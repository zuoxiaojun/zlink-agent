"""路径归一：有会话上下文时相对路径落产物目录；没有时行为不变。"""

import json

import pytest

from agent import session_context as ctx
from agent import session_manager as sm
from agent.tools import session_artifact_hook as sah


@pytest.fixture
def sessions_root(tmp_path, monkeypatch):
    root = tmp_path / "sessions"
    root.mkdir()
    monkeypatch.setattr(sm, "SESSIONS_DIR", root)
    monkeypatch.setattr(sm, "INDEX_FILE", root / "index.json")
    yield root
    ctx.set_current_session(None)


@pytest.fixture
def cwd_isolated(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    return tmp_path


def _call(tool, **args):
    return sah.artifact_before_hook(tool, dict(args))


def test_relative_write_path_goes_to_artifacts(sessions_root):
    sid = sm.create_session()
    ctx.set_current_session(sid)
    out = _call("write_file", path="report.html", content="x")
    assert out["path"] == str(sessions_root / sid / "artifacts" / "report.html")


def test_nested_relative_path_carries_subdir(sessions_root):
    sid = sm.create_session()
    ctx.set_current_session(sid)
    out = _call("write_file", path="charts/bar.js", content="x")
    assert out["path"].endswith("artifacts/charts/bar.js")


def test_absolute_and_tilde_paths_untouched(sessions_root):
    sid = sm.create_session()
    ctx.set_current_session(sid)
    assert _call("write_file", path="/tmp/a.html")["path"] == "/tmp/a.html"
    assert _call("write_file", path="~/Desktop/a.html")["path"] == "~/Desktop/a.html"


def test_no_session_context_leaves_path_as_is(cwd_isolated):
    """无会话上下文 → args 逐字不动（行为与改动前一致）。"""
    assert _call("write_file", path="a.html")["path"] == "a.html"
    assert _call("ls") == {}  # 不注入 key；缺省 "." 由 handler 自己的默认值决定
    assert _call("ls", path=".")["path"] == "."
    assert _call("terminal", command="pwd") == {"command": "pwd"}  # 不填 workdir
    assert list(cwd_isolated.iterdir()) == []  # 也没有顺手创建任何目录


def test_missing_path_arg_gets_artifacts_dir(sessions_root):
    sid = sm.create_session()
    ctx.set_current_session(sid)
    assert _call("ls")["path"] == str(sessions_root / sid / "artifacts")
    assert _call("terminal", command="pwd")["workdir"] == str(sessions_root / sid / "artifacts")


def test_terminal_relative_workdir_resolves_to_artifacts(sessions_root):
    sid = sm.create_session()
    ctx.set_current_session(sid)
    out = _call("terminal", command="ls", workdir="sub")
    assert out["workdir"] == str(sessions_root / sid / "artifacts" / "sub")


def test_unknown_tool_and_non_string_path_pass_through(sessions_root):
    sid = sm.create_session()
    ctx.set_current_session(sid)
    assert _call("erp_ys_api", path="a.html")["path"] == "a.html"
    assert _call("write_file", path=123)["path"] == 123


def test_hook_never_blocks(sessions_root):
    sid = sm.create_session()
    ctx.set_current_session(sid)
    assert "__block__" not in _call("write_file", path="a.html")


def test_real_write_lands_in_session_artifacts(sessions_root, cwd_isolated):
    """端到端：真调 write_file handler（含 FileMutationQueue 路径）。"""
    from agent.tools.file_tools import _handle_write_file

    sid = sm.create_session()
    ctx.set_current_session(sid)
    args = sah.artifact_before_hook("write_file", {"path": "r.html", "content": "<h1>hi</h1>"})
    res = json.loads(_handle_write_file(args))
    assert res["success"] is True
    assert (sessions_root / sid / "artifacts" / "r.html").read_text(encoding="utf-8") == "<h1>hi</h1>"
    assert list(cwd_isolated.glob("*.html")) == []  # 仓库/cwd 不再被污染


def test_is_within_helper(tmp_path):
    root = tmp_path / "artifacts"
    root.mkdir()
    assert sah.is_within(root / "a" / "b.html", root)
    assert not sah.is_within(tmp_path / "elsewhere.html", root)
