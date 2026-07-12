"""Tests for the /api/mcp REST endpoints.

Uses FastAPI's TestClient with an isolated config and monkeypatched
MCP server connection functions (no real subprocess or network calls).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client(isolated_config, monkeypatch):
    """TestClient with isolated config and no-op MCP server functions."""

    # Patch all async MCP functions to no-ops so we never try real connections
    async def _noop_connect(name, config):
        pass

    async def _noop_disconnect(name):
        pass

    async def _noop_reload():
        return {"status": {}}

    async def _noop_test(name, config):
        return {"success": True, "tools_discovered": 3, "tool_names": ["tool1", "tool2"], "error_message": None}

    def _noop_statuses():
        return []

    import agent.tools.mcp_manager as mcp_mgr

    monkeypatch.setattr(mcp_mgr, "connect_server", _noop_connect)
    monkeypatch.setattr(mcp_mgr, "disconnect_server", _noop_disconnect)
    monkeypatch.setattr(mcp_mgr, "reload_all_servers", _noop_reload)
    monkeypatch.setattr(mcp_mgr, "test_server_connection", _noop_test)
    monkeypatch.setattr(mcp_mgr, "get_server_statuses", _noop_statuses)

    from agent.extensions import register_built_in_extensions
    from agent.events.extensions import apply_config_overrides

    register_built_in_extensions()
    apply_config_overrides([])

    from backend.main import app

    # Also patch the references in mcp_api, which may have been
    # imported earlier by another test's fixture (module caching).
    import backend.api.mcp_api as mcp_api_mod

    monkeypatch.setattr(mcp_api_mod, "connect_server", _noop_connect)
    monkeypatch.setattr(mcp_api_mod, "disconnect_server", _noop_disconnect)
    monkeypatch.setattr(mcp_api_mod, "reload_all_servers", _noop_reload)
    monkeypatch.setattr(mcp_api_mod, "test_server_connection", _noop_test)
    monkeypatch.setattr(mcp_api_mod, "get_server_statuses", _noop_statuses)

    with TestClient(app) as c:
        yield c


MCP_SERVER_PAYLOAD = {
    "name": "test-server",
    "transport": "stdio",
    "command": "echo",
    "args": ["hello"],
    "env": {"FOO": "bar"},
    "enabled": True,
    "timeout": 30,
}


# ────────────────────────────────────────────────────────────────────
# 1) GET /api/mcp/servers
# ────────────────────────────────────────────────────────────────────


def test_list_servers_empty(client):
    """Initially there should be no MCP servers."""
    resp = client.get("/api/mcp/servers")
    assert resp.status_code == 200
    assert resp.json() == []


# ────────────────────────────────────────────────────────────────────
# 2) POST /api/mcp/servers — add
# ────────────────────────────────────────────────────────────────────


def test_add_server(client, isolated_config: Path):
    resp = client.post("/api/mcp/servers", json=MCP_SERVER_PAYLOAD)
    assert resp.status_code == 201
    assert resp.json()["ok"] is True

    # Verify it was persisted
    raw = json.loads(isolated_config.read_text())
    assert "test-server" in raw.get("mcp_servers", {})


def test_add_server_duplicate_returns_409(client):
    client.post("/api/mcp/servers", json=MCP_SERVER_PAYLOAD)
    resp = client.post("/api/mcp/servers", json=MCP_SERVER_PAYLOAD)
    assert resp.status_code == 409
    assert "already exists" in resp.json()["detail"].lower()


def test_add_server_http_transport(client, isolated_config: Path):
    payload = {
        "name": "http-server",
        "transport": "http",
        "url": "http://localhost:9999/mcp",
        "headers": {"Authorization": "Bearer tok"},
        "enabled": True,
        "timeout": 60,
    }
    resp = client.post("/api/mcp/servers", json=payload)
    assert resp.status_code == 201

    raw = json.loads(isolated_config.read_text())
    srv = raw["mcp_servers"]["http-server"]
    assert srv["transport"] == "http"
    assert srv["url"] == "http://localhost:9999/mcp"


# ────────────────────────────────────────────────────────────────────
# 3) PUT /api/mcp/servers/{name} — update
# ────────────────────────────────────────────────────────────────────


def test_update_server(client, isolated_config: Path):
    client.post("/api/mcp/servers", json=MCP_SERVER_PAYLOAD)

    update = dict(MCP_SERVER_PAYLOAD)
    update["args"] = ["world"]
    resp = client.put(f"/api/mcp/servers/{MCP_SERVER_PAYLOAD['name']}", json=update)
    assert resp.status_code == 200

    raw = json.loads(isolated_config.read_text())
    assert raw["mcp_servers"]["test-server"]["args"] == ["world"]


def test_update_server_not_found(client):
    resp = client.put("/api/mcp/servers/does-not-exist", json=MCP_SERVER_PAYLOAD)
    assert resp.status_code == 404
    assert "not found" in resp.json()["detail"].lower()


def test_update_server_builtin_returns_403(client, isolated_config: Path):
    """A builtin server should not be updatable."""
    # Manually inject a builtin server
    cfg = json.loads(isolated_config.read_text())
    cfg["mcp_servers"] = {
        "builtin-srv": {
            "transport": "stdio",
            "command": "echo",
            "args": [],
            "env": {},
            "enabled": True,
            "timeout": 120,
            "builtin": True,
        }
    }
    isolated_config.write_text(json.dumps(cfg))

    resp = client.put("/api/mcp/servers/builtin-srv", json=MCP_SERVER_PAYLOAD)
    assert resp.status_code == 403


# ────────────────────────────────────────────────────────────────────
# 4) DELETE /api/mcp/servers/{name}
# ────────────────────────────────────────────────────────────────────


def test_delete_server(client, isolated_config: Path):
    client.post("/api/mcp/servers", json=MCP_SERVER_PAYLOAD)
    resp = client.delete(f"/api/mcp/servers/{MCP_SERVER_PAYLOAD['name']}")
    assert resp.status_code == 204

    raw = json.loads(isolated_config.read_text())
    assert "test-server" not in raw.get("mcp_servers", {})


def test_delete_server_not_found(client):
    resp = client.delete("/api/mcp/servers/does-not-exist")
    assert resp.status_code == 404


def test_delete_server_builtin_returns_403(client, isolated_config: Path):
    cfg = json.loads(isolated_config.read_text())
    cfg["mcp_servers"] = {
        "builtin-srv": {
            "transport": "stdio",
            "command": "echo",
            "args": [],
            "env": {},
            "enabled": True,
            "timeout": 120,
            "builtin": True,
        }
    }
    isolated_config.write_text(json.dumps(cfg))

    resp = client.delete("/api/mcp/servers/builtin-srv")
    assert resp.status_code == 403


# ────────────────────────────────────────────────────────────────────
# 5) PUT /api/mcp/servers/{name}/toggle
# ────────────────────────────────────────────────────────────────────


def test_toggle_server_disable(client, isolated_config: Path):
    client.post("/api/mcp/servers", json=MCP_SERVER_PAYLOAD)
    resp = client.put(f"/api/mcp/servers/{MCP_SERVER_PAYLOAD['name']}/toggle")
    assert resp.status_code == 200
    data = resp.json()
    assert data["enabled"] is False

    raw = json.loads(isolated_config.read_text())
    assert raw["mcp_servers"]["test-server"]["enabled"] is False


def test_toggle_server_enable(client, isolated_config: Path):
    # Add disabled then toggle
    payload = dict(MCP_SERVER_PAYLOAD)
    payload["enabled"] = False
    client.post("/api/mcp/servers", json=payload)

    resp = client.put(f"/api/mcp/servers/{MCP_SERVER_PAYLOAD['name']}/toggle")
    assert resp.status_code == 200
    assert resp.json()["enabled"] is True


def test_toggle_server_not_found(client):
    resp = client.put("/api/mcp/servers/does-not-exist/toggle")
    assert resp.status_code == 404


# ────────────────────────────────────────────────────────────────────
# 6) POST /api/mcp/servers/{name}/reconnect
# ────────────────────────────────────────────────────────────────────


def test_reconnect_server(client):
    client.post("/api/mcp/servers", json=MCP_SERVER_PAYLOAD)
    resp = client.post(f"/api/mcp/servers/{MCP_SERVER_PAYLOAD['name']}/reconnect")
    assert resp.status_code == 200
    assert resp.json()["ok"] is True


def test_reconnect_server_not_found(client):
    resp = client.post("/api/mcp/servers/does-not-exist/reconnect")
    assert resp.status_code == 404


# ────────────────────────────────────────────────────────────────────
# 7) POST /api/mcp/servers/{name}/test
# ────────────────────────────────────────────────────────────────────


def test_test_server_by_name(client):
    client.post("/api/mcp/servers", json=MCP_SERVER_PAYLOAD)
    resp = client.post(f"/api/mcp/servers/{MCP_SERVER_PAYLOAD['name']}/test")
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert data["tools_discovered"] == 3


def test_test_server_not_found(client):
    resp = client.post("/api/mcp/servers/does-not-exist/test")
    assert resp.status_code == 404


def test_test_server_with_body(client):
    """Test connection with an inline config (not stored)."""
    resp = client.post(
        "/api/mcp/servers/test-inline/test",
        json={
            "name": "test-inline",
            "transport": "stdio",
            "command": "echo",
            "args": [],
            "enabled": True,
            "timeout": 30,
        },
    )
    assert resp.status_code == 200
    assert resp.json()["success"] is True


# ────────────────────────────────────────────────────────────────────
# 8) POST /api/mcp/reload
# ────────────────────────────────────────────────────────────────────


def test_reload_servers(client):
    resp = client.post("/api/mcp/reload")
    assert resp.status_code == 200
    assert resp.json() == {"status": {}}
