"""MCP server management tools for ZLink Agent.

Lets the LLM add, delete, toggle, list, and test MCP server connections
directly from conversation, without needing to use the Settings UI.

Usage (in conversation):
  "帮我加一个 Playwright MCP: {name: playwright, command: npx, args: [...]}"
    → agent calls mcp_add_server(...)

  "查看当前 MCP 服务器状态"
    → agent calls mcp_list_servers()
"""

import asyncio
import json
import logging

from agent.tools.registry import registry

logger = logging.getLogger(__name__)

# ═══════════════════════════════════════════════════════════════
# Helpers — submit async work to the MCP event loop
# ═══════════════════════════════════════════════════════════════

_MCP_LOOP_IMPORTED = False


def _ensure_mcp_loop():
    """Import and return _main_loop from mcp_manager; caches success."""
    from agent.tools.mcp_manager import _main_loop

    global _MCP_LOOP_IMPORTED
    try:
        if _main_loop is None:
            return None
        _MCP_LOOP_IMPORTED = True
        return _main_loop
    except (ImportError, AttributeError):
        return None


def _run_async(coro, timeout: float = 30.0):
    """Run an async coroutine on the MCP event loop (sync caller)."""
    loop = _ensure_mcp_loop()
    if loop is None:
        return {"success": False, "error": "MCP 事件循环未初始化"}
    future = asyncio.run_coroutine_threadsafe(coro, loop)
    try:
        return future.result(timeout=timeout)
    except TimeoutError:
        return {"success": False, "error": f"操作超时 ({timeout}s)"}
    except Exception as e:
        logger.exception("MCP management async call failed")
        return {"success": False, "error": str(e)[:500]}


# ═══════════════════════════════════════════════════════════════
# Tool handlers
# ═══════════════════════════════════════════════════════════════


def mcp_list_servers(args: dict) -> str:
    """List all configured MCP servers and their current status."""
    from agent.tools.mcp_manager import get_server_statuses

    try:
        statuses = get_server_statuses()
        # Build a compact summary for the LLM
        summary = []
        for s in statuses:
            summary.append(
                {
                    "name": s.get("name"),
                    "transport": s.get("transport"),
                    "status": s.get("status"),
                    "enabled": s.get("enabled"),
                    "builtin": s.get("builtin", False),
                    "tool_count": s.get("tool_count", 0),
                    "error": s.get("error_message"),
                    "command": s.get("command"),
                    "url": s.get("url"),
                }
            )
        return json.dumps(
            {"success": True, "servers": summary, "total": len(summary)},
            ensure_ascii=False,
        )
    except Exception as e:
        logger.exception("mcp_list_servers failed")
        return json.dumps({"success": False, "error": str(e)[:500]}, ensure_ascii=False)


def mcp_add_server(args: dict) -> str:
    """Add and connect a new MCP server."""
    name = (args.get("name") or "").strip()
    if not name:
        return json.dumps({"success": False, "error": "服务器名称不能为空"}, ensure_ascii=False)

    transport = args.get("transport", "stdio")
    timeout = args.get("timeout", 120)

    # Build config dict (same shape as _build_config_dict from mcp_api)
    config = {
        "transport": transport,
        "enabled": True,
        "timeout": timeout,
    }
    if transport == "stdio":
        command = args.get("command") or ""
        if not command:
            return json.dumps(
                {"success": False, "error": "stdio 传输模式需要提供 command"}, ensure_ascii=False
            )
        config["command"] = command
        config["args"] = args.get("args", [])
        config["env"] = args.get("env", {})
    else:
        url = args.get("url") or ""
        if not url:
            return json.dumps(
                {"success": False, "error": "HTTP 传输模式需要提供 url"}, ensure_ascii=False
            )
        config["url"] = url
        config["headers"] = args.get("headers", {})

    try:
        from agent import config_manager
        from agent.config_model import MCPServerEntry
        from agent.tools.mcp_manager import connect_server, get_server_statuses

        # Load config
        cfg = config_manager.load()

        # Check duplicate
        if name in cfg.mcp_servers:
            return json.dumps(
                {"success": False, "error": f"服务器「{name}」已存在"}, ensure_ascii=False
            )

        # Build entry and save
        entry = MCPServerEntry(**config)
        cfg.mcp_servers[name] = entry
        config_manager.save(cfg)

        # Connect
        result = _run_async(connect_server(name, config), timeout=max(timeout + 5, 60))
        if result and isinstance(result, dict) and not result.get("success", True):
            return json.dumps(
                {"success": False, "error": f"服务器已保存但连接失败: {result.get('error')}"},
                ensure_ascii=False,
            )

        # Return status
        statuses = {s["name"]: s for s in get_server_statuses()}
        s = statuses.get(name, {})
        return json.dumps(
            {
                "success": True,
                "message": f"MCP 服务器「{name}」已添加",
                "status": s.get("status", "unknown"),
                "tool_count": s.get("tool_count", 0),
                "name": name,
            },
            ensure_ascii=False,
        )

    except Exception as e:
        logger.exception("mcp_add_server failed")
        return json.dumps({"success": False, "error": str(e)[:500]}, ensure_ascii=False)


def mcp_delete_server(args: dict) -> str:
    """Delete an MCP server by name."""
    from agent import config_manager
    from agent.tools.mcp_manager import disconnect_server

    name = (args.get("name") or "").strip()
    if not name:
        return json.dumps({"success": False, "error": "服务器名称不能为空"}, ensure_ascii=False)

    try:
        cfg = config_manager.load()
        if name not in cfg.mcp_servers:
            return json.dumps(
                {"success": False, "error": f"服务器「{name}」不存在"}, ensure_ascii=False
            )

        # Protect builtin servers
        entry = cfg.mcp_servers[name]
        if getattr(entry, "builtin", False):
            return json.dumps(
                {"success": False, "error": f"内置服务器「{name}」不允许删除"}, ensure_ascii=False
            )

        # Disconnect and remove
        _run_async(disconnect_server(name), timeout=10)
        del cfg.mcp_servers[name]
        config_manager.save(cfg)

        return json.dumps(
            {"success": True, "message": f"MCP 服务器「{name}」已删除"},
            ensure_ascii=False,
        )
    except Exception as e:
        logger.exception("mcp_delete_server failed")
        return json.dumps({"success": False, "error": str(e)[:500]}, ensure_ascii=False)


def mcp_toggle_server(args: dict) -> str:
    """Enable or disable an MCP server."""
    from agent import config_manager
    from agent.tools.mcp_manager import connect_server, disconnect_server

    name = (args.get("name") or "").strip()
    if not name:
        return json.dumps({"success": False, "error": "服务器名称不能为空"}, ensure_ascii=False)

    try:
        cfg = config_manager.load()
        if name not in cfg.mcp_servers:
            return json.dumps(
                {"success": False, "error": f"服务器「{name}」不存在"}, ensure_ascii=False
            )

        entry = cfg.mcp_servers[name]
        new_enabled = not entry.enabled
        entry.enabled = new_enabled
        config_manager.save(cfg)

        if new_enabled:
            config_dict = entry.model_dump()
            _run_async(connect_server(name, config_dict), timeout=max(entry.timeout + 5, 60))
            action = "已启用"
        else:
            _run_async(disconnect_server(name), timeout=10)
            action = "已停用"

        return json.dumps(
            {
                "success": True,
                "message": f"MCP 服务器「{name}」{action}",
                "enabled": new_enabled,
                "name": name,
            },
            ensure_ascii=False,
        )
    except Exception as e:
        logger.exception("mcp_toggle_server failed")
        return json.dumps({"success": False, "error": str(e)[:500]}, ensure_ascii=False)


def mcp_test_server(args: dict) -> str:
    """Test-connect to an MCP server (ad-hoc config or existing)."""
    from agent import config_manager
    from agent.tools.mcp_manager import test_server_connection

    name = (args.get("name") or "").strip()
    if not name:
        return json.dumps({"success": False, "error": "服务器名称不能为空"}, ensure_ascii=False)

    # Build test config — either from args (ad-hoc) or from config (existing server)
    transport = args.get("transport", "stdio")
    timeout = args.get("timeout", 30)

    config: dict
    if args.get("command") or args.get("url"):
        # User provided ad-hoc config inline
        config = {
            "transport": transport,
            "timeout": timeout,
        }
        if transport == "stdio":
            config["command"] = args.get("command", "")
            config["args"] = args.get("args", [])
            config["env"] = args.get("env", {})
        else:
            config["url"] = args.get("url", "")
            config["headers"] = args.get("headers", {})
    else:
        # Use existing config
        try:
            cfg = config_manager.load()
            if name not in cfg.mcp_servers:
                return json.dumps(
                    {"success": False, "error": f"服务器「{name}」不存在"}, ensure_ascii=False
                )
            config = cfg.mcp_servers[name].model_dump()
        except Exception as e:
            return json.dumps({"success": False, "error": str(e)[:500]}, ensure_ascii=False)

    try:
        result = _run_async(
            test_server_connection(name, config), timeout=max(timeout + 5, 60)
        )
        if isinstance(result, dict):
            return json.dumps(
                {
                    "success": result.get("success", False),
                    "tools_discovered": result.get("tools_discovered", 0),
                    "tool_names": result.get("tool_names", []),
                    "error_message": result.get("error_message"),
                    "name": name,
                },
                ensure_ascii=False,
            )
        return json.dumps({"success": False, "error": "测试返回无效结果"}, ensure_ascii=False)
    except Exception as e:
        logger.exception("mcp_test_server failed")
        return json.dumps({"success": False, "error": str(e)[:500]}, ensure_ascii=False)


def mcp_reload_servers(args: dict) -> str:
    """Disconnect all MCP servers and reconnect enabled ones from config."""
    from agent.tools.mcp_manager import reload_all_servers

    try:
        result = _run_async(reload_all_servers(), timeout=120)
        if isinstance(result, dict):
            status = result.get("status", {})
            connected = sum(1 for v in status.values() if v == "connected")
            total = len(status)
            return json.dumps(
                {
                    "success": True,
                    "message": f"MCP 服务器已重载，{connected}/{total} 已连接",
                    "status": status,
                },
                ensure_ascii=False,
            )
        return json.dumps({"success": False, "error": "重载返回无效结果"}, ensure_ascii=False)
    except Exception as e:
        logger.exception("mcp_reload_servers failed")
        return json.dumps({"success": False, "error": str(e)[:500]}, ensure_ascii=False)


# ═══════════════════════════════════════════════════════════════
# Schemas & registration
# ═══════════════════════════════════════════════════════════════

MCP_LIST_SCHEMA = {
    "name": "mcp_list_servers",
    "description": "列出所有已配置的 MCP 服务器及其连接状态、工具数量。",
    "parameters": {"type": "object", "properties": {}},
}

MCP_ADD_SCHEMA = {
    "name": "mcp_add_server",
    "description": "添加并连接一个新的 MCP 服务器。用户提供 JSON 配置时，解析 name、command、args、transport、url、env 等字段。",
    "parameters": {
        "type": "object",
        "properties": {
            "name": {
                "type": "string",
                "description": "服务器唯一名称，如 'playwright'、'sequential-thinking'",
            },
            "transport": {
                "type": "string",
                "enum": ["stdio", "http"],
                "description": "传输方式，stdio=子进程，http=HTTP JSON-RPC",
            },
            "command": {
                "type": "string",
                "description": "stdio 模式下可执行命令，如 'npx'、'uvx'、'node'",
            },
            "args": {
                "type": "array",
                "items": {"type": "string"},
                "description": "命令行参数列表，如 ['-y', '@playwright/mcp@latest']",
            },
            "url": {
                "type": "string",
                "description": "HTTP 模式下的服务器 URL",
            },
            "headers": {
                "type": "object",
                "description": "HTTP 请求头（仅 HTTP 模式）",
                "additionalProperties": {"type": "string"},
            },
            "env": {
                "type": "object",
                "description": "环境变量（仅 stdio 模式）",
                "additionalProperties": {"type": "string"},
            },
            "timeout": {
                "type": "integer",
                "description": "超时时间（秒），默认 120",
            },
        },
        "required": ["name"],
    },
}

MCP_DELETE_SCHEMA = {
    "name": "mcp_delete_server",
    "description": "删除一个 MCP 服务器（断开连接、移除配置）。内置服务器不允许删除。",
    "parameters": {
        "type": "object",
        "properties": {
            "name": {"type": "string", "description": "要删除的服务器名称"},
        },
        "required": ["name"],
    },
}

MCP_TOGGLE_SCHEMA = {
    "name": "mcp_toggle_server",
    "description": "启用或停用（断开/连接）一个 MCP 服务器。",
    "parameters": {
        "type": "object",
        "properties": {
            "name": {"type": "string", "description": "服务器名称"},
        },
        "required": ["name"],
    },
}

MCP_TEST_SCHEMA = {
    "name": "mcp_test_server",
    "description": "测试 MCP 服务器连接。可以用现有配置测试，也可以在参数中临时传入 command/url 测试新配置。",
    "parameters": {
        "type": "object",
        "properties": {
            "name": {"type": "string", "description": "服务器名称（必填）"},
            "command": {
                "type": "string",
                "description": "可选：临时测试用的命令，不传则使用现有配置",
            },
            "args": {
                "type": "array",
                "items": {"type": "string"},
                "description": "临时测试用的参数",
            },
            "transport": {
                "type": "string",
                "enum": ["stdio", "http"],
                "description": "传输方式，默认 stdio",
            },
            "url": {
                "type": "string",
                "description": "HTTP 模式下的 URL",
            },
            "timeout": {
                "type": "integer",
                "description": "超时秒数，默认 30",
            },
        },
        "required": ["name"],
    },
}

MCP_RELOAD_SCHEMA = {
    "name": "mcp_reload_servers",
    "description": "断开所有 MCP 服务器并根据配置重新连接。",
    "parameters": {"type": "object", "properties": {}},
}

registry.register(
    name="mcp_list_servers",
    toolset="mcp",
    schema=MCP_LIST_SCHEMA,
    handler=mcp_list_servers,
    description="列出所有 MCP 服务器状态",
    emoji="📋",
)

registry.register(
    name="mcp_add_server",
    execution_mode="sequential",
    toolset="mcp",
    schema=MCP_ADD_SCHEMA,
    handler=mcp_add_server,
    description="添加并连接 MCP 服务器",
    emoji="➕",
    risk_level="medium",
)

registry.register(
    name="mcp_delete_server",
    execution_mode="sequential",
    toolset="mcp",
    schema=MCP_DELETE_SCHEMA,
    handler=mcp_delete_server,
    description="删除 MCP 服务器",
    emoji="🗑️",
    risk_level="high",
)

registry.register(
    name="mcp_toggle_server",
    execution_mode="sequential",
    toolset="mcp",
    schema=MCP_TOGGLE_SCHEMA,
    handler=mcp_toggle_server,
    description="启用/停用 MCP 服务器",
    emoji="⏯️",
    risk_level="medium",
)

registry.register(
    name="mcp_test_server",
    toolset="mcp",
    schema=MCP_TEST_SCHEMA,
    handler=mcp_test_server,
    description="测试 MCP 服务器连接",
    emoji="🔌",
)

registry.register(
    name="mcp_reload_servers",
    execution_mode="sequential",
    toolset="mcp",
    schema=MCP_RELOAD_SCHEMA,
    handler=mcp_reload_servers,
    description="重载所有 MCP 服务器",
    emoji="🔄",
    risk_level="high",
)
