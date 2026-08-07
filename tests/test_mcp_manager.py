"""Tests for agent/tools/mcp_manager — MCP tool description labeling."""


def test_mcp_tool_description_tagged_with_source_label():
    """已知 ERP 的 MCP 服务器注册工具时，description 应包含数据源标签。"""
    from agent.tools.mcp_manager import _convert_mcp_tool_schema

    schema = _convert_mcp_tool_schema(
        "yonsuite",
        {
            "name": "ys_api",
            "description": "调用 YonSuite 开放 API",
            "inputSchema": {"type": "object", "properties": {}},
        },
    )
    assert "【数据源：YonSuite】" in schema.get("description", "")


def test_non_erp_mcp_tool_not_tagged():
    """非 ERP 的 MCP 服务器（如 chart server）不应被打上数据源标签。"""
    from agent.tools.mcp_manager import _convert_mcp_tool_schema

    schema = _convert_mcp_tool_schema(
        "mcp-server-chart",
        {
            "name": "render_chart",
            "description": "渲染图表",
            "inputSchema": {"type": "object", "properties": {}},
        },
    )
    assert "【数据源" not in schema.get("description", "")


def test_erp_label_added_in_register_tools():
    """验证 _register_tools 实际调用注册时 description 被正确追加。"""
    from agent.tools.mcp_manager import MCPServerConnection
    from agent.tools.registry import registry

    conn = MCPServerConnection(
        "mcp-nc",
        {"transport": "stdio", "command": "python", "args": [], "timeout": 120},
    )
    conn._tools = [
        {
            "name": "query_sales_orders",
            "description": "查询 NC 销售订单",
            "inputSchema": {"type": "object", "properties": {}},
        }
    ]

    # 手动运行注册逻辑，验证 description 被追加了标签
    conn._register_tools()

    entry = registry.get_entry("mcp_mcp_nc_query_sales_orders")
    assert entry is not None
    assert "【数据源：NC】" in entry.description
    assert "查询 NC 销售订单" in entry.description

    # 清理
    registry.deregister("mcp_mcp_nc_query_sales_orders")


class TestResolveCommand:
    """Windows 上裸命令名（npx/npm）必须解析成 .cmd 完整路径。"""

    def test_resolves_bare_command_via_path(self, tmp_path, monkeypatch):
        import sys

        from agent.tools import mcp_manager

        if sys.platform == "win32":
            fake = tmp_path / "faketool.cmd"
        else:
            fake = tmp_path / "faketool"
        fake.write_text("@echo off\n" if sys.platform == "win32" else "#!/bin/sh\n")
        monkeypatch.setenv("PATH", str(tmp_path))

        resolved = mcp_manager._resolve_command("faketool")
        assert resolved.lower() == str(fake).lower()

    def test_absolute_path_passthrough(self):
        from agent.tools import mcp_manager

        assert mcp_manager._resolve_command(r"D:\Program Files\nodejs\node.EXE") == r"D:\Program Files\nodejs\node.EXE"

    def test_missing_command_returned_as_is(self, monkeypatch):
        from agent.tools import mcp_manager

        monkeypatch.setenv("PATH", "")
        assert mcp_manager._resolve_command("definitely-not-a-real-cmd-xyz") == "definitely-not-a-real-cmd-xyz"
