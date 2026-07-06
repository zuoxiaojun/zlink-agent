"""MCP server management REST API."""

from fastapi import APIRouter, HTTPException

from agent import config_manager
from agent.config_model import MCPServerEntry
from agent.tools.mcp_manager import (
    _build_config_dict,
    connect_server,
    disconnect_server,
    get_server_statuses,
    reload_all_servers,
    test_server_connection,
)
from backend.schemas.mcp import MCPServerConfig, MCPServerStatus, MCPTestResult

router = APIRouter(prefix="/api/mcp", tags=["mcp"])


def _check_builtin(name: str, servers: dict):
    entry = servers.get(name)
    if entry and getattr(entry, "builtin", False):
        raise HTTPException(status_code=403, detail=f"内置服务器「{name}」不允许修改或删除")


def _to_dict(entry: MCPServerEntry) -> dict:
    return entry.model_dump()


def _to_entry(d: dict) -> MCPServerEntry:
    return MCPServerEntry(**d)


@router.get("/servers", response_model=list[MCPServerStatus])
def list_servers():
    return [MCPServerStatus(**s) for s in get_server_statuses()]


@router.post("/servers", status_code=201)
async def add_server(body: MCPServerConfig):
    cfg = config_manager.load()
    servers = cfg.mcp_servers
    if body.name in servers:
        raise HTTPException(status_code=409, detail=f"Server '{body.name}' already exists")
    config_dict = _build_config_dict(body)
    servers[body.name] = _to_entry(config_dict)
    config_manager.save(cfg)
    await connect_server(body.name, config_dict)
    return {"ok": True}


@router.put("/servers/{name}")
async def update_server(name: str, body: MCPServerConfig):
    cfg = config_manager.load()
    servers = cfg.mcp_servers
    if name not in servers:
        raise HTTPException(status_code=404, detail=f"Server '{name}' not found")
    _check_builtin(name, servers)
    await disconnect_server(name)
    config_dict = _build_config_dict(body)
    config_dict["enabled"] = servers[name].enabled
    config_dict["builtin"] = servers[name].builtin
    servers[name] = _to_entry(config_dict)
    config_manager.save(cfg)
    if config_dict["enabled"]:
        await connect_server(name, config_dict)
    return {"ok": True}


@router.delete("/servers/{name}", status_code=204)
async def delete_server(name: str):
    cfg = config_manager.load()
    servers = cfg.mcp_servers
    if name not in servers:
        raise HTTPException(status_code=404, detail=f"Server '{name}' not found")
    _check_builtin(name, servers)
    await disconnect_server(name)
    del servers[name]
    config_manager.save(cfg)


@router.put("/servers/{name}/toggle")
async def toggle_server(name: str):
    cfg = config_manager.load()
    servers = cfg.mcp_servers
    if name not in servers:
        raise HTTPException(status_code=404, detail=f"Server '{name}' not found")
    entry = servers[name]
    new_enabled = not entry.enabled
    entry.enabled = new_enabled
    config_manager.save(cfg)
    if new_enabled:
        await connect_server(name, _to_dict(entry))
    else:
        await disconnect_server(name)
    return {"ok": True, "enabled": new_enabled}


@router.post("/servers/{name}/reconnect")
async def reconnect_server(name: str):
    cfg = config_manager.load()
    servers = cfg.mcp_servers
    if name not in servers:
        raise HTTPException(status_code=404, detail=f"Server '{name}' not found")
    await disconnect_server(name)
    await connect_server(name, _to_dict(servers[name]))
    return {"ok": True}


@router.post("/servers/{name}/test", response_model=MCPTestResult)
async def test_server(name: str, body: MCPServerConfig | None = None):
    if body:
        config_dict = _build_config_dict(body)
    else:
        cfg = config_manager.load()
        servers = cfg.mcp_servers
        if name not in servers:
            raise HTTPException(status_code=404, detail=f"Server '{name}' not found")
        config_dict = _to_dict(servers[name])
    result = await test_server_connection(name, config_dict)
    return MCPTestResult(**result)


@router.post("/reload")
async def reload_servers():
    result = await reload_all_servers()
    return result
