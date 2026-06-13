"""JSON-RPC 2.0 server loop over stdio."""

import json
import os
import sys

from .tools import build_tools_list, dispatch_tool_call


def _rpc_result(req_id, result):
    return {"jsonrpc": "2.0", "id": req_id, "result": result}


def _rpc_error(req_id, code, message):
    return {"jsonrpc": "2.0", "id": req_id, "error": {"code": code, "message": message}}


def _send(msg: dict):
    sys.stdout.write(json.dumps(msg, ensure_ascii=False) + "\n")
    sys.stdout.flush()


def _handle_initialize(req_id: int, _params: dict):
    return _rpc_result(
        req_id,
        {
            "protocolVersion": "2024-11-05",
            "serverInfo": {"name": "ys-mcp-server", "version": "1.0.0"},
            "capabilities": {"tools": {}},
        },
    )


def _handle_tools_list(req_id: int):
    return _rpc_result(req_id, {"tools": build_tools_list()})


def _handle_tools_call(req_id: int, params: dict):
    name = params.get("name", "")
    arguments = params.get("arguments", {})
    result = dispatch_tool_call(name, arguments)
    return _rpc_result(req_id, result)


DISPATCH = {
    "initialize": _handle_initialize,
    "tools/list": _handle_tools_list,
    "tools/call": _handle_tools_call,
}


def main():
    sys.stderr.write(f"[ys-mcp-server] started (pid={os.getpid()})\n")
    sys.stderr.flush()

    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
        except json.JSONDecodeError:
            continue

        req_id = msg.get("id")
        method = msg.get("method", "")

        handler = DISPATCH.get(method)
        if handler is None:
            if req_id is not None:
                _send(_rpc_error(req_id, -32601, f"Method not found: {method}"))
            continue

        try:
            if method == "tools/list":
                resp = handler(req_id)
            else:
                resp = handler(req_id, msg.get("params", {}))
            _send(resp)
        except Exception as e:
            _send(_rpc_error(req_id, -32603, str(e)[:500]))
