"""Tool registry: builds tool list and dispatches calls from handler modules."""

from .handlers import ALL_HANDLERS
from .utils import get_client, tool_error


def build_tools_list() -> list[dict]:
    """Return the tools/list payload for all registered handlers."""
    return [
        {
            "name": h.schema["name"],
            "description": h.schema["description"],
            "inputSchema": h.schema["inputSchema"],
        }
        for h in ALL_HANDLERS
    ]


def dispatch_tool_call(name: str, arguments: dict) -> dict:
    """Route a tools/call request to the matching handler."""
    for h in ALL_HANDLERS:
        if h.schema["name"] == name:
            client = None if name == "ys_api" else get_client()
            if client is None and name != "ys_api":
                return tool_error("YonSuite 未配置")
            try:
                # ys_api needs get_client() called inside its handler too
                if name == "ys_api":
                    client = get_client()
                return h.handle(client, arguments)
            except Exception as e:
                return tool_error(f"查询失败: {e}")

    return tool_error(f"未知工具: {name}")
