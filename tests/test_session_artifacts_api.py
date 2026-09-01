"""产物 API：列表分类/截断，文件端点的路径穿越防护，zip，reveal。"""

import shutil

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import backend.api.session_artifacts as sa_mod
from agent import search_index
from agent import session_manager as sm


@pytest.fixture
def client(tmp_path, monkeypatch):
    root = tmp_path / "sessions"
    root.mkdir()
    monkeypatch.setattr(sm, "SESSIONS_DIR", root)
    monkeypatch.setattr(sm, "INDEX_FILE", root / "index.json")
    monkeypatch.setattr(search_index, "DB_PATH", tmp_path / "search.db")

    app = FastAPI()
    app.include_router(sa_mod.router)
    with TestClient(app) as c:
        yield c


@pytest.fixture
def sid_with_artifacts(client):
    sid = sm.create_session("报表")
    art = sm.ensure_artifacts_dir(sid)
    (art / "report.html").write_text("<h1>r</h1>", encoding="utf-8")
    (art / "notes.md").write_text("# t", encoding="utf-8")
    (art / "chart.js").write_text("console.log(1)", encoding="utf-8")
    (art / "pic.png").write_bytes(b"\x89PNG\r\n")
    sub = art / "sub"
    sub.mkdir()
    (sub / "deep.pdf").write_bytes(b"%PDF-1.4")
    (sub / "blob.bin").write_bytes(b"\x00\x01")
    return sid


def test_list_artifacts_classifies_kinds(client, sid_with_artifacts):
    sid = sid_with_artifacts
    r = client.get(f"/api/sessions/{sid}/artifacts")
    assert r.status_code == 200
    body = r.json()
    kinds = {i["name"]: i["kind"] for i in body["items"]}
    assert kinds["report.html"] == "html"
    assert kinds["notes.md"] == "md"
    assert kinds["pic.png"] == "image"
    assert kinds["deep.pdf"] == "pdf"
    assert kinds["chart.js"] == "text"
    assert kinds["blob.bin"] == "other"
    assert body["truncated"] is False
    assert body["count"] == len(body["items"]) == 6
    # rel 是相对 artifacts/ 的 POSIX 路径
    assert "sub/deep.pdf" in {i["rel"] for i in body["items"]}


def test_list_artifacts_unknown_sid_404(client):
    assert client.get("/api/sessions/deadbeef/artifacts").status_code == 404


def test_list_artifacts_truncation_flag(client, sid_with_artifacts):
    sid = sid_with_artifacts
    art = sm.ensure_artifacts_dir(sid)
    for i in range(300):
        (art / f"f{i:03d}.txt").write_text("x", encoding="utf-8")
    body = client.get(f"/api/sessions/{sid}/artifacts").json()
    assert body["truncated"] is True
    assert len(body["items"]) == sa_mod.MAX_LIST_ITEMS


def test_list_includes_external_with_exists(client, sid_with_artifacts, tmp_path):
    from agent.tools import session_artifact_hook as sah

    sid = sid_with_artifacts
    gone = str(tmp_path / "gone.html")
    here = tmp_path / "here.html"
    here.write_text("x", encoding="utf-8")
    sah.record_external_write(sid, str(here), "write_file")
    sah.record_external_write(sid, gone, "write_file")
    body = client.get(f"/api/sessions/{sid}/artifacts").json()
    by_path = {e["abs_path"]: e for e in body["external"]}
    assert by_path[str(here)]["exists"] is True
    assert by_path[gone]["exists"] is False


def test_empty_session_dir_gets_recreated(client, sid_with_artifacts):
    sid = sid_with_artifacts
    shutil.rmtree(sm.artifacts_dir(sid))
    assert client.get(f"/api/sessions/{sid}/artifacts").status_code == 200
    assert sm.artifacts_dir(sid).is_dir()


def test_illegal_sid_in_url_is_404(client):
    assert client.get("/api/sessions/..%2F..%2Fetc/artifacts").status_code == 404


def test_list_rejects_illegal_sid_shape(client, sid_with_artifacts):
    # 含点的名字不是合法 sid（正是迁移用例里被跳过的那一类），必须 404 而不是 500
    assert client.get("/api/sessions/notes.backup/artifacts").status_code == 404
