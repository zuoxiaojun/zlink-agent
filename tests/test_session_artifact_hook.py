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


# ── T4: 会话外写出登记 external.jsonl ────────────────────────


def _ok_result(path: str) -> str:
    return json.dumps({"success": True, "data": f"Written 3 chars to {path}"})


def test_outside_write_is_registered(sessions_root):
    sid = sm.create_session()
    ctx.set_current_session(sid)
    outside = str(sessions_root.parent / "Desktop" / "U8_2026-09-01_销售订单.html")
    sah.artifact_after_hook("write_file", {"path": outside}, _ok_result(outside))
    entries = sah.read_external_entries(sid)
    assert len(entries) == 1
    assert entries[0]["path"] == outside
    assert entries[0]["tool"] == "write_file"
    assert "ts" in entries[0]


def test_inside_write_is_not_registered(sessions_root):
    sid = sm.create_session()
    ctx.set_current_session(sid)
    inside = str(sm.artifacts_dir(sid) / "r.html")
    sah.artifact_after_hook("write_file", {"path": inside}, _ok_result(inside))
    assert sah.read_external_entries(sid) == []


def test_failed_write_is_not_registered(sessions_root):
    sid = sm.create_session()
    ctx.set_current_session(sid)
    outside = str(sessions_root.parent / "x.html")
    sah.artifact_after_hook("write_file", {"path": outside}, json.dumps({"success": False, "error": "boom"}))
    assert sah.read_external_entries(sid) == []


def test_read_tools_never_register(sessions_root):
    sid = sm.create_session()
    ctx.set_current_session(sid)
    sah.artifact_after_hook("read_file", {"path": "/etc/hosts"}, json.dumps({"success": True}))
    assert sah.read_external_entries(sid) == []


def test_no_session_registers_nothing(sessions_root, tmp_path):
    ctx.set_current_session(None)
    sah.artifact_after_hook("write_file", {"path": str(tmp_path / "x.html")}, _ok_result("x"))
    assert list(sessions_root.glob("*/external.jsonl")) == []


def test_malformed_jsonl_lines_are_skipped(sessions_root):
    sid = sm.create_session()
    f = sm.session_dir(sid) / "external.jsonl"
    f.write_text('{"path": "/a.html"}\nNOT JSON\n\n{"path": "/b.html", "tool": "patch"}\n', encoding="utf-8")
    entries = sah.read_external_entries(sid)
    assert sorted(e["path"] for e in entries) == ["/a.html", "/b.html"]


def test_duplicates_deduped_latest_wins(sessions_root):
    sid = sm.create_session()
    ctx.set_current_session(sid)
    p = str(sessions_root.parent / "same.html")
    sah.artifact_after_hook("write_file", {"path": p}, _ok_result(p))
    sah.artifact_after_hook("patch", {"path": p}, _ok_result(p))
    entries = sah.read_external_entries(sid)
    assert len(entries) == 1 and entries[0]["tool"] == "patch"


def test_after_hook_does_not_mutate_result(sessions_root):
    sid = sm.create_session()
    ctx.set_current_session(sid)
    payload = _ok_result("/tmp/whatever.html")
    assert sah.artifact_after_hook("write_file", {"path": "/tmp/whatever.html"}, payload) == payload


def test_install_registers_both_hooks(sessions_root):
    from agent.tools.registry import registry

    sah.install_session_artifact_hooks()
    assert sah.artifact_before_hook in registry._before_hooks
    assert sah.artifact_after_hook in registry._after_hooks
    # 幂等：重复安装不叠加
    n = registry._after_hooks.count(sah.artifact_after_hook)
    sah.install_session_artifact_hooks()
    assert registry._after_hooks.count(sah.artifact_after_hook) == n
