"""Tests for the /api/config REST endpoints.

Uses FastAPI's TestClient with an isolated config file so tests don't
pollute the real data/config.json.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client(isolated_config, monkeypatch):
    """TestClient with isolated config and no lifespan side-effects."""
    from agent.extensions import register_built_in_extensions
    from agent.events.extensions import apply_config_overrides

    register_built_in_extensions()
    apply_config_overrides([])

    from backend.main import app

    with TestClient(app) as c:
        yield c


# ────────────────────────────────────────────────────────────────────
# 1) GET /api/config
# ────────────────────────────────────────────────────────────────────


def test_get_config_returns_all_sections(client):
    resp = client.get("/api/config")
    assert resp.status_code == 200
    data = resp.json()
    assert "llm" in data
    assert "yonsuite" in data
    assert "agent" in data


def test_get_config_llm_shape(client):
    resp = client.get("/api/config")
    llm = resp.json()["llm"]
    assert "api_key" in llm
    assert "base_url" in llm
    assert "model" in llm
    assert "provider" in llm
    # API key should be masked
    assert "****" in llm["api_key"] or llm["api_key"] == ""


def test_get_config_yonsuite_shape(client):
    resp = client.get("/api/config")
    ys = resp.json()["yonsuite"]
    assert "app_key" in ys
    assert "app_secret" in ys
    assert "tenant_id" in ys
    assert "gateway_url" in ys


def test_get_config_agent_shape(client):
    resp = client.get("/api/config")
    agent = resp.json()["agent"]
    assert "max_iterations" in agent
    assert "compaction_enabled" in agent
    assert "max_context_tokens" in agent
    assert "max_context_tokens_auto" in agent
    assert "reserve_tokens" in agent
    assert "keep_recent_tokens" in agent
    assert "approval_mode" in agent
    assert agent["max_context_tokens_auto"] is True  # default is auto


def test_get_config_default_values(client):
    """Default config should have sensible defaults."""
    resp = client.get("/api/config")
    data = resp.json()
    assert data["llm"]["base_url"] == "https://api.openai.com/v1"
    assert data["llm"]["model"] == "gpt-4o"
    assert data["llm"]["provider"] == "OpenAI"
    assert data["agent"]["max_iterations"] == 30
    assert data["agent"]["compaction_enabled"] is True
    assert data["agent"]["reserve_tokens"] == 4000
    assert data["agent"]["keep_recent_tokens"] == 8000
    assert data["agent"]["approval_mode"] == "allow_all"


# ────────────────────────────────────────────────────────────────────
# 2) PUT /api/config/llm
# ────────────────────────────────────────────────────────────────────


def test_save_llm_config_updates_values(client):
    resp = client.put(
        "/api/config/llm",
        json={
            "api_key": "sk-new-key",
            "base_url": "https://custom.api.com/v1",
            "model": "custom-model",
            "provider": "CustomProvider",
        },
    )
    assert resp.status_code == 200
    assert resp.json()["ok"] is True

    # Verify it was persisted
    config = client.get("/api/config").json()
    assert config["llm"]["model"] == "custom-model"
    assert config["llm"]["provider"] == "CustomProvider"


def test_save_llm_config_ignores_masked_key(client):
    """If the api_key starts with ***, it should not overwrite the stored key."""
    # First set a key
    client.put("/api/config/llm", json={"api_key": "real-key-12345", "base_url": "", "model": "gpt-4o", "provider": "OpenAI"})
    # Then send a masked key — should be ignored
    resp = client.put(
        "/api/config/llm",
        json={
            "api_key": "***masked***",
            "base_url": "",
            "model": "gpt-4o",
            "provider": "OpenAI",
        },
    )
    assert resp.status_code == 200

    config = client.get("/api/config").json()
    # The masked key should not have replaced the real key
    assert config["llm"]["api_key"] != "***masked***"


def test_save_llm_config_empty_api_key_ignored(client):
    """If api_key is empty string, it should be treated as no-update
    (the endpoint only updates if api_key is truthy and not masked)."""
    resp = client.put(
        "/api/config/llm",
        json={"api_key": "", "base_url": "https://new.url/v1", "model": "gpt-4o-mini", "provider": "OpenAI"},
    )
    assert resp.status_code == 200
    config = client.get("/api/config").json()
    # base_url and model should update, api_key stays empty/previous
    assert config["llm"]["base_url"] == "https://new.url/v1"


# ────────────────────────────────────────────────────────────────────
# 3) PUT /api/config/agent
# ────────────────────────────────────────────────────────────────────


def test_save_agent_config(client, isolated_config: Path):
    resp = client.put(
        "/api/config/agent",
        json={
            "max_iterations": 20,
            "compaction_enabled": False,
            "max_context_tokens": 64000,
            "max_context_tokens_auto": False,
            "reserve_tokens": 2000,
            "keep_recent_tokens": 6000,
            "approval_mode": "approve",
        },
    )
    assert resp.status_code == 200
    assert resp.json()["ok"] is True

    config = client.get("/api/config").json()
    assert config["agent"]["max_iterations"] == 20
    assert config["agent"]["compaction_enabled"] is False
    assert config["agent"]["max_context_tokens"] == 64000
    assert config["agent"]["max_context_tokens_auto"] is False
    assert config["agent"]["reserve_tokens"] == 2000
    assert config["agent"]["keep_recent_tokens"] == 6000
    assert config["agent"]["approval_mode"] == "approve"


def test_save_agent_config_auto_context(client, isolated_config: Path):
    """When max_context_tokens_auto is True, max_context_tokens should be 0."""
    resp = client.put(
        "/api/config/agent",
        json={
            "max_iterations": 30,
            "compaction_enabled": True,
            "max_context_tokens": 64000,
            "max_context_tokens_auto": True,
            "reserve_tokens": 4000,
            "keep_recent_tokens": 8000,
            "approval_mode": "allow_all",
        },
    )
    assert resp.status_code == 200

    # Read the raw config to verify 0 is stored
    import json

    raw = json.loads(isolated_config.read_text())
    assert raw["max_context_tokens"] == 0


def test_save_agent_config_manual_context(client, isolated_config: Path):
    """When max_context_tokens_auto is False, max_context_tokens should be persisted."""
    resp = client.put(
        "/api/config/agent",
        json={
            "max_iterations": 30,
            "compaction_enabled": True,
            "max_context_tokens": 32000,
            "max_context_tokens_auto": False,
            "reserve_tokens": 4000,
            "keep_recent_tokens": 8000,
            "approval_mode": "allow_all",
        },
    )
    assert resp.status_code == 200

    import json

    raw = json.loads(isolated_config.read_text())
    assert raw["max_context_tokens"] == 32000


# ────────────────────────────────────────────────────────────────────
# 4) PUT /api/config/yonsuite
# ────────────────────────────────────────────────────────────────────


def test_save_yonsuite_config(client):
    resp = client.put(
        "/api/config/yonsuite",
        json={
            "app_key": "test-app-key",
            "app_secret": "test-secret",
            "tenant_id": "t-12345",
            "gateway_url": "https://custom.gateway.com",
        },
    )
    assert resp.status_code == 200
    assert resp.json()["ok"] is True

    config = client.get("/api/config").json()
    # Values should be masked in the response
    assert config["yonsuite"]["app_key"] != ""
    assert config["yonsuite"]["app_secret"] != ""
    assert config["yonsuite"]["tenant_id"] != ""


def test_save_yonsuite_config_empty_values_unchanged(client):
    """Empty values should not overwrite existing previously-set values."""
    # First set values
    client.put(
        "/api/config/yonsuite",
        json={
            "app_key": "key1",
            "app_secret": "secret1",
            "tenant_id": "tenant1",
            "gateway_url": "https://gw1.com",
        },
    )
    # Then send empty values — all are guarded by ``if body.xxx:`` in the
    # handler, so empty strings should be ignored.
    resp = client.put(
        "/api/config/yonsuite",
        json={
            "app_key": "",
            "app_secret": "",
            "tenant_id": "",
            "gateway_url": "",
        },
    )
    assert resp.status_code == 200

    config = client.get("/api/config").json()
    # Previously set values should survive
    assert "https://gw1.com" in config["yonsuite"]["gateway_url"]


# ────────────────────────────────────────────────────────────────────
# 5) GET /api/config/providers
# ────────────────────────────────────────────────────────────────────


def test_get_providers_returns_list(client):
    resp = client.get("/api/config/providers")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    assert len(data) >= 1


def test_get_providers_contains_openai(client):
    resp = client.get("/api/config/providers")
    names = {p["name"] for p in resp.json()}
    assert "OpenAI" in names


def test_get_providers_has_custom(client):
    resp = client.get("/api/config/providers")
    names = {p["name"] for p in resp.json()}
    assert "自定义" in names


def test_get_providers_shape(client):
    resp = client.get("/api/config/providers")
    for p in resp.json():
        assert "name" in p
        assert "base_url" in p
        assert "models" in p
        assert "api_key_label" in p
        assert "api_key_placeholder" in p
        assert isinstance(p["models"], list)


def test_get_providers_model_shape(client):
    resp = client.get("/api/config/providers")
    openai = next(p for p in resp.json() if p["name"] == "OpenAI")
    for m in openai["models"]:
        assert "id" in m
        assert "context_length" in m
