"""Tests for agent/tools/mcp_management_tool — LLM-conversation MCP server management.

Each tool handler is a sync function that calls ``_run_async()`` to bridge
into the MCP event loop.  We monkeypatch the async MCP functions to no-ops
and patch ``_run_async`` to execute the coroutine synchronously.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest


# ────────────────────────────────────────────────────────────────────
# Fixtures
# ────────────────────────────────────────────────────────────────────


@pytest.fixture
def mgmt_env(monkeypatch, isolated_config: Path):
    """Set up test environment for MCP management tools.

    - Isolated config (temp file)
    - ``_run_async`` patched to execute coroutines synchronously
    - All MCP manager async functions patched to no-ops
    - ``get_server_statuses`` returns a controlled list
    """
    import asyncio
    import agent.tools.mcp_manager as mcp_mgr
    import agent.tools.mcp_management_tool as mgmt_tool

    # Patch _run_async to just run the coroutine synchronously
    def _sync_run_async(coro, timeout: float = 30.0):
        try:
            return asyncio.run(coro)
        except Exception as e:
            return {"success": False, "error": str(e)[:500]}

    monkeypatch.setattr(mgmt_tool, "_run_async", _sync_run_async)

    # Patch async MCP functions
    async def _noop_connect(name, config):
        pass

    async def _noop_disconnect(name):
        pass

    async def _noop_test(name, config):
        return {
            "success": True,
            "tools_discovered": 3,
            "tool_names": ["tool_a", "tool_b", "tool_c"],
            "error_message": None,
        }

    async def _noop_reload():
        return {"status": {"srv1": "connected", "srv2": "error"}}

    monkeypatch.setattr(mcp_mgr, "connect_server", _noop_connect)
    monkeypatch.setattr(mcp_mgr, "disconnect_server", _noop_disconnect)
    monkeypatch.setattr(mcp_mgr, "test_server_connection", _noop_test)
    monkeypatch.setattr(mcp_mgr, "reload_all_servers", _noop_reload)
    monkeypatch.setattr(mcp_mgr, "get_server_statuses", _mock_statuses)

    return isolated_config


def _mock_statuses() -> list[dict]:
    """Return controlled server status list for testing."""
    return [
        {
            "name": "test-server",
            "transport": "stdio",
            "status": "connected",
            "enabled": True,
            "builtin": False,
            "tool_count": 3,
            "error_message": None,
            "command": "echo",
            "args": ["hello"],
            "url": None,
            "headers": {},
            "env": {"FOO": "bar"},
            "timeout": 120,
        },
        {
            "name": "http-server",
            "transport": "http",
            "status": "error",
            "enabled": True,
            "builtin": False,
            "tool_count": 0,
            "error_message": "Connection refused",
            "command": None,
            "args": [],
            "url": "http://localhost:9999/mcp",
            "headers": {"Authorization": "Bearer tok"},
            "env": {},
            "timeout": 60,
        },
        {
            "name": "builtin-srv",
            "transport": "stdio",
            "status": "disconnected",
            "enabled": False,
            "builtin": True,
            "tool_count": 0,
            "error_message": None,
            "command": "python",
            "args": ["-m", "some_server"],
            "url": None,
            "headers": {},
            "env": {},
            "timeout": 120,
        },
    ]


def _add_server_to_config(config_path: Path, name: str, **overrides):
    """Helper: add a server entry to the config file."""
    raw = json.loads(config_path.read_text(encoding="utf-8"))
    servers = raw.setdefault("mcp_servers", {})
    entry = {
        "transport": "stdio",
        "enabled": True,
        "timeout": 120,
        "command": "echo",
        "args": ["hello"],
        "env": {},
        "builtin": False,
        **overrides,
    }
    servers[name] = entry
    config_path.write_text(json.dumps(raw), encoding="utf-8")


# ────────────────────────────────────────────────────────────────────
# 1) mcp_list_servers
# ────────────────────────────────────────────────────────────────────


def test_list_servers_returns_statuses(mgmt_env):
    from agent.tools.mcp_management_tool import mcp_list_servers

    result = json.loads(mcp_list_servers({}))
    assert result["success"] is True
    assert result["total"] == 3
    names = [s["name"] for s in result["servers"]]
    assert "test-server" in names
    assert "http-server" in names
    assert "builtin-srv" in names


def test_list_servers_includes_key_fields(mgmt_env):
    from agent.tools.mcp_management_tool import mcp_list_servers

    result = json.loads(mcp_list_servers({}))
    srv = next(s for s in result["servers"] if s["name"] == "test-server")
    assert srv["status"] == "connected"
    assert srv["transport"] == "stdio"
    assert srv["tool_count"] == 3
    assert srv["enabled"] is True
    assert srv["error"] is None


def test_list_servers_includes_http_server(mgmt_env):
    from agent.tools.mcp_management_tool import mcp_list_servers

    result = json.loads(mcp_list_servers({}))
    srv = next(s for s in result["servers"] if s["name"] == "http-server")
    assert srv["status"] == "error"
    assert srv["transport"] == "http"
    assert srv["url"] == "http://localhost:9999/mcp"
    assert srv["error"] == "Connection refused"


# ────────────────────────────────────────────────────────────────────
# 2) mcp_add_server
# ────────────────────────────────────────────────────────────────────


def test_add_server_stdio(mgmt_env, isolated_config):
    from agent.tools.mcp_management_tool import mcp_add_server

    result = json.loads(
        mcp_add_server(
            {
                "name": "playwright",
                "transport": "stdio",
                "command": "npx",
                "args": ["-y", "@playwright/mcp@latest"],
                "env": {"HOME": "/tmp"},
                "timeout": 60,
            }
        )
    )
    assert result["success"] is True
    assert "playwright" in result["message"]

    # Verify persisted to config
    raw = json.loads(isolated_config.read_text())
    entry = raw["mcp_servers"]["playwright"]
    assert entry["command"] == "npx"
    assert entry["args"] == ["-y", "@playwright/mcp@latest"]
    assert entry["env"] == {"HOME": "/tmp"}
    assert entry["timeout"] == 60
    assert entry["transport"] == "stdio"


def test_add_server_http(mgmt_env, isolated_config):
    from agent.tools.mcp_management_tool import mcp_add_server

    result = json.loads(
        mcp_add_server(
            {
                "name": "my-http-server",
                "transport": "http",
                "url": "http://localhost:3000/mcp",
                "headers": {"X-API-Key": "secret"},
                "timeout": 30,
            }
        )
    )
    assert result["success"] is True

    raw = json.loads(isolated_config.read_text())
    entry = raw["mcp_servers"]["my-http-server"]
    assert entry["transport"] == "http"
    assert entry["url"] == "http://localhost:3000/mcp"
    assert entry["headers"] == {"X-API-Key": "secret"}
    assert entry["timeout"] == 30


def test_add_server_empty_name_returns_error(mgmt_env):
    from agent.tools.mcp_management_tool import mcp_add_server

    result = json.loads(mcp_add_server({"name": ""}))
    assert result["success"] is False
    assert "不能为空" in result["error"]


def test_add_server_stdio_missing_command_returns_error(mgmt_env):
    from agent.tools.mcp_management_tool import mcp_add_server

    result = json.loads(mcp_add_server({"name": "no-cmd", "transport": "stdio"}))
    assert result["success"] is False
    assert "command" in result["error"]


def test_add_server_http_missing_url_returns_error(mgmt_env):
    from agent.tools.mcp_management_tool import mcp_add_server

    result = json.loads(
        mcp_add_server({"name": "no-url", "transport": "http"})
    )
    assert result["success"] is False
    assert "url" in result["error"]


def test_add_server_duplicate_returns_error(mgmt_env, isolated_config):
    from agent.tools.mcp_management_tool import mcp_add_server

    _add_server_to_config(isolated_config, "dup-server", command="echo")

    result = json.loads(
        mcp_add_server({"name": "dup-server", "command": "echo", "args": []})
    )
    assert result["success"] is False
    assert "已存在" in result["error"]


# ────────────────────────────────────────────────────────────────────
# 3) mcp_delete_server
# ────────────────────────────────────────────────────────────────────


def test_delete_server(mgmt_env, isolated_config):
    from agent.tools.mcp_management_tool import mcp_delete_server

    _add_server_to_config(isolated_config, "delete-me", command="echo")

    result = json.loads(mcp_delete_server({"name": "delete-me"}))
    assert result["success"] is True
    assert "已删除" in result["message"]

    raw = json.loads(isolated_config.read_text())
    assert "delete-me" not in raw.get("mcp_servers", {})


def test_delete_server_not_found(mgmt_env):
    from agent.tools.mcp_management_tool import mcp_delete_server

    result = json.loads(mcp_delete_server({"name": "does-not-exist"}))
    assert result["success"] is False
    assert "不存在" in result["error"]


def test_delete_server_empty_name(mgmt_env):
    from agent.tools.mcp_management_tool import mcp_delete_server

    result = json.loads(mcp_delete_server({"name": ""}))
    assert result["success"] is False
    assert "不能为空" in result["error"]


def test_delete_server_builtin_returns_error(mgmt_env, isolated_config):
    from agent.tools.mcp_management_tool import mcp_delete_server

    _add_server_to_config(isolated_config, "builtin-srv", command="echo", builtin=True)

    result = json.loads(mcp_delete_server({"name": "builtin-srv"}))
    assert result["success"] is False
    assert "内置" in result["error"]
    assert "不允许删除" in result["error"]

    # Config should be unchanged
    raw = json.loads(isolated_config.read_text())
    assert "builtin-srv" in raw.get("mcp_servers", {})


# ────────────────────────────────────────────────────────────────────
# 4) mcp_toggle_server
# ────────────────────────────────────────────────────────────────────


def test_toggle_server_disable(mgmt_env, isolated_config):
    from agent.tools.mcp_management_tool import mcp_toggle_server

    _add_server_to_config(isolated_config, "toggle-me", command="echo", enabled=True)

    result = json.loads(mcp_toggle_server({"name": "toggle-me"}))
    assert result["success"] is True
    assert result["enabled"] is False
    assert "已停用" in result["message"]

    raw = json.loads(isolated_config.read_text())
    assert raw["mcp_servers"]["toggle-me"]["enabled"] is False


def test_toggle_server_enable(mgmt_env, isolated_config):
    from agent.tools.mcp_management_tool import mcp_toggle_server

    _add_server_to_config(isolated_config, "toggle-me", command="echo", enabled=False)

    result = json.loads(mcp_toggle_server({"name": "toggle-me"}))
    assert result["success"] is True
    assert result["enabled"] is True
    assert "已启用" in result["message"]

    raw = json.loads(isolated_config.read_text())
    assert raw["mcp_servers"]["toggle-me"]["enabled"] is True


def test_toggle_server_not_found(mgmt_env):
    from agent.tools.mcp_management_tool import mcp_toggle_server

    result = json.loads(mcp_toggle_server({"name": "does-not-exist"}))
    assert result["success"] is False
    assert "不存在" in result["error"]


def test_toggle_server_empty_name(mgmt_env):
    from agent.tools.mcp_management_tool import mcp_toggle_server

    result = json.loads(mcp_toggle_server({"name": ""}))
    assert result["success"] is False
    assert "不能为空" in result["error"]


# ────────────────────────────────────────────────────────────────────
# 5) mcp_test_server
# ────────────────────────────────────────────────────────────────────


def test_test_server_from_config(mgmt_env, isolated_config):
    from agent.tools.mcp_management_tool import mcp_test_server

    _add_server_to_config(isolated_config, "test-me", command="echo")

    result = json.loads(mcp_test_server({"name": "test-me"}))
    assert result["success"] is True
    assert result["tools_discovered"] == 3
    assert "tool_a" in result["tool_names"]


def test_test_server_adhoc_stdio(mgmt_env):
    from agent.tools.mcp_management_tool import mcp_test_server

    result = json.loads(
        mcp_test_server(
            {
                "name": "adhoc-test",
                "transport": "stdio",
                "command": "npx",
                "args": ["-y", "@playwright/mcp@latest"],
                "timeout": 30,
            }
        )
    )
    assert result["success"] is True
    assert result["tools_discovered"] == 3


def test_test_server_adhoc_http(mgmt_env):
    from agent.tools.mcp_management_tool import mcp_test_server

    result = json.loads(
        mcp_test_server(
            {
                "name": "adhoc-http",
                "transport": "http",
                "url": "http://localhost:3000/mcp",
                "timeout": 15,
            }
        )
    )
    assert result["success"] is True


def test_test_server_not_found(mgmt_env):
    from agent.tools.mcp_management_tool import mcp_test_server

    result = json.loads(mcp_test_server({"name": "does-not-exist"}))
    assert result["success"] is False
    assert "不存在" in result["error"]


def test_test_server_empty_name(mgmt_env):
    from agent.tools.mcp_management_tool import mcp_test_server

    result = json.loads(mcp_test_server({"name": ""}))
    assert result["success"] is False
    assert "不能为空" in result["error"]


# ────────────────────────────────────────────────────────────────────
# 6) mcp_reload_servers
# ────────────────────────────────────────────────────────────────────


def test_reload_servers(mgmt_env):
    from agent.tools.mcp_management_tool import mcp_reload_servers

    result = json.loads(mcp_reload_servers({}))
    assert result["success"] is True
    assert "已重载" in result["message"]
    assert result["status"] == {"srv1": "connected", "srv2": "error"}


# ────────────────────────────────────────────────────────────────────
# 7) Edge cases & error handling
# ────────────────────────────────────────────────────────────────────


def test_list_servers_handles_exception(mgmt_env, monkeypatch):
    """Simulate a failure in get_server_statuses."""
    import agent.tools.mcp_manager as mcp_mgr

    def _broken_statuses():
        raise RuntimeError("boom")

    monkeypatch.setattr(mcp_mgr, "get_server_statuses", _broken_statuses)

    from agent.tools.mcp_management_tool import mcp_list_servers

    result = json.loads(mcp_list_servers({}))
    assert result["success"] is False
    assert "boom" in result["error"]


def test_add_server_persists_enabled_true(mgmt_env, isolated_config):
    """New servers should always be persisted with enabled=True."""
    from agent.tools.mcp_management_tool import mcp_add_server

    mcp_add_server({"name": "enabled-test", "command": "echo", "args": []})

    raw = json.loads(isolated_config.read_text())
    assert raw["mcp_servers"]["enabled-test"]["enabled"] is True


def test_delete_server_not_found_no_config_change(mgmt_env, isolated_config):
    """Deleting a non-existent server should not modify the config file."""
    from agent.tools.mcp_management_tool import mcp_delete_server

    original = isolated_config.read_text()
    mcp_delete_server({"name": "ghost"})
    assert isolated_config.read_text() == original