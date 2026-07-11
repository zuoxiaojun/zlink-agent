"""
把 config.json 里的 erp_clients.nc 用户友好配置
转换为 nc-mcp-server 进程需要的 ORACLE_* 环境变量
"""

from __future__ import annotations

from typing import Any


def _decrypt_password(value: str | None) -> str:
    """解密密码 (config_manager 已解密的明文直接返回; 否则再次尝试解密)"""
    if not value:
        return ""
    if value.startswith("encrypted:"):
        try:
            from agent.config_manager import decrypt_secret

            return decrypt_secret(value)
        except Exception:
            return ""
    return value


def build_nc_mcp_env(erp_config: dict[str, Any]) -> dict[str, str]:
    """转换配置: erp_clients.nc.* → ORACLE_*"""
    return {
        "ORACLE_HOST": str(erp_config.get("host", "")),
        "ORACLE_PORT": str(erp_config.get("port", "")),
        "ORACLE_SERVICE": str(erp_config.get("service", "")),
        "ORACLE_USER": str(erp_config.get("user", "")),
        "ORACLE_PASSWORD": _decrypt_password(erp_config.get("password")),
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
