"""
按 config.json 里的 erp_clients.nc 状态决定 mcp-nc 是否启动
"""

from __future__ import annotations

import json
import logging

from agent import config_manager
from agent.tools.mcp_manager import connect_server, disconnect_server, get_server_statuses
from mcp_server.nc_mcp.config import build_nc_mcp_config

logger = logging.getLogger(__name__)

NC_MCP_NAME = "mcp-nc"


def _persist_mcp_nc_config(target: dict) -> None:
    """把 mcp-nc 配置写进 config.json 的 mcp_servers 字段, 确保 get_server_statuses 能发现它"""
    raw = json.loads(config_manager.CONFIG_FILE.read_text(encoding="utf-8"))
    raw.setdefault("mcp_servers", {})[NC_MCP_NAME] = target
    config_manager.atomic_json_write(config_manager.CONFIG_FILE, raw)


async def sync_nc_mcp() -> None:
    """
    每次配置变更后调用, 确保 mcp-nc 状态与 erp_clients.nc.enabled 一致

    行为:
    - enabled=True: 把 mcp-nc 注册到 config.json + 启动进程
    - enabled=False: 停止进程 + 保留配置 (启用时可用)
    - 配置不存在: no-op
    """
    config = config_manager.load().model_dump(mode="json")
    nc_cfg = config.get("erp_clients", {}).get("nc")

    if nc_cfg is None:
        logger.debug("erp_clients.nc 不存在, 跳过 sync_nc_mcp")
        return

    enabled = bool(nc_cfg.get("enabled", False))
    target = build_nc_mcp_config(nc_cfg, enabled=enabled)

    # 先持久化, 确保 get_server_statuses 能找到 mcp-nc
    _persist_mcp_nc_config(target)

    statuses = {s["name"]: s for s in get_server_statuses()}
    current = statuses.get(NC_MCP_NAME, {})
    current_status = current.get("status", "disconnected")

    if enabled and current_status != "connected":
        logger.info("启动 mcp-nc (host=%s)", nc_cfg.get("host"))
        await connect_server(NC_MCP_NAME, target)
    elif not enabled and current_status == "connected":
        logger.info("停止 mcp-nc")
        await disconnect_server(NC_MCP_NAME)
    else:
        logger.debug("mcp-nc 状态已同步 (enabled=%s, current=%s)", enabled, current_status)
