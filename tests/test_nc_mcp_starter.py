"""测试 mcp_server.nc_mcp.mcp_starter 的启停逻辑 (用 asyncio.run 避免 pytest-asyncio 依赖)"""

import asyncio
from unittest.mock import AsyncMock, patch

from agent.config_model import AppConfig


def _run(coro):
    return asyncio.run(coro)


def _make_cfg(erp_clients: dict | None = None) -> AppConfig:
    """Build an AppConfig with optional erp_clients."""
    cfg = AppConfig()
    if erp_clients:
        cfg.erp_clients = erp_clients
    return cfg


def test_sync_nc_mcp_disabled_when_no_config():
    """erp_clients.nc 不存在时, sync_nc_mcp 应该是 no-op"""
    from mcp_server.nc_mcp import mcp_starter

    async def go():
        with (
            patch.object(mcp_starter.config_manager, "load") as mock_load,
            patch.object(mcp_starter, "connect_server", new=AsyncMock()) as mock_connect,
            patch.object(mcp_starter, "disconnect_server", new=AsyncMock()) as mock_disconnect,
            patch.object(mcp_starter, "get_server_statuses", return_value=[]),
        ):
            mock_load.return_value = _make_cfg({})
            await mcp_starter.sync_nc_mcp()
            mock_connect.assert_not_called()
            mock_disconnect.assert_not_called()

    _run(go())


def test_sync_nc_mcp_enabled_starts_server():
    """erp_clients.nc.enabled=True 且有 host 时, 应该启动 mcp-nc"""
    from mcp_server.nc_mcp import mcp_starter

    nc_config = {
        "host": "1.2.3.4",
        "port": "1521",
        "service": "orcl",
        "user": "u",
        "password": "p",
        "enabled": True,
    }

    async def go():
        with (
            patch.object(mcp_starter.config_manager, "load") as mock_load,
            patch.object(mcp_starter, "connect_server", new=AsyncMock()) as mock_connect,
            patch.object(mcp_starter, "disconnect_server", new=AsyncMock()) as mock_disconnect,
            patch.object(mcp_starter, "get_server_statuses", return_value=[]),
            patch.object(mcp_starter, "_persist_mcp_nc_config"),
        ):
            mock_load.return_value = _make_cfg({"nc": nc_config})
            await mcp_starter.sync_nc_mcp()
            mock_connect.assert_called_once()
            args, _ = mock_connect.call_args
            assert args[0] == "mcp-nc"
            target_config = args[1]
            assert target_config.get("enabled") is True
            assert target_config.get("env", {}).get("ORACLE_HOST") == "1.2.3.4"
            mock_disconnect.assert_not_called()

    _run(go())


def test_sync_nc_mcp_disabled_stops_server():
    """erp_clients.nc.enabled=False 时, 应该停止 mcp-nc"""
    from mcp_server.nc_mcp import mcp_starter

    nc_config = {
        "host": "1.2.3.4",
        "enabled": False,
        "port": "1521",
        "service": "orcl",
        "user": "u",
        "password": "p",
    }

    async def go():
        with (
            patch.object(mcp_starter.config_manager, "load") as mock_load,
            patch.object(mcp_starter, "connect_server", new=AsyncMock()) as mock_connect,
            patch.object(mcp_starter, "disconnect_server", new=AsyncMock()) as mock_disconnect,
            patch.object(
                mcp_starter,
                "get_server_statuses",
                return_value=[{"name": "mcp-nc", "status": "connected"}],
            ),
            patch.object(mcp_starter, "_persist_mcp_nc_config"),
        ):
            mock_load.return_value = _make_cfg({"nc": nc_config})
            await mcp_starter.sync_nc_mcp()
            mock_disconnect.assert_called_once()
            mock_connect.assert_not_called()

    _run(go())
