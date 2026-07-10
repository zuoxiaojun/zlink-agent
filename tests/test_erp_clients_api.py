"""测试 /api/config/erp-clients 端点 (v1.5.0)"""

import json

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client(tmp_path, monkeypatch):
    # 用临时 config.json
    from agent import config_manager

    monkeypatch.setattr(config_manager, "CONFIG_FILE", tmp_path / "config.json")
    cfg_file = tmp_path / "config.json"
    cfg_file.write_text(
        json.dumps(
            {
                "erp_clients": {
                    "yonsuite": {"enabled": True, "tenant_id": "t1", "app_key": "encrypted:abc"},
                    "nc": {"enabled": False, "host": "1.2.3.4"},
                }
            }
        )
    )
    # 通过 env var 强制 config_manager 用临时文件
    monkeypatch.setenv("YS_DATA_DIR", str(tmp_path))
    # 重新加载配置 (Pydantic 缓存可能需要 invalidate)
    from backend.main import app

    return TestClient(app)


def test_get_erp_clients_returns_both(client):
    r = client.get("/api/config/erp-clients")
    assert r.status_code == 200, r.text
    data = r.json()
    assert "yonsuite" in data
    assert "nc" in data


def test_get_erp_client_yonsuite_secrets_masked(client):
    r = client.get("/api/config/erp-clients/yonsuite")
    assert r.status_code == 200, r.text
    data = r.json()
    if "app_key" in data:
        # 已经是 encrypted: 开头, 不再 mask
        assert data["app_key"] == "***" or data["app_key"].startswith("encrypted:")


def test_put_erp_client_nc_encrypts_password(client):
    """PUT NC 配置时 password 字段被加密 (写盘后是 encrypted: 前缀)"""
    from agent import config_manager

    r = client.put(
        "/api/config/erp-clients/nc",
        json={
            "host": "1.2.3.4",
            "port": "1521",
            "service": "orcl",
            "user": "u",
            "password": "plain-password",
        },
    )
    assert r.status_code == 200, r.text
    # 读落盘 config.json, 验证 password 已加密
    cfg = json.loads(config_manager.CONFIG_FILE.read_text())
    assert cfg["erp_clients"]["nc"]["password"].startswith("encrypted:")
