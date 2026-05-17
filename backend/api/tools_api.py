from fastapi import APIRouter
from backend.schemas.tool import ToolInfo
from agent.tools.registry import registry, discover_tools

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
    ]
