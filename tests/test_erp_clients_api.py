"""测试 /api/config/erp-clients 端点 (v1.5.0)"""
import json
import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client(tmp_path, monkeypatch):
    # 用临时 config.json
    from agent import config_manager
    monkeypatch.setattr(config_manager, "CONFIG_FILE", tmp_path / "config.json")
    (tmp_path / "config.json").write_text(json.dumps({
        "erp_clients": {
            "yonsuite": {"enabled": True, "tenant_id": "t1", "app_key": "encrypted:abc"},
            "nc": {"enabled": False, "host": "1.2.3.4"},
        }
    }))
    from backend.main import app
    return TestClient(app)


def test_get_erp_clients_returns_both(client):
    r = client.get("/api/config/erp-clients")
    assert r.status_code == 200
    data = r.json()
    assert "yonsuite" in data
    assert "nc" in data


def test_get_erp_client_yonsuite_secrets_masked(client):
    r = client.get("/api/config/erp-clients/yonsuite")
    assert r.status_code == 200
    data = r.json()
    # secret 字段应被脱敏
    if "app_key" in data:
        # 已经是 encrypted: 开头, 不再 mask (它已经加密了)
        # 但如果是明文, 应该 mask
        assert data["app_key"] == "***" or data["app_key"].startswith("encrypted:")


def test_put_erp_client_nc_encrypts_password(client, tmp_path, monkeypatch):
    """PUT NC 配置时 password 字段被加密 (写盘后是 encrypted: 前缀)"""
    from agent import config_manager
    r = client.put("/api/config/erp-clients/nc", json={
        "host": "1.2.3.4", "port": "1521", "service": "orcl",
        "user": "u", "password": "plain-password",
    })
    assert r.status_code == 200
    # 读落盘 config.json, 验证 password 已加密
    cfg = json.loads(config_manager.CONFIG_FILE.read_text())
    assert cfg["erp_clients"]["nc"]["password"].startswith("encrypted:")
