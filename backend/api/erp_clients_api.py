"""
ERP 客户端配置 REST API (v1.5.0)

端点:
- GET    /api/config/erp-clients              列出所有
- GET    /api/config/erp-clients/{name}       获取单个
- PUT    /api/config/erp-clients/{name}       更新单个 (自动加密 secret)
- POST   /api/config/erp-clients/{name}/test  测试连接
- GET    /api/config/mcp-servers              列出所有 MCP server 状态
- POST   /api/config/mcp-servers/{name}/toggle 启用/禁用
"""
from __future__ import annotations
import json
import logging
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from agent import config_manager
from agent.config_model import _encrypt

logger = logging.getLogger(__name__)
router = APIRouter()

# secret 字段在 PUT 时自动加密
SECRET_FIELDS = {
    "yonsuite": ["app_key", "app_secret"],
    "nc": ["password"],
}


class ERPPutRequest(BaseModel):
    """ERP 配置 PUT body (v1.5.0)"""
    enabled: bool | None = None
    # yonsuite 字段
    tenant_id: str | None = None
    app_key: str | None = None
    app_secret: str | None = None
    base_url: str | None = None
    # nc 字段
    host: str | None = None
    port: str | None = None
    service: str | None = None
    user: str | None = None
    password: str | None = None
    max_rows: int | None = None


def _read_raw_config() -> dict:
    """从 config.json 读原始 dict (不走 Pydantic, 避免 erp_clients 字段不在 AppConfig 里)"""
    try:
        return json.loads(config_manager.CONFIG_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def _write_raw_config(raw: dict) -> None:
    """写原始 dict 到 config.json"""
    config_manager.CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
    config_manager.atomic_json_write(config_manager.CONFIG_FILE, raw)


def _mask_secrets(name: str, cfg: dict) -> dict:
    """脱敏 secret 字段 (已加密的不 mask, 明文的 mask)"""
    masked = dict(cfg)
    for f in SECRET_FIELDS.get(name, []):
        if f in masked and isinstance(masked[f], str) and not masked[f].startswith("encrypted:"):
            masked[f] = "***"
    return masked


@router.get("/api/config/erp-clients")
async def list_erp_clients() -> dict:
    raw = _read_raw_config()
    erp_clients = raw.get("erp_clients", {})
    return {name: _mask_secrets(name, cfg) for name, cfg in erp_clients.items()}


@router.get("/api/config/erp-clients/{name}")
async def get_erp_client(name: str) -> dict:
    raw = _read_raw_config()
    erp_clients = raw.get("erp_clients", {})
    if name not in erp_clients:
        raise HTTPException(404, f"ERP client {name!r} not found")
    return _mask_secrets(name, erp_clients[name])


@router.put("/api/config/erp-clients/{name}")
async def put_erp_client(name: str, body: ERPPutRequest) -> dict:
    raw = _read_raw_config()
    erp_clients = raw.setdefault("erp_clients", {})
    if name not in erp_clients:
        erp_clients[name] = {}
    cfg = erp_clients[name]

    updates = body.model_dump(exclude_none=True)
    secret_fields = SECRET_FIELDS.get(name, [])
    for k, v in updates.items():
        if k in secret_fields and v and not v.startswith("encrypted:") and v != "***":
            cfg[k] = _encrypt(v)
        else:
            cfg[k] = v

    _write_raw_config(raw)

    # 触发 NC MCP 同步 (如果改了 nc)
    if name == "nc":
        try:
            from mcp_server.nc_mcp.mcp_starter import sync_nc_mcp
            await sync_nc_mcp()
        except Exception as e:
            logger.warning("sync_nc_mcp 失败: %s", e)

    return _mask_secrets(name, cfg)


@router.post("/api/config/erp-clients/{name}/test")
async def test_erp_client(name: str) -> dict:
    """测试连接"""
    if name == "yonsuite":
        try:
            from agent.erp_clients.yonsuite import YonSuiteClient
            from agent.config_manager import get_erp_config
            cfg = get_erp_config("yonsuite")
            client = YonSuiteClient(cfg)
            ok = client.health_check()
            return {"ok": bool(ok)}
        except Exception as e:
            return {"ok": False, "error": str(e)}
    elif name == "nc":
        try:
            from agent.tools.mcp_manager import get_server_statuses
            statuses = {s["name"]: s for s in get_server_statuses()}
            nc_status = statuses.get("mcp-nc", {}).get("status", "disconnected")
            if nc_status == "connected":
                return {"ok": True}
            return {"ok": False, "error": f"mcp-nc 状态: {nc_status}, 确认已装 nc-mcp-server 包"}
        except Exception as e:
            return {"ok": False, "error": str(e)}
    raise HTTPException(404, f"Unknown ERP {name!r}")


@router.get("/api/config/mcp-servers")
async def list_mcp_servers() -> list:
    from agent.tools.mcp_manager import get_server_statuses
    return get_server_statuses()


@router.post("/api/config/mcp-servers/{name}/toggle")
async def toggle_mcp_server(name: str) -> dict:
    """启用/禁用某个 MCP server"""
    from agent.tools.mcp_manager import reconnect_server, get_server_statuses
    statuses = {s["name"]: s for s in get_server_statuses()}
    if name not in statuses:
        raise HTTPException(404, f"MCP server {name!r} not found")
    current = statuses[name]
    new_enabled = current.get("status") != "connected"
    cfg = current.get("config", {})
    cfg["enabled"] = new_enabled
    await reconnect_server(name, cfg)
    return {"name": name, "enabled": new_enabled}
