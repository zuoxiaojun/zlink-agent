"""MCP server management REST API."""

from fastapi import APIRouter, HTTPException
from backend.schemas.mcp import MCPServerConfig, MCPServerStatus, MCPTestResult
from agent import config_manager
from agent.tools.mcp_manager import (
    connect_server,
    disconnect_server,
    reload_all_servers,
    get_server_statuses,
    test_server_connection,
    _build_config_dict,
)

router = APIRouter(prefix="/api/mcp", tags=["mcp"])


@router.get("/servers", response_model=list[MCPServerStatus])
def list_servers():
    return [MCPServerStatus(**s) for s in get_server_statuses()]


@router.post("/servers", status_code=201)
async def add_server(body: MCPServerConfig):
    cfg = config_manager.load()
    servers = cfg.get("mcp_servers", {})
    if body.name in servers:
        raise HTTPException(status_code=409, detail=f"Server '{body.name}' already exists")
    config_dict = _build_config_dict(body)
    servers[body.name] = config_dict
    config_manager.save(cfg)
    await connect_server(body.name, config_dict)
    return {"ok": True}


@router.delete("/servers/{name}", status_code=204)
async def delete_server(name: str):
    cfg = config_manager.load()
    servers = cfg.get("mcp_servers", {})
    if name not in servers:
        raise HTTPException(status_code=404, detail=f"Server '{name}' not found")
    await disconnect_server(name)
    del servers[name]
    config_manager.save(cfg)


@router.put("/servers/{name}/toggle")
async def toggle_server(name: str):
    cfg = config_manager.load()
    servers = cfg.get("mcp_servers", {})
    if name not in servers:
        raise HTTPException(status_code=404, detail=f"Server '{name}' not found")
    current = servers[name]
    new_enabled = not current.get("enabled", True)
    current["enabled"] = new_enabled
    config_manager.save(cfg)
    if new_enabled:
        await connect_server(name, current)
    else:
        await disconnect_server(name)
    return {"ok": True, "enabled": new_enabled}


@router.post("/servers/{name}/test", response_model=MCPTestResult)
async def test_server(name: str, body: MCPServerConfig | None = None):
    if body:
        config_dict = _build_config_dict(body)
    else:
        cfg = config_manager.load()
        servers = cfg.get("mcp_servers", {})
        if name not in servers:
            raise HTTPException(status_code=404, detail=f"Server '{name}' not found")
        config_dict = servers[name]
    result = await test_server_connection(name, config_dict)
    return MCPTestResult(**result)


@router.post("/reload")
async def reload_servers():
    result = await reload_all_servers()
    return result
