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


def _apply_erp_env(name: str, cfg: dict):
    """将 ERP 配置注入环境变量，供内置工具 (agent/tools/erp_*_tools.py) 读取。"""
    import os

    if name == "nc":
        host = cfg.get("host", "")
        if host:
            os.environ["ORACLE_HOST"] = host
            os.environ["ORACLE_PORT"] = str(cfg.get("port", "") or "")
            os.environ["ORACLE_SERVICE"] = str(cfg.get("service", "") or "")
            os.environ["ORACLE_USER"] = str(cfg.get("user", "") or "")
            os.environ["ORACLE_PASSWORD"] = str(cfg.get("password", "") or "")
            os.environ["NC_MCP_MAX_ROWS"] = str(cfg.get("max_rows", 200) or 200)
    elif name == "yonsuite":
        app_key = cfg.get("app_key", "")
        app_secret = cfg.get("app_secret", "")
        tenant_id = cfg.get("tenant_id", "")
        gateway_url = cfg.get("base_url", "https://c2.yonyoucloud.com/iuap-api-gateway")
        if app_key:
            os.environ["YONSUITE_APP_KEY"] = app_key
            os.environ["YONSUITE_APP_SECRET"] = app_secret
            os.environ["YONSUITE_TENANT_ID"] = tenant_id
            os.environ["YONSUITE_GATEWAY_URL"] = gateway_url
    elif name == "u8":
        host = cfg.get("host", "")
        if host:
            os.environ["U8_HOST"] = host
            os.environ["U8_PORT"] = str(cfg.get("port", "") or "")
            os.environ["U8_DATABASE"] = str(cfg.get("database", "") or "")
            os.environ["U8_USER"] = str(cfg.get("user", "") or "")
            os.environ["U8_PASSWORD"] = str(cfg.get("password", "") or "")
            os.environ["U8_MAX_ROWS"] = str(cfg.get("max_rows", 500) or 500)

    elif name == "u9c":
        host = cfg.get("host", "")
        if host:
            os.environ["U9C_HOST"] = host
            os.environ["U9C_PORT"] = str(cfg.get("port", "") or "")
            os.environ["U9C_DATABASE"] = str(cfg.get("database", "") or "")
            os.environ["U9C_USER"] = str(cfg.get("user", "") or "")
            os.environ["U9C_PASSWORD"] = str(cfg.get("password", "") or "")
            os.environ["U9C_MAX_ROWS"] = str(cfg.get("max_rows", 500) or 500)


# secret 字段在 PUT 时自动加密
SECRET_FIELDS = {
    "yonsuite": ["app_key", "app_secret"],
    "nc": ["password"],
    "u8": ["password"],
    "u9c": ["password"],
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
    # u8 字段
    database: str | None = None


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
    """列出所有 ERP 配置（含 .env 中的密钥，已脱敏）"""
    cfg = config_manager.load()
    erp_clients = cfg.erp_clients or {}
    return {name: _mask_secrets(name, ecfg) for name, ecfg in erp_clients.items()}


@router.get("/api/config/erp-clients/{name}")
async def get_erp_client(name: str) -> dict:
    """获取单个 ERP 配置（含 .env 中的密钥，已脱敏）"""
    cfg = config_manager.load()
    if name == "yonsuite":
        ys_cfg = cfg.erp_clients.get("yonsuite", {})
        if not isinstance(ys_cfg, dict):
            ys_cfg = {}
        return _mask_secrets(
            name,
            {
                "enabled": ys_cfg.get("enabled", False),
                "tenant_id": ys_cfg.get("tenant_id") or cfg.ys_tenant_id or "",
                "app_key": ys_cfg.get("app_key") or "",
                "app_secret": ys_cfg.get("app_secret") or "",
                "base_url": ys_cfg.get("base_url") or cfg.ys_gateway_url or "",
            },
        )
    if name == "nc":
        raw = _read_raw_config()
        ecfg = cfg.erp_clients.get("nc", {}) if isinstance(cfg.erp_clients.get("nc"), dict) else {}
        if not ecfg.get("host"):
            # 尝试从 mcp_servers 反向回读
            mcp_cfg = raw.get("mcp_servers", {}).get("mcp-nc")
            if mcp_cfg:
                return _mask_secrets(name, _mcp_env_to_erp_config(mcp_cfg))
        return _mask_secrets(
            name,
            {
                "enabled": ecfg.get("enabled", False),
                "host": ecfg.get("host", ""),
                "port": ecfg.get("port", ""),
                "service": ecfg.get("service", ""),
                "user": ecfg.get("user", ""),
                "password": ecfg.get("password", ""),
                "max_rows": ecfg.get("max_rows", 500),
            },
        )
    if name == "u8":
        ecfg = cfg.erp_clients.get("u8", {}) if isinstance(cfg.erp_clients.get("u8"), dict) else {}
        return _mask_secrets(
            name,
            {
                "enabled": ecfg.get("enabled", False),
                "host": ecfg.get("host", ""),
                "port": ecfg.get("port", ""),
                "database": ecfg.get("database", ""),
                "user": ecfg.get("user", ""),
                "password": ecfg.get("password", ""),
                "max_rows": ecfg.get("max_rows", 200),
            },
        )
    if name == "u9c":
        ecfg = cfg.erp_clients.get("u9c", {}) if isinstance(cfg.erp_clients.get("u9c"), dict) else {}
        return _mask_secrets(
            name,
            {
                "enabled": ecfg.get("enabled", False),
                "host": ecfg.get("host", ""),
                "port": ecfg.get("port", ""),
                "database": ecfg.get("database", ""),
                "user": ecfg.get("user", ""),
                "password": ecfg.get("password", ""),
                "max_rows": ecfg.get("max_rows", 200),
            },
        )
        raise HTTPException(404, f"ERP client {name!r} not found")


@router.put("/api/config/erp-clients/{name}")
async def put_erp_client(name: str, body: ERPPutRequest) -> dict:
    cfg = config_manager.load()
    erp_clients = cfg.erp_clients
    if name not in erp_clients or not isinstance(erp_clients[name], dict):
        erp_clients[name] = {}

    updates = body.model_dump(exclude_none=True)
    secret_fields = SECRET_FIELDS.get(name, [])
    for k, v in updates.items():
        if k in secret_fields:
            if v == "***":
                continue  # 前端脱敏占位符，跳过
            if v:
                erp_clients[name][k] = v
        else:
            erp_clients[name][k] = v

    cfg.erp_clients = erp_clients
    config_manager.save(cfg)

    _apply_erp_env(name, erp_clients.get(name, {}))

    return await get_erp_client(name)


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
            from agent.config_manager import get_erp_config

            cfg = get_erp_config("nc")
            host = cfg.get("host", "")
            port = cfg.get("port", "")
            user = cfg.get("user", "")
            password = cfg.get("password", "")
            service = cfg.get("service", "")
            if not all([host, port, user, password, service]):
                return {"ok": False, "error": "NC 配置不完整，请填写所有连接字段"}

            import oracledb

            conn = oracledb.connect(user=user, password=password, host=host, port=int(port), service_name=service)
            cursor = conn.cursor()
            cursor.execute("SELECT 1 FROM DUAL")
            conn.close()
            return {"ok": True}
        except Exception as e:
            return {"ok": False, "error": str(e)}
    elif name == "u8":
        try:
            from agent.config_manager import get_erp_config

            cfg = get_erp_config("u8")
            host = cfg.get("host", "")
            port = cfg.get("port", "")
            database = cfg.get("database", "")
            user = cfg.get("user", "")
            password = cfg.get("password", "")
            if not all([host, port, database, user, password]):
                return {"ok": False, "error": "U8 配置不完整，请填写所有连接字段"}

            import pymssql

            conn = pymssql.connect(
                server=host,
                port=int(port),  # type: ignore[arg-type] — pymssql 存根标注 str 但实际接受 int
                database=database,
                user=user,
                password=password,
                timeout=10,
            )
            cursor = conn.cursor()
            cursor.execute("SELECT 1")
            conn.close()
            return {"ok": True}
        except Exception as e:
            return {"ok": False, "error": str(e)}
    elif name == "u9c":
        try:
            from agent.config_manager import get_erp_config

            cfg = get_erp_config("u9c")
            host = cfg.get("host", "")
            port = cfg.get("port", "")
            database = cfg.get("database", "")
            user = cfg.get("user", "")
            password = cfg.get("password", "")
            if not all([host, port, database, user, password]):
                return {"ok": False, "error": "U9C 配置不完整，请填写所有连接字段"}

            import pymssql

            conn = pymssql.connect(
                server=host,
                port=int(port),  # type: ignore[arg-type] — pymssql 存根标注 str 但实际接受 int
                database=database,
                user=user,
                password=password,
                timeout=10,
            )
            cursor = conn.cursor()
            cursor.execute("SELECT 1")
            conn.close()
            return {"ok": True}
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
    try:
        raw = json.loads(config_manager.CONFIG_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        raw = {}
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
