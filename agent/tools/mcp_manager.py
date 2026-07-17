"""MCP server client — connect to MCP servers, discover tools, register into ToolRegistry.

JSON-RPC over stdio (subprocess) or HTTP (httpx POST). Tool handlers bridge
async MCP calls to the synchronous ToolRegistry.dispatch() via
asyncio.run_coroutine_threadsafe().
"""

import asyncio
import concurrent.futures
import json
import logging
import os
import re
import time

import httpx

from agent.config_model import MCPServerEntry  # Pydantic model check in connect_all_servers

logger = logging.getLogger(__name__)

# --- Module-level state ---
_connections: dict[str, "MCPServerConnection"] = {}
_server_error_counts: dict[str, int] = {}
_server_breaker_opened_at: dict[str, float] = {}
_main_loop: asyncio.AbstractEventLoop | None = None

_CIRCUIT_BREAKER_THRESHOLD = 3
_CIRCUIT_BREAKER_COOLDOWN_SEC = 60.0

_INITIALIZE_TIMEOUT = 30.0


def _sanitize_name(name: str) -> str:
    """Replace non-alphanumeric chars with underscores for tool naming."""
    return re.sub(r"[^a-zA-Z0-9_]", "_", name)


def _bump_server_error(server_name: str):
    n = _server_error_counts.get(server_name, 0) + 1
    _server_error_counts[server_name] = n
    if n >= _CIRCUIT_BREAKER_THRESHOLD:
        _server_breaker_opened_at[server_name] = time.monotonic()


def _reset_server_error(server_name: str):
    _server_error_counts.pop(server_name, None)
    _server_breaker_opened_at.pop(server_name, None)


def _circuit_breaker_blocks(server_name: str) -> str | None:
    """Return an error message if the circuit breaker is open, else None."""
    count = _server_error_counts.get(server_name, 0)
    if count < _CIRCUIT_BREAKER_THRESHOLD:
        return None
    opened_at = _server_breaker_opened_at.get(server_name, 0.0)
    age = time.monotonic() - opened_at
    if age >= _CIRCUIT_BREAKER_COOLDOWN_SEC:
        _reset_server_error(server_name)
        return None
    remaining = max(1, int(_CIRCUIT_BREAKER_COOLDOWN_SEC - age))
    return (
        f"MCP server '{server_name}' unreachable ({count} consecutive failures). "
        f"Circuit breaker open, retry in ~{remaining}s."
    )


# --- JSON-RPC helpers ---


def _jsonrpc_request(req_id: int, method: str, params: dict | None = None) -> dict:
    msg = {"jsonrpc": "2.0", "id": req_id, "method": method}
    if params is not None:
        msg["params"] = params
    return msg


def _jsonrpc_result(resp: dict) -> dict:
    if "result" in resp:
        return resp["result"]
    err = resp.get("error", {})
    raise RuntimeError(f"JSON-RPC error {err.get('code', -1)}: {err.get('message', 'unknown')}")


# --- Schema conversion ---


def _convert_mcp_tool_schema(server_name: str, tool: dict) -> dict:
    """Convert an MCP tool definition to OpenAI function-calling schema."""
    safe_server = _sanitize_name(server_name)
    safe_tool = _sanitize_name(tool["name"])
    prefixed = f"mcp_{safe_server}_{safe_tool}"

    input_schema = tool.get("inputSchema", {})
    params = {"type": "object", "properties": {}, "required": []}

    if input_schema:
        params["properties"] = input_schema.get("properties", {})
        params["required"] = input_schema.get("required", [])

    description = tool.get("description", f"MCP tool: {tool['name']}")
    # Redact potential credential leakage in descriptions
    if len(description) > 2000:
        description = description[:2000] + "..."

    # ERP 数据源标签：在 description 末尾标注数据来源
    erp_source_labels = {"yonsuite": "YonSuite", "mcp-nc": "NC"}
    source_label = erp_source_labels.get(server_name)
    if source_label:
        description = f"{description.rstrip()} 【数据源：{source_label}】"

    return {
        "name": prefixed,
        "description": description,
        "parameters": params,
    }


# --- Tool handler factory ---


def _make_mcp_tool_handler(server_name: str, tool_name: str):
    """Return a sync handler(args: dict) -> str for an MCP tool."""

    def _handler(args: dict) -> str:
        breaker_msg = _circuit_breaker_blocks(server_name)
        if breaker_msg:
            return json.dumps({"error": breaker_msg}, ensure_ascii=False)

        conn = _connections.get(server_name)
        if conn is None or not conn.connected:
            _bump_server_error(server_name)
            return json.dumps(
                {"error": f"MCP server '{server_name}' not connected"},
                ensure_ascii=False,
            )

        loop = _main_loop
        if loop is None:
            return json.dumps({"error": "MCP event loop not initialized"})

        async def _call():
            return await conn.call_tool(tool_name, args)

        future = asyncio.run_coroutine_threadsafe(_call(), loop)
        try:
            result = future.result(timeout=conn.timeout)
            _reset_server_error(server_name)
            # MCP result: {"content": [{"type": "text", "text": "..."}, ...]}
            content = result.get("content", [])
            text_parts = []
            for c in content:
                if c.get("type") == "text":
                    text_parts.append(c.get("text", ""))
                elif c.get("type") == "resource":
                    text_parts.append(json.dumps(c.get("resource", {}), ensure_ascii=False))
            return "\n".join(text_parts) if text_parts else json.dumps(result, ensure_ascii=False)
        except concurrent.futures.TimeoutError:
            _bump_server_error(server_name)
            return json.dumps({"error": f"MCP tool '{tool_name}' timed out after {conn.timeout}s"})
        except RuntimeError as e:
            _bump_server_error(server_name)
            msg = str(e)
            # Sanitize potential credential leakage
            if len(msg) > 500:
                msg = msg[:500] + "..."
            return json.dumps({"error": msg}, ensure_ascii=False)
        except Exception as e:
            _bump_server_error(server_name)
            return json.dumps(
                {"error": f"MCP call failed: {type(e).__name__}"},
                ensure_ascii=False,
            )

    return _handler


# --- MCPServerConnection ---


class MCPServerConnection:
    """Manages a single MCP server through JSON-RPC over stdio or HTTP."""

    def __init__(self, name: str, config: dict):
        self.name = name
        self.config = config
        self.transport = config.get("transport", "stdio")
        self.timeout = config.get("timeout", 120)

        # stdio transport
        self._process: asyncio.subprocess.Process | None = None
        self._reader_lock: asyncio.Lock | None = None

        # HTTP transport
        self._http_client: httpx.AsyncClient | None = None
        self._http_url: str | None = None

        # JSON-RPC state
        self._request_id: int = 0
        self._pending: dict[int, asyncio.Future] = {}
        self._reader_task: asyncio.Task | None = None
        self._stderr_task: asyncio.Task | None = None
        self._rpc_lock: asyncio.Lock | None = None
        self._server_name: str = ""
        self._server_version: str = ""

        self._ready: bool = False
        self._error: str | None = None
        self._tools: list[dict] = []
        self._registered_tool_names: list[str] = []

    @property
    def connected(self) -> bool:
        return self._ready

    @property
    def status(self) -> str:
        if self._ready:
            return "connected"
        if self._error:
            return "error"
        return "disconnected"

    @property
    def tool_count(self) -> int:
        return len(self._tools)

    async def connect(self) -> None:
        """Connect, send initialize, discover tools. Sets _ready on success."""
        self._error = None
        try:
            if self.transport == "stdio":
                await self._connect_stdio()
            else:
                await self._connect_http()

            # Initialize
            init_result = await self._send_request(
                "initialize",
                {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {},
                    "clientInfo": {
                        "name": "ZLink Agent",
                        "version": "1.0.0",
                    },
                },
            )
            self._server_name = init_result.get("serverInfo", {}).get("name", "")
            self._server_version = init_result.get("serverInfo", {}).get("version", "")

            # Send initialized notification
            await self._send_notification("notifications/initialized")

            # Discover tools
            tools = await self._list_tools()
            self._tools = tools.get("tools", [])
            self._ready = True
            self._error = None

            logger.info(
                "MCP server '%s' connected, %d tools discovered",
                self.name,
                len(self._tools),
            )
        except Exception as e:
            self._error = str(e)[:500]
            self._ready = False
            logger.warning("MCP server '%s' connection failed: %s", self.name, self._error)
            await self.disconnect()

    async def disconnect(self) -> None:
        """Close transport and clean up state."""
        self._ready = False

        # Cancel reader
        if self._reader_task:
            self._reader_task.cancel()
            try:
                await self._reader_task
            except asyncio.CancelledError:
                pass
            self._reader_task = None

        # Cancel stderr reader
        if self._stderr_task:
            self._stderr_task.cancel()
            try:
                await self._stderr_task
            except asyncio.CancelledError:
                pass
            self._stderr_task = None

        # Resolve pending futures
        for fut in self._pending.values():
            if not fut.done():
                fut.set_exception(RuntimeError("connection closed"))
        self._pending.clear()

        # Kill stdio process
        if self._process:
            if self._process.stdin:
                try:
                    self._process.stdin.close()
                except Exception:
                    logger.debug("MCP server '%s' stdin close error during disconnect", self.name)
            try:
                self._process.kill()
            except Exception:
                logger.debug("MCP server '%s' kill error during disconnect", self.name)
            try:
                await asyncio.wait_for(self._process.wait(), timeout=3)
            except (TimeoutError, Exception):
                logger.debug("MCP server '%s' wait error during disconnect", self.name)
            self._process = None

        # Close HTTP client
        if self._http_client:
            try:
                await self._http_client.aclose()
            except Exception:
                logger.debug("MCP server '%s' HTTP close error during disconnect", self.name)
            self._http_client = None

        self._reader_lock = None
        self._rpc_lock = None

        # Unregister tools from registry
        self._unregister_tools()

        logger.info("MCP server '%s' disconnected", self.name)

    def _unregister_tools(self):
        from agent.tools.registry import registry

        for name in self._registered_tool_names:
            if name in registry.entries:
                del registry.entries[name]
        self._registered_tool_names.clear()

    def _register_tools(self):
        from agent.tools.registry import registry

        toolset = f"mcp-{self.name}"
        registered = []
        for tool in self._tools:
            schema = _convert_mcp_tool_schema(self.name, tool)
            name = schema["name"]
            handler = _make_mcp_tool_handler(self.name, tool["name"])
            registry.register(
                name=name,
                toolset=toolset,
                schema=schema,
                handler=handler,
                description=schema.get("description", ""),
                emoji="\U0001f50c",  # electric plug
            )
            registered.append(name)
        self._registered_tool_names = registered

    # --- stdio transport ---

    async def _connect_stdio(self):
        command = self.config.get("command")
        if not command:
            raise ValueError("stdio transport requires 'command'")
        args = self.config.get("args", [])

        # v1.5.0: 解析 ${path.to.value} 占位符 (用户友好配置 → MCP env)
        user_env = self.config.get("env", {})
        try:
            from agent.config_manager import load as _load_cfg

            cfg_obj = _load_cfg()
            # Pydantic model → dict (Pydantic v2 用 model_dump)
            full_config = cfg_obj.model_dump() if hasattr(cfg_obj, "model_dump") else dict(cfg_obj)
            from agent.config_manager import resolve_placeholders

            user_env = resolve_placeholders(user_env, full_config)
        except Exception:
            # config 不可用时保持原样, 启动时报错定位更明确
            logger.warning("MCP server '%s': failed to resolve config placeholders", self.name)

        # Filter safe env vars + user-specified env
        safe_env = {
            k: v for k, v in os.environ.items() if k in ("PATH", "HOME", "USER", "SHELL", "TMPDIR", "TEMP", "TMP", "PYTHONPATH")
        }
        safe_env.update(user_env)

        self._process = await asyncio.create_subprocess_exec(
            command,
            *args,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=safe_env,
        )
        self._reader_lock = asyncio.Lock()
        self._rpc_lock = asyncio.Lock()
        self._reader_task = asyncio.ensure_future(self._stdio_reader())
        self._stderr_task = asyncio.ensure_future(self._stderr_reader())

    async def _stdio_reader(self):
        """Read line-delimited JSON-RPC responses from process stdout."""
        assert self._process and self._process.stdout
        try:
            buf = b""
            while True:
                chunk = await self._process.stdout.read(8192)
                if not chunk:
                    break
                buf += chunk
                while b"\n" in buf:
                    line, buf = buf.split(b"\n", 1)
                    if line.strip():
                        self._handle_line(line.decode("utf-8"))
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.warning("MCP server '%s' stdio reader exception", self.name)
        finally:
            if self._ready:
                self._ready = False
                self._error = "stdio process exited unexpectedly"

    async def _stderr_reader(self):
        """Log stderr output from the subprocess."""
        assert self._process and self._process.stderr
        try:
            buf = b""
            while True:
                chunk = await self._process.stderr.read(8192)
                if not chunk:
                    break
                buf += chunk
                while b"\n" in buf:
                    line, buf = buf.split(b"\n", 1)
                    if line.strip():
                        logger.debug("[mcp %s stderr] %s", self.name, line.decode("utf-8", errors="replace"))
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.warning("MCP server '%s' stderr reader exception", self.name)

    def _handle_line(self, line: str):
        try:
            msg = json.loads(line)
        except json.JSONDecodeError:
            return
        rid = msg.get("id")
        if rid is not None and rid in self._pending:
            fut = self._pending.pop(rid)
            if not fut.done():
                fut.set_result(msg)

    # --- HTTP transport ---

    async def _connect_http(self):
        url = self.config.get("url")
        if not url:
            raise ValueError("HTTP transport requires 'url'")
        self._http_url = url
        headers = dict(self.config.get("headers", {}))
        # Expand ${ENV_VAR} in header values
        for k, v in list(headers.items()):
            for match in re.finditer(r"\$\{(\w+)\}", v):
                headers[k] = v.replace(match.group(0), os.environ.get(match.group(1), ""))
        self._http_client = httpx.AsyncClient(
            headers=headers,
            timeout=httpx.Timeout(self.timeout),
        )
        self._rpc_lock = asyncio.Lock()

    # --- JSON-RPC ---

    async def _send_request(self, method: str, params: dict | None = None) -> dict:
        self._request_id += 1
        rid = self._request_id
        msg = _jsonrpc_request(rid, method, params)

        if self.transport == "stdio":
            assert self._process and self._process.stdin
            loop = asyncio.get_event_loop()
            fut: asyncio.Future = loop.create_future()
            self._pending[rid] = fut
            try:
                line = json.dumps(msg, ensure_ascii=False) + "\n"
                self._process.stdin.write(line.encode("utf-8"))
                await self._process.stdin.drain()
                result_msg = await asyncio.wait_for(fut, timeout=self.timeout)
                return _jsonrpc_result(result_msg)
            except TimeoutError:
                self._pending.pop(rid, None)
                raise RuntimeError(f"JSON-RPC request '{method}' timed out after {self.timeout}s")
        else:
            assert self._http_client and self._http_url
            if self._rpc_lock is None:
                raise RuntimeError("RPC lock not initialized")
            async with self._rpc_lock:
                resp = await self._http_client.post(
                    self._http_url,
                    json=msg,
                )
                resp.raise_for_status()
                result_msg = resp.json()
                return _jsonrpc_result(result_msg)

    async def _send_notification(self, method: str, params: dict | None = None):
        msg: dict[str, object] = {"jsonrpc": "2.0", "method": method}
        if params is not None:
            msg["params"] = params
        if self.transport == "stdio":
            assert self._process and self._process.stdin
            line = json.dumps(msg, ensure_ascii=False) + "\n"
            self._process.stdin.write(line.encode("utf-8"))
            await self._process.stdin.drain()
        else:
            assert self._http_client and self._http_url
            await self._http_client.post(self._http_url, json=msg)

    async def _list_tools(self) -> dict:
        """List tools; returns {"tools": [...]}."""
        return await self._send_request("tools/list")

    async def call_tool(self, tool_name: str, arguments: dict) -> dict:
        """Call a tool on the MCP server. Returns the result dict."""
        if self._rpc_lock is None:
            raise RuntimeError("RPC lock not initialized")
        async with self._rpc_lock:
            return await self._send_request("tools/call", {"name": tool_name, "arguments": arguments})


# --- Public API ---


def _ensure_loop() -> asyncio.AbstractEventLoop:
    global _main_loop
    if _main_loop is None:
        try:
            _main_loop = asyncio.get_running_loop()
        except RuntimeError:
            _main_loop = asyncio.new_event_loop()
            asyncio.set_event_loop(_main_loop)
    return _main_loop


def _build_config_dict(body) -> dict:
    """Convert a pydantic MCPServerConfig to a plain config dict."""
    cfg = {
        "transport": body.transport,
        "enabled": body.enabled,
        "timeout": body.timeout,
    }
    if body.transport == "stdio":
        cfg["command"] = body.command
        cfg["args"] = body.args or []
        cfg["env"] = body.env or {}
    else:
        cfg["url"] = body.url
        cfg["headers"] = body.headers or {}
    return cfg


async def connect_all_servers(servers_config: dict) -> dict[str, str]:
    """Connect to all enabled MCP servers from config. Returns status map."""
    _ensure_loop()
    status: dict[str, str] = {}
    tasks = []
    names = []
    for name, cfg in servers_config.items():
        # Convert Pydantic model to dict (v1.3.0+ config model)
        if isinstance(cfg, MCPServerEntry):
            cfg = cfg.model_dump()
        if not cfg.get("enabled", True):
            status[name] = "disabled"
            continue
        tasks.append(connect_server(name, cfg))
        names.append(name)

    results = await asyncio.gather(*tasks, return_exceptions=True)
    for name, result in zip(names, results, strict=False):
        if isinstance(result, Exception):
            logger.warning("MCP server '%s' connection error: %s", name, result)
            status[name] = "error"
        else:
            conn = _connections.get(name)
            status[name] = conn.status if conn else "error"
    return status


async def connect_server(name: str, config: dict):
    """Connect to an MCP server and register its tools."""
    # Disconnect existing if any
    if name in _connections:
        await disconnect_server(name)

    conn = MCPServerConnection(name, config)
    _connections[name] = conn
    _reset_server_error(name)

    try:
        await conn.connect()
        if conn.connected:
            conn._register_tools()
        else:
            logger.warning("MCP server '%s' connection failed", name)
    except Exception:
        logger.exception("MCP server '%s' connection error", name)


async def disconnect_server(name: str):
    """Disconnect an MCP server and unregister its tools."""
    conn = _connections.pop(name, None)
    if conn:
        await conn.disconnect()
    _reset_server_error(name)


async def disconnect_all_servers():
    """Disconnect all MCP servers."""
    for name in list(_connections):
        await disconnect_server(name)


async def reload_all_servers() -> dict:
    """Disconnect all, then reconnect enabled servers from config."""
    from agent import config_manager

    await disconnect_all_servers()
    cfg = config_manager.load()
    servers_cfg = {k: v.model_dump() for k, v in cfg.mcp_servers.items()}
    status = await connect_all_servers(servers_cfg)
    return {"status": status}


def get_server_statuses() -> list[dict]:
    """Return status info for all configured servers."""
    from agent import config_manager

    cfg = config_manager.load()
    servers_cfg = {k: v.model_dump() for k, v in cfg.mcp_servers.items()}

    result = []
    for name, scfg in servers_cfg.items():
        conn = _connections.get(name)
        enabled = scfg.get("enabled", True)
        base = {
            "name": name,
            "transport": scfg.get("transport", "stdio"),
            "enabled": enabled,
            "builtin": scfg.get("builtin", False),
            "command": scfg.get("command"),
            "args": scfg.get("args", []),
            "url": scfg.get("url"),
            "headers": scfg.get("headers", {}),
            "env": scfg.get("env", {}),
            "timeout": scfg.get("timeout", 120),
        }
        if not enabled:
            result.append(
                {
                    **base,
                    "status": "disconnected",
                    "tool_count": 0,
                    "error_message": None,
                }
            )
        elif conn:
            result.append(
                {
                    **base,
                    "status": "connected" if conn.connected else "error",
                    "tool_count": len(conn._registered_tool_names) if conn.connected else 0,
                    "error_message": conn._error if not conn.connected else None,
                }
            )
        else:
            result.append(
                {
                    **base,
                    "status": "disconnected",
                    "tool_count": 0,
                    "error_message": None,
                }
            )
    return result


async def test_server_connection(name: str, config: dict) -> dict:
    """Test-connect to a server, discover tools, then disconnect. Does NOT register."""
    conn = MCPServerConnection(name, config)
    try:
        await conn.connect()
        return {
            "success": conn.connected,
            "tools_discovered": conn.tool_count,
            "tool_names": [t["name"] for t in conn._tools],
            "error_message": conn._error,
        }
    except Exception as e:
        return {
            "success": False,
            "tools_discovered": 0,
            "tool_names": [],
            "error_message": str(e)[:500],
        }
    finally:
        await conn.disconnect()
