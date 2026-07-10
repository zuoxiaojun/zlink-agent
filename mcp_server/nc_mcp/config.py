"""
把 config.json 里的 erp_clients.nc 用户友好配置
转换为 nc-mcp-server 进程需要的 ORACLE_* 环境变量
"""

from __future__ import annotations
from typing import Any


def build_nc_mcp_env(erp_config: dict[str, Any]) -> dict[str, str]:
    """转换配置: erp_clients.nc.* → ORACLE_*"""
    return {
        "ORACLE_HOST": str(erp_config["host"]),
        "ORACLE_PORT": str(erp_config["port"]),
        "ORACLE_SERVICE": str(erp_config["service"]),
        "ORACLE_USER": str(erp_config["user"]),
        "ORACLE_PASSWORD": str(erp_config["password"]),
        "NC_MCP_MAX_ROWS": str(erp_config.get("max_rows", 200)),
    }


def build_nc_mcp_config(erp_config: dict[str, Any], enabled: bool) -> dict[str, Any]:
    """构造 mcp_manager 需要的 config dict"""
    return {
        "transport": "stdio",
        "command": "nc-mcp-server",
        "args": [],
        "env": build_nc_mcp_env(erp_config),
        "builtin": False,
        "enabled": enabled,
        "install_hint": "pip install zlink-agent[nc]",
    }
