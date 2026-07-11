"""测试 mcp_server.nc_mcp.config 的环境变量转换"""


def test_build_nc_mcp_env_basic():
    from mcp_server.nc_mcp.config import build_nc_mcp_env

    env = build_nc_mcp_env(
        {
            "host": "192.168.31.96",
            "port": "1521",
            "service": "orcl",
            "user": "NC65",
            "password": "secret123",
        }
    )
    assert env["ORACLE_HOST"] == "192.168.31.96"
    assert env["ORACLE_PORT"] == "1521"
    assert env["ORACLE_SERVICE"] == "orcl"
    assert env["ORACLE_USER"] == "NC65"
    assert env["ORACLE_PASSWORD"] == "secret123"


def test_build_nc_mcp_env_with_max_rows():
    from mcp_server.nc_mcp.config import build_nc_mcp_env

    env = build_nc_mcp_env(
        {
            "host": "h",
            "port": "1521",
            "service": "orcl",
            "user": "u",
            "password": "p",
            "max_rows": 500,
        }
    )
    assert env["NC_MCP_MAX_ROWS"] == "500"


def test_build_nc_mcp_env_default_max_rows():
    from mcp_server.nc_mcp.config import build_nc_mcp_env

    env = build_nc_mcp_env(
        {
            "host": "h",
            "port": "1521",
            "service": "orcl",
            "user": "u",
            "password": "p",
        }
    )
    assert env["NC_MCP_MAX_ROWS"] == "200"


def test_build_nc_mcp_config():
    import sys

    from mcp_server.nc_mcp.config import build_nc_mcp_config

    cfg = build_nc_mcp_config(
        erp_config={"host": "h", "port": "1521", "service": "orcl", "user": "u", "password": "p"},
        enabled=True,
    )
    assert cfg["transport"] == "stdio"
    assert cfg["command"] == sys.executable
    assert cfg["args"] == ["-m", "mcp_server.nc_mcp_server"]
    assert cfg["builtin"] is True
    assert cfg["enabled"] is True
    assert cfg["env"]["ORACLE_HOST"] == "h"
