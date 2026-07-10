"""
按 config.json 里的 erp_clients.nc 状态决定 mcp-nc 是否启动
"""

from __future__ import annotations
import logging

from mcp_server.nc_mcp.config import build_nc_mcp_config

logger = logging.getLogger(__name__)

NC_MCP_NAME = "mcp-nc"


async def sync_nc_mcp() -> None:
    """
    每次配置变更后调用, 确保 mcp-nc 状态与 erp_clients.nc.enabled 一致

    行为:
    - enabled=True: 启动 nc-mcp-server, 工具自动注册到 LLM
    - enabled=False: 停止 nc-mcp-server, 工具从 LLM 视野消失
    - 配置不存在: no-op
    """
    # 延迟导入避免循环依赖
    from agent.config_manager import get_config
    from agent.tools.mcp_manager import get_server_statuses, reconnect_server

    config = get_config()
    nc_cfg = config.get("erp_clients", {}).get("nc")

    if nc_cfg is None:
        logger.debug("erp_clients.nc 不存在, 跳过 sync_nc_mcp")
        return

    enabled = bool(nc_cfg.get("enabled", False))
    target = build_nc_mcp_config(nc_cfg, enabled=enabled)

    statuses = {s["name"]: s for s in get_server_statuses()}
    current = statuses.get(NC_MCP_NAME, {})
    current_status = current.get("status", "disconnected")

    if enabled and current_status != "connected":
        logger.info("启动 mcp-nc (host=%s)", nc_cfg.get("host"))
        await reconnect_server(NC_MCP_NAME, target)
    elif not enabled and current_status == "connected":
        logger.info("停止 mcp-nc")
        await reconnect_server(NC_MCP_NAME, {**target, "enabled": False})
    else:
        logger.debug("mcp-nc 状态已同步 (enabled=%s, current=%s)", enabled, current_status)
