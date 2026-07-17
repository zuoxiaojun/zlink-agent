from fastapi import APIRouter

from agent.tools.registry import discover_tools, registry
from backend.schemas.tool import ToolInfo

router = APIRouter(prefix="/api/tools", tags=["tools"])

discover_tools()


@router.get("", response_model=list[ToolInfo])
def list_tools():
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
