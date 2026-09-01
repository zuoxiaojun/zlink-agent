"""会话目录化：CRUD 走 <sid>/session.json，迁移幂等，非法 sid 不落盘。"""

import json

import pytest

from agent import search_index
from agent import session_manager as sm


@pytest.fixture
def sessions_root(tmp_path, monkeypatch):
    """把 sessions 目录与 FTS 库都指向 tmp，测试不碰真实 ~/.zlink-agent。"""
    root = tmp_path / "sessions"
    root.mkdir()
    monkeypatch.setattr(sm, "SESSIONS_DIR", root)
    monkeypatch.setattr(sm, "INDEX_FILE", root / "index.json")
    monkeypatch.setattr(search_index, "DB_PATH", tmp_path / "search.db")
    return root


def test_create_session_makes_dir_and_artifacts(sessions_root):
    sid = sm.create_session("报表")
    assert (sessions_root / sid / "session.json").is_file()
    assert (sessions_root / sid / "artifacts").is_dir()
    assert not (sessions_root / f"{sid}.json").exists()


def test_save_and_load_roundtrip_uses_session_json(sessions_root):
    sid = sm.create_session()
    msgs = [{"role": "user", "content": "查一下销售订单"}]
    sm.save_session(sid, msgs, title="销售订单查询")
    assert (sessions_root / sid / "session.json").is_file()
    assert sm.load_session(sid) == msgs
    entry = next(e for e in sm.list_sessions() if e["id"] == sid)
    assert entry["title"] == "销售订单查询"


def test_delete_session_removes_dir_with_artifacts(sessions_root):
    sid = sm.create_session()
    art = sm.ensure_artifacts_dir(sid)
    (art / "report.html").write_text("<h1>x</h1>", encoding="utf-8")
    (sm.session_dir(sid) / "external.jsonl").write_text("{}", encoding="utf-8")
    sm.delete_session(sid)
    assert not (sessions_root / sid).exists()
    assert all(e["id"] != sid for e in sm.list_sessions())


def test_load_falls_back_to_legacy_flat_file(sessions_root):
    legacy = sessions_root / "abcd1234.json"
    legacy.write_text(
        json.dumps({"id": "abcd1234", "title": "旧", "messages": [{"role": "user", "content": "hi"}]}),
        encoding="utf-8",
    )
    assert sm.load_session("abcd1234") == [{"role": "user", "content": "hi"}]


def test_migrate_moves_flat_files_once(sessions_root):
    for sid in ("aaaa1111", "bbbb2222"):
        (sessions_root / f"{sid}.json").write_text(
            json.dumps({"id": sid, "title": sid, "messages": []}),
            encoding="utf-8",
        )
    (sessions_root / "index.json").write_text("[]", encoding="utf-8")

    assert sm.migrate_session_layout() == 2
    for sid in ("aaaa1111", "bbbb2222"):
        assert (sessions_root / sid / "session.json").is_file()
        assert (sessions_root / sid / "artifacts").is_dir()
        assert not (sessions_root / f"{sid}.json").exists()
    # 幂等：再跑一次不报错、不搬东西
    assert sm.migrate_session_layout() == 0


def test_migrate_skips_illegal_names_but_keeps_sibling(sessions_root):
    # "notes.backup" 含点 → 非法 sid，不应当作会话文件迁移
    (sessions_root / "notes.backup.json").write_text("{}", encoding="utf-8")
    (sessions_root / "cccc3333.json").write_text(
        json.dumps({"id": "cccc3333", "title": "", "messages": []}),
        encoding="utf-8",
    )
    sm.migrate_session_layout()
    assert (sessions_root / "notes.backup.json").is_file()
    assert not (sessions_root / "notes.backup").exists()
    assert (sessions_root / "cccc3333" / "session.json").is_file()


def test_illegal_session_id_never_writes_outside(sessions_root, tmp_path):
    evil = "../../../../../" + tmp_path.parent.name + "/pwn"
    sm.save_session(evil, [{"role": "user", "content": "x"}], title="t")
    assert not (tmp_path.parent / "pwn.json").exists()
    assert list(sessions_root.glob("*pwn*")) == []
    assert sm.load_session(evil) == []
