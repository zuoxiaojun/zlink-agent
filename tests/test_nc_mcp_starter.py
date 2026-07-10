"""测试 mcp_server.nc_mcp.mcp_starter 的启停逻辑 (用 asyncio.run 避免 pytest-asyncio 依赖)"""
import asyncio
from unittest.mock import patch, AsyncMock


def _run(coro):
    return asyncio.run(coro)


def test_sync_nc_mcp_disabled_when_no_config():
    """erp_clients.nc 不存在时, sync_nc_mcp 应该是 no-op"""
    from mcp_server.nc_mcp import mcp_starter

    async def go():
        with patch.object(mcp_starter, "get_config") as mock_cfg, \
             patch.object(mcp_starter, "reconnect_server", new=AsyncMock()) as mock_reconnect, \
             patch.object(mcp_starter, "get_server_statuses", return_value=[]):
            mock_cfg.return_value = {}  # 没有 erp_clients
            await mcp_starter.sync_nc_mcp()
            mock_reconnect.assert_not_called()
    _run(go())


def test_sync_nc_mcp_enabled_starts_server():
    """erp_clients.nc.enabled=True 且有 host 时, 应该启动 mcp-nc"""
    from mcp_server.nc_mcp import mcp_starter

    nc_config = {
        "host": "1.2.3.4", "port": "1521", "service": "orcl",
        "user": "u", "password": "p", "enabled": True,
    }

    async def go():
        with patch.object(mcp_starter, "get_config") as mock_cfg, \
             patch.object(mcp_starter, "reconnect_server", new=AsyncMock()) as mock_reconnect, \
             patch.object(mcp_starter, "get_server_statuses", return_value=[]):
            mock_cfg.return_value = {"erp_clients": {"nc": nc_config}}
            await mcp_starter.sync_nc_mcp()
            mock_reconnect.assert_called_once()
            args, kwargs = mock_reconnect.call_args
            assert args[0] == "mcp-nc"
            target_config = args[1]
            assert target_config["enabled"] is True
            assert target_config["env"]["ORACLE_HOST"] == "1.2.3.4"
    _run(go())


def test_sync_nc_mcp_disabled_stops_server():
    """erp_clients.nc.enabled=False 时, 应该停止 mcp-nc"""
    from mcp_server.nc_mcp import mcp_starter

    nc_config = {
        "host": "1.2.3.4", "enabled": False,
        "port": "1521", "service": "orcl", "user": "u", "password": "p",
    }

    async def go():
        with patch.object(mcp_starter, "get_config") as mock_cfg, \
             patch.object(mcp_starter, "reconnect_server", new=AsyncMock()) as mock_reconnect, \
             patch.object(mcp_starter, "get_server_statuses", return_value=[{"name": "mcp-nc", "status": "connected"}]):
            mock_cfg.return_value = {"erp_clients": {"nc": nc_config}}
            await mcp_starter.sync_nc_mcp()
            mock_reconnect.assert_called_once()
            args, kwargs = mock_reconnect.call_args
            target_config = args[1]
            assert target_config["enabled"] is False
    _run(go())
