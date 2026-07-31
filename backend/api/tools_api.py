import threading

from fastapi import APIRouter

from agent.tools.registry import discover_tools, registry
from backend.schemas.tool import ToolInfo

router = APIRouter(prefix="/api/tools", tags=["tools"])

_discovered = False
_discover_lock = threading.Lock()


def _ensure_discovered() -> None:
    """Lazily import tool modules on first use (keeps them off the startup path)."""
    global _discovered
    if _discovered:
        return
    with _discover_lock:
        if not _discovered:
            discover_tools()
            _discovered = True


@router.get("", response_model=list[ToolInfo])
def list_tools():
    _ensure_discovered()
    return [
        ToolInfo(
            name=e.name,
            toolset=e.toolset,
            description=e.description or e.schema.get("description", ""),
            emoji=e.emoji,
        )
        for e in registry.entries.values()
        if not e.toolset.startswith("mcp-")
    ]
