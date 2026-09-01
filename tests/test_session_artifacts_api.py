"""产物 API：列表分类/截断，文件端点的路径穿越防护，zip，reveal。"""

import shutil
import zipfile
from io import BytesIO

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


# ── T6: 文件端点（内容出口 + CSP + 下载）──────────────────


def _get_file(client, sid, rel, **params):
    return client.get(f"/api/session-files/{sid}/{rel}", params=params)


def test_file_endpoint_serves_html_with_csp(client, sid_with_artifacts):
    r = _get_file(client, sid_with_artifacts, "report.html")
    assert r.status_code == 200
    assert r.text == "<h1>r</h1>"
    assert "sandbox allow-scripts" in r.headers.get("content-security-policy", "")
    assert r.headers.get("x-content-type-options") == "nosniff"
    assert r.headers.get("content-disposition", "").startswith("inline")


def test_file_endpoint_text_body(client, sid_with_artifacts):
    r = _get_file(client, sid_with_artifacts, "notes.md")
    assert r.status_code == 200
    assert r.text == "# t"


def test_file_endpoint_nested_rel(client, sid_with_artifacts):
    r = _get_file(client, sid_with_artifacts, "sub/deep.pdf")
    assert r.status_code == 200
    assert r.content.startswith(b"%PDF")


def test_file_endpoint_download_disposition(client, sid_with_artifacts):
    r = _get_file(client, sid_with_artifacts, "report.html", download=1)
    cd = r.headers.get("content-disposition", "")
    assert cd.startswith("attachment")
    assert "report.html" in cd


ATTACKS = [
    "../session.json",
    "..%2Fsession.json",
    "sub/../../session.json",
    "./../session.json",
    "/etc/hosts",
    "C:\\Windows\\win.ini",
    "Session.json",
    "nope.html",
]


@pytest.mark.parametrize("target", ATTACKS)
def test_path_traversal_is_404(client, sid_with_artifacts, target):
    assert _get_file(client, sid_with_artifacts, target).status_code == 404


def test_empty_rel_is_rejected():
    # 空 rel 不走 HTTP：Starlette 对末尾斜杠会 307，不适合做 404 断言
    assert sa_mod._resolve_in_artifacts("aaaa1111", "") is None


def test_symlink_escape_is_404(client, sid_with_artifacts, tmp_path):
    sid = sid_with_artifacts
    outside = tmp_path / "secret.txt"
    outside.write_text("secret", encoding="utf-8")
    link = sm.artifacts_dir(sid) / "link.txt"
    try:
        link.symlink_to(outside)
    except OSError:  # pragma: no cover - 文件系统不支持软链接
        pytest.skip("文件系统不支持软链接")
    assert _get_file(client, sid, "link.txt").status_code == 404


def test_illegal_sid_is_404(client):
    # 百分号编码的 .. 才能原样抵达路由参数（字面 /../ 会被 httpx 在客户端归一）
    assert client.get("/api/session-files/%2e%2e%2fdeadbeef/report.html").status_code == 404


# ── T7: zip 打包 + 在 Finder 显示 ─────────────────────


def test_zip_contains_relative_entries(client, sid_with_artifacts):
    sid = sid_with_artifacts
    r = client.get(f"/api/sessions/{sid}/artifacts/zip")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("application/zip")
    assert sid in r.headers["content-disposition"]
    zf = zipfile.ZipFile(BytesIO(r.content))
    names = set(zf.namelist())
    assert {"report.html", "notes.md", "sub/deep.pdf"} <= names
    assert zf.read("report.html").decode() == "<h1>r</h1>"


def test_zip_skips_symlinks(client, sid_with_artifacts, tmp_path):
    sid = sid_with_artifacts
    outside = tmp_path / "evil.txt"
    outside.write_text("nope", encoding="utf-8")
    try:
        (sm.artifacts_dir(sid) / "link.txt").symlink_to(outside)
    except OSError:  # pragma: no cover
        pytest.skip("文件系统不支持软链接")
    zf = zipfile.ZipFile(BytesIO(client.get(f"/api/sessions/{sid}/artifacts/zip").content))
    assert "link.txt" not in zf.namelist()


def test_zip_empty_dir_ok(client, sid_with_artifacts):
    sid = sid_with_artifacts
    for p in sm.artifacts_dir(sid).rglob("*"):
        if p.is_file():
            p.unlink()
    r = client.get(f"/api/sessions/{sid}/artifacts/zip")
    assert r.status_code == 200
    assert zipfile.ZipFile(BytesIO(r.content)).namelist() == []


def test_zip_oversized_returns_413(client, sid_with_artifacts, monkeypatch):
    monkeypatch.setattr(sa_mod, "MAX_ZIP_BYTES", 10)
    r = client.get(f"/api/sessions/{sid_with_artifacts}/artifacts/zip")
    assert r.status_code == 413


def test_reveal_rejects_unlisted_abs_path(client, sid_with_artifacts):
    r = client.post(f"/api/sessions/{sid_with_artifacts}/artifacts/reveal", json={"abs_path": "/etc/hosts"})
    assert r.status_code == 403


def test_reveal_requires_a_target(client, sid_with_artifacts):
    assert client.post(f"/api/sessions/{sid_with_artifacts}/artifacts/reveal", json={}).status_code == 422


def test_reveal_accepts_internal_rel(client, sid_with_artifacts, monkeypatch):
    sid = sid_with_artifacts
    seen: list[str] = []
    monkeypatch.setattr(sa_mod, "_reveal_in_file_manager", lambda p: seen.append(str(p)))
    r = client.post(f"/api/sessions/{sid}/artifacts/reveal", json={"rel": "report.html"})
    assert r.status_code == 200
    assert seen and seen[0].endswith("report.html")


def test_reveal_rejects_rel_traversal(client, sid_with_artifacts):
    r = client.post(f"/api/sessions/{sid_with_artifacts}/artifacts/reveal", json={"rel": "../session.json"})
    assert r.status_code == 404


def test_reveal_accepts_registered_abs_path(client, sid_with_artifacts, tmp_path, monkeypatch):
    from agent.tools import session_artifact_hook as sah

    sid = sid_with_artifacts
    p = tmp_path / "out.html"
    p.write_text("x", encoding="utf-8")
    sah.record_external_write(sid, str(p), "write_file")
    monkeypatch.setattr(sa_mod, "_reveal_in_file_manager", lambda target: None)
    assert client.post(f"/api/sessions/{sid}/artifacts/reveal", json={"abs_path": str(p)}).status_code == 200


def test_reveal_registered_but_gone_is_404(client, sid_with_artifacts, tmp_path, monkeypatch):
    from agent.tools import session_artifact_hook as sah

    sid = sid_with_artifacts
    gone = tmp_path / "gone.html"
    sah.record_external_write(sid, str(gone), "write_file")
    monkeypatch.setattr(sa_mod, "_reveal_in_file_manager", lambda target: None)
    assert client.post(f"/api/sessions/{sid}/artifacts/reveal", json={"abs_path": str(gone)}).status_code == 404
