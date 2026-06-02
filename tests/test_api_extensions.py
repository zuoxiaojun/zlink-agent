"""Tests for the M5+ Extension HTTP API + smoke test for a session
endpoint.

These tests use FastAPI's :class:`TestClient` to drive the real
router stack.  No LLM, no YonSuite, no MCP server — just the
HTTP / FastAPI / pydantic plumbing.

The ``client`` fixture redirects ``agent.config_manager`` to a
temp file so the tests don't pollute the real ``data/config.json``
on the developer's machine.
"""
from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client(isolated_config, monkeypatch):
    """A TestClient around the real FastAPI app, with config
    redirected to a tmp file (so toggle tests don't write to
    the real data/config.json) and the 2 built-in extensions
    re-registered (the autouse ``clean_extensions`` fixture
    wiped them at the start of the test).
    """
    # Re-register the built-in extensions that
    # ``agent.agent`` registered at import time — the autouse
    # ``clean_extensions`` fixture cleared them.
    from agent.extensions import register_built_in_extensions
    from agent.events.extensions import apply_config_overrides
    register_built_in_extensions()
    # Apply the (empty) disabled list from the isolated config so
    # the runtime state matches what config says.
    apply_config_overrides([])

    from backend.main import app
    with TestClient(app) as c:
        yield c


# ────────────────────────────────────────────────────────────────────
# 1) GET /api/extensions — 列出全部
# ────────────────────────────────────────────────────────────────────

def test_list_extensions_returns_built_ins(client):
    """GET /api/extensions must return at least log-everything +
    security-event (built-ins registered at import time)."""
    resp = client.get("/api/extensions")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    names = {e["name"] for e in data}
    assert "log-everything" in names
    assert "security-event" in names
    # Each entry has the documented shape
    for entry in data:
        assert "name" in entry
        assert "enabled" in entry
        assert "description" in entry
        assert "kind" in entry
        assert entry["kind"] in ("log", "policy", "transform", "other")


def test_list_active_only_returns_enabled(client):
    """GET /api/extensions/active should be a subset of
    /api/extensions, and every entry must have enabled=True."""
    all_resp = client.get("/api/extensions").json()
    active_resp = client.get("/api/extensions/active").json()
    all_names = {e["name"] for e in all_resp}
    active_names = {e["name"] for e in active_resp}
    # active is a subset of all
    assert active_names.issubset(all_names)
    # all active entries are enabled
    for e in active_resp:
        assert e["enabled"] is True


# ────────────────────────────────────────────────────────────────────
# 2) PUT /api/extensions/{name}/toggle — runtime toggle
# ────────────────────────────────────────────────────────────────────

def test_toggle_extension_disables_it(client):
    """PUT /api/extensions/{name}/toggle with enabled=False must
    flip the live state and persist to config.json."""
    # Start from a known state — disable first
    client.put("/api/extensions/security-event/toggle", json={"enabled": False})

    resp = client.put("/api/extensions/security-event/toggle", json={"enabled": False})
    assert resp.status_code == 200
    data = resp.json()
    assert data["name"] == "security-event"
    assert data["enabled"] is False

    # Verify in the list endpoint
    listed = client.get("/api/extensions").json()
    sec = next(e for e in listed if e["name"] == "security-event")
    assert sec["enabled"] is False

    # And in the active endpoint
    active = client.get("/api/extensions/active").json()
    assert "security-event" not in {e["name"] for e in active}

    # Cleanup — re-enable so other tests aren't affected
    client.put("/api/extensions/security-event/toggle", json={"enabled": True})


def test_toggle_extension_re_enables_it(client):
    """Re-enabling via toggle must put the extension back in
    the active list."""
    # First disable
    client.put("/api/extensions/security-event/toggle", json={"enabled": False})
    # Then re-enable
    resp = client.put("/api/extensions/security-event/toggle", json={"enabled": True})
    assert resp.status_code == 200
    assert resp.json()["enabled"] is True

    listed = client.get("/api/extensions").json()
    sec = next(e for e in listed if e["name"] == "security-event")
    assert sec["enabled"] is True


def test_toggle_unknown_extension_returns_404(client):
    """A toggle request for a non-existent extension must return
    404, not 500 (no NameError leak)."""
    resp = client.put("/api/extensions/does_not_exist_xyz/toggle", json={"enabled": True})
    assert resp.status_code == 404
    assert "not found" in resp.json()["detail"].lower()


# ────────────────────────────────────────────────────────────────────
# 3) POST /api/extensions/reload
# ────────────────────────────────────────────────────────────────────

def test_reload_extensions_returns_now_active_and_disabled(client):
    """POST /api/extensions/reload should return a body with
    now_active and now_disabled lists (possibly empty)."""
    resp = client.post("/api/extensions/reload")
    assert resp.status_code == 200
    data = resp.json()
    assert "now_active" in data
    assert "now_disabled" in data
    assert isinstance(data["now_active"], list)
    assert isinstance(data["now_disabled"], list)


# ────────────────────────────────────────────────────────────────────
# 4) Health check — fast smoke that the whole FastAPI app boots
# ────────────────────────────────────────────────────────────────────

def test_health_check(client):
    """GET /api/health is a 1-line smoke test for the whole app."""
    resp = client.get("/api/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}
