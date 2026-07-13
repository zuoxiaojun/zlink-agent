"""
把 config.json 里的 erp_clients.nc 用户友好配置
转换为 nc-mcp-server 进程需要的 ORACLE_* 环境变量
"""

from __future__ import annotations

from typing import Any


def _password_or_empty(value: str | None) -> str:
    """Return the NC DB password verbatim, or "" if missing.

    Secrets live as plain JSON in ``data/config.json`` (see
    ``agent/config_manager``), so this is a pass-through.
    """
    return value or ""


def build_nc_mcp_env(erp_config: dict[str, Any]) -> dict[str, str]:
    """转换配置: erp_clients.nc.* → ORACLE_*"""
    return {
        "ORACLE_HOST": str(erp_config.get("host", "")),
        "ORACLE_PORT": str(erp_config.get("port", "")),
        "ORACLE_SERVICE": str(erp_config.get("service", "")),
        "ORACLE_USER": str(erp_config.get("user", "")),
        "ORACLE_PASSWORD": _password_or_empty(erp_config.get("password")),
        "NC_MCP_MAX_ROWS": str(erp_config.get("max_rows", 200)),
    }


def build_nc_mcp_config(erp_config: dict[str, Any], enabled: bool) -> dict[str, Any]:
    """构造 mcp_manager 需要的 config dict（使用本地 nc_mcp_server 模块）"""
    import sys

    py_path = sys.executable
    return {
        "transport": "stdio",
        "command": py_path,
        "args": ["-m", "mcp_server.nc_mcp_server"],
        "env": build_nc_mcp_env(erp_config),
        "builtin": True,
        "enabled": enabled,
    }
