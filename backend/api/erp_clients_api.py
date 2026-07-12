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
    """脱敏 secret 字段"""
    masked = dict(cfg)
    for f in SECRET_FIELDS.get(name, []):
        if f in masked and isinstance(masked[f], str) and masked[f]:
            masked[f] = "***"
    return masked


def _mcp_env_to_erp_config(mcp_cfg: dict) -> dict:
    """从 mcp_servers.mcp-nc.env 反向构造 erp_clients.nc 样式的配置"""
    env = mcp_cfg.get("env", {})
    max_rows_raw = env.get("NC_MCP_MAX_ROWS", "200")
    try:
        max_rows = int(max_rows_raw)
    except (ValueError, TypeError):
        max_rows = 200
    return {
        "enabled": bool(mcp_cfg.get("enabled", False)),
        "host": env.get("ORACLE_HOST", ""),
        "port": env.get("ORACLE_PORT", ""),
        "service": env.get("ORACLE_SERVICE", ""),
        "user": env.get("ORACLE_USER", ""),
        "password": env.get("ORACLE_PASSWORD", ""),
        "max_rows": max_rows,
    }


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
        # 尝试从 mcp_servers 反向回读（兼容旧 MCP 管理页保存的配置）
        mcp_cfg = raw.get("mcp_servers", {}).get(f"mcp-{name}")
        if name == "yonsuite":
            return {"enabled": False, "tenant_id": "", "app_key": "", "app_secret": "", "base_url": ""}
        if name == "nc":
            if mcp_cfg:
                return _mcp_env_to_erp_config(mcp_cfg)
            return {
                "enabled": False,
                "host": "",
                "port": "",
                "service": "",
                "user": "",
                "password": "",
                "max_rows": 200,
            }
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
        if k in secret_fields:
            if v == "***":
                continue  # 前端脱敏占位符，跳过
            if v:
                cfg[k] = v
                config_manager._save_erp_secret(name, k, v)
            # else: v 为空字符串，跳过更新（保留已有值）
        else:
            cfg[k] = v

    # Strip secrets from raw dict before writing to config.json
    for sf in secret_fields:
        if name in erp_clients:
            ecfg = erp_clients[name]
            if sf in ecfg:
                del ecfg[sf]

    _write_raw_config(raw)

    # 触发 MCP 同步
    try:
        if name == "nc":
            from mcp_server.nc_mcp.mcp_starter import sync_nc_mcp

            await sync_nc_mcp()
        elif name == "yonsuite":
            # 同步 YonSuite 凭证到 MCP server 环境变量（立即生效，无需重启）
            from agent.config_manager import get_erp_config
            from agent.tools.mcp_manager import connect_server, disconnect_server, get_server_statuses

            ys_cfg = get_erp_config("yonsuite")
            statuses = {s["name"]: s for s in get_server_statuses()}
            ys_mcp = statuses.get("yonsuite")
            if ys_mcp and ys_mcp.get("status") == "connected":
                from agent.config_model import MCPServerEntry

                ys_mcp_cfg = MCPServerEntry(
                    transport="stdio",
                    command=ys_mcp.get("command", ""),
                    args=ys_mcp.get("args", []),
                    enabled=bool(ys_cfg.get("enabled", False)),
                    env={
                        "YONSUITE_APP_KEY": ys_cfg.get("app_key", ""),
                        "YONSUITE_APP_SECRET": ys_cfg.get("app_secret", ""),
                        "YONSUITE_TENANT_ID": ys_cfg.get("tenant_id", ""),
                        "YONSUITE_GATEWAY_URL": ys_cfg.get("base_url") or "https://c2.yonyoucloud.com/iuap-api-gateway",
                    },
                    builtin=True,
                )
                await disconnect_server("yonsuite")
                await connect_server("yonsuite", ys_mcp_cfg.model_dump())
    except Exception as e:
        logger.warning("MCP 同步失败 (%s): %s", name, e)

    return _mask_secrets(name, cfg)


@router.post("/api/config/erp-clients/{name}/test")
async def test_erp_client(name: str) -> dict:
    """测试连接"""
    if name == "yonsuite":
        try:
            from agent.config_manager import get_erp_config
            from agent.erp_clients.yonsuite import YonSuiteClient

            cfg = get_erp_config("yonsuite")
            # cfg keys: tenant_id, app_key, app_secret, base_url
            # YonSuiteClient 参数: app_key, app_secret, tenant_id, gateway_url
            client = YonSuiteClient(
                app_key=cfg.get("app_key"),
                app_secret=cfg.get("app_secret"),
                tenant_id=cfg.get("tenant_id"),
                gateway_url=cfg.get("base_url") or cfg.get("gateway_url"),
            )
            token = client.get_access_token()
            return {"ok": bool(token)}
        except Exception as e:
            return {"ok": False, "error": str(e)}
    elif name == "nc":
        try:
            from agent.tools.mcp_manager import get_server_statuses

            statuses = {s["name"]: s for s in get_server_statuses()}
            nc_status = statuses.get("mcp-nc", {}).get("status", "disconnected")
            if nc_status == "connected":
                return {"ok": True}
            return {"ok": False, "error": f"mcp-nc 状态: {nc_status}，请先在 ERP 连接页启用 NC"}
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
    import json

    from agent import config_manager
    from agent.tools.mcp_manager import connect_server, disconnect_server, get_server_statuses

    statuses = {s["name"]: s for s in get_server_statuses()}
    if name not in statuses:
        raise HTTPException(404, f"MCP server {name!r} not found")
    current = statuses[name]
    new_enabled = current.get("status") != "connected"

    # 持久化到 config.json
    raw = json.loads(config_manager.CONFIG_FILE.read_text(encoding="utf-8"))
    servers = raw.setdefault("mcp_servers", {})
    servers.setdefault(name, {})["enabled"] = new_enabled
    config_manager.atomic_json_write(config_manager.CONFIG_FILE, raw)

    # 启停
    if new_enabled:
        cfg = servers[name]
        await connect_server(name, cfg)
    else:
        await disconnect_server(name)

    return {"name": name, "enabled": new_enabled}
