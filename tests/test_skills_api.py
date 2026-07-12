"""Tests for the /api/skills REST endpoints.

Uses FastAPI's TestClient with an isolated config and monkeypatched
skill_manager functions (no real filesystem skills).
"""

from __future__ import annotations

import io
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client(isolated_config, monkeypatch):
    """TestClient with isolated config and mocked skill_manager."""

    # Mock all skill_manager functions to avoid real filesystem access
    mock_skills = [
        {"name": "skill-a", "description": "Skill A desc", "version": "1.0", "tags": ["tag1"], "builtin": True},
        {"name": "skill-b", "description": "Skill B desc", "version": "2.0", "tags": ["tag2", "tag3"], "builtin": False},
    ]

    import agent.skill_manager as sm

    monkeypatch.setattr(sm, "get_all_skills", lambda: mock_skills)
    monkeypatch.setattr(sm, "get_active_skills", lambda: ["skill-a"])
    monkeypatch.setattr(sm, "get_skill_content", lambda name: f"---\nname: {name}\n---\nContent for {name}" if name in ("skill-a", "skill-b") else None)
    monkeypatch.setattr(sm, "set_skill_active", lambda name, active: name in ("skill-a", "skill-b"))
    monkeypatch.setattr(sm, "update_skill_content", _mock_update_skill)
    monkeypatch.setattr(sm, "uninstall_skill", _mock_uninstall_skill)
    monkeypatch.setattr(sm, "install_skill_from_zip", lambda path: "installed-skill")

    from agent.extensions import register_built_in_extensions
    from agent.events.extensions import apply_config_overrides

    register_built_in_extensions()
    apply_config_overrides([])

    from backend.main import app

    with TestClient(app) as c:
        yield c


def _mock_update_skill(name, content) -> bool | None:
    if name == "builtin-skill":
        return None  # builtin — not modifiable
    if name == "skill-b":
        return True  # user skill — modifiable
    return False  # not found


def _mock_uninstall_skill(name) -> bool | None:
    if name == "builtin-skill":
        return None  # builtin — not removable
    if name == "skill-b":
        return True  # user skill — removable
    return False  # not found


# ────────────────────────────────────────────────────────────────────
# 1) GET /api/skills — list
# ────────────────────────────────────────────────────────────────────


def test_list_skills_returns_all(client):
    resp = client.get("/api/skills")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 2


def test_list_skills_shape(client):
    resp = client.get("/api/skills")
    for s in resp.json():
        assert "name" in s
        assert "description" in s
        assert "version" in s
        assert "tags" in s
        assert "active" in s
        assert "builtin" in s
        assert isinstance(s["active"], bool)
        assert isinstance(s["builtin"], bool)
        assert isinstance(s["tags"], list)


def test_list_skills_active_status(client):
    resp = client.get("/api/skills")
    data = resp.json()
    skill_a = next(s for s in data if s["name"] == "skill-a")
    skill_b = next(s for s in data if s["name"] == "skill-b")
    assert skill_a["active"] is True  # in active list
    assert skill_b["active"] is False  # not in active list


def test_list_skills_builtin_flag(client):
    resp = client.get("/api/skills")
    data = resp.json()
    skill_a = next(s for s in data if s["name"] == "skill-a")
    skill_b = next(s for s in data if s["name"] == "skill-b")
    assert skill_a["builtin"] is True
    assert skill_b["builtin"] is False


# ────────────────────────────────────────────────────────────────────
# 2) GET /api/skills/{name}
# ────────────────────────────────────────────────────────────────────


def test_get_skill_content(client):
    resp = client.get("/api/skills/skill-a")
    assert resp.status_code == 200
    data = resp.json()
    assert data["name"] == "skill-a"
    assert "Content for skill-a" in data["content"]


def test_get_skill_not_found(client):
    resp = client.get("/api/skills/does-not-exist")
    assert resp.status_code == 404
    assert "not found" in resp.json()["detail"].lower()


# ────────────────────────────────────────────────────────────────────
# 3) PUT /api/skills/{name}/toggle
# ────────────────────────────────────────────────────────────────────


def test_toggle_skill_enable(client):
    resp = client.put("/api/skills/skill-b/toggle", json={"active": True})
    assert resp.status_code == 200
    assert resp.json()["ok"] is True


def test_toggle_skill_disable(client):
    resp = client.put("/api/skills/skill-a/toggle", json={"active": False})
    assert resp.status_code == 200
    assert resp.json()["ok"] is True


def test_toggle_skill_not_found(client):
    """Toggle a non-existent skill returns 404."""
    resp = client.put("/api/skills/does-not-exist/toggle", json={"active": True})
    assert resp.status_code == 404


# ────────────────────────────────────────────────────────────────────
# 4) PUT /api/skills/{name} — update content
# ────────────────────────────────────────────────────────────────────


def test_update_skill_content(client):
    resp = client.put("/api/skills/skill-b", json={"content": "new content"})
    assert resp.status_code == 200
    assert resp.json()["ok"] is True


def test_update_builtin_skill_returns_403(client):
    """Builtin skills should not be modifiable."""
    resp = client.put("/api/skills/builtin-skill", json={"content": "new content"})
    assert resp.status_code == 403
    assert "内置技能" in resp.json()["detail"]


def test_update_skill_not_found(client):
    resp = client.put("/api/skills/does-not-exist", json={"content": "new content"})
    assert resp.status_code == 404


# ────────────────────────────────────────────────────────────────────
# 5) DELETE /api/skills/{name}
# ────────────────────────────────────────────────────────────────────


def test_delete_user_skill(client):
    resp = client.delete("/api/skills/skill-b")
    assert resp.status_code == 200
    assert resp.json()["ok"] is True


def test_delete_builtin_skill_returns_403(client):
    resp = client.delete("/api/skills/builtin-skill")
    assert resp.status_code == 403
    assert "内置技能" in resp.json()["detail"]


def test_delete_skill_not_found(client):
    resp = client.delete("/api/skills/does-not-exist")
    assert resp.status_code == 404


# ────────────────────────────────────────────────────────────────────
# 6) POST /api/skills/install
# ────────────────────────────────────────────────────────────────────


def test_install_skill_rejects_non_zip(client):
    resp = client.post("/api/skills/install", files={"file": ("skill.txt", b"not a zip", "text/plain")})
    assert resp.status_code == 400
    assert ".zip" in resp.json()["detail"].lower()


def test_install_skill_accepts_zip(client, monkeypatch):
    """Should accept a .zip file and return the skill name."""

    # We already mocked install_skill_from_zip in the fixture, but
    # for this test we need to also make sure the file upload works.
    # The mock already returns "installed-skill".
    zip_data = io.BytesIO()
    import zipfile

    with zipfile.ZipFile(zip_data, "w") as zf:
        zf.writestr("skill-dir/SKILL.md", "---\nname: installed-skill\n---\nContent")
    zip_data.seek(0)

    resp = client.post(
        "/api/skills/install",
        files={"file": ("skill.zip", zip_data.read(), "application/zip")},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["skill_name"] == "installed-skill"
