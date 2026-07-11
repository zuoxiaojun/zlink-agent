from fastapi import APIRouter

from agent.slash_commands import list_commands
from backend.schemas.slash_command import SlashCommandInfo, SlashCommandsResponse

router = APIRouter(prefix="/api/slash-commands", tags=["slash-commands"])


@router.get("", response_model=SlashCommandsResponse)
def get_slash_commands():
    """Return all registered slash commands with name, description, and usage."""
    cmds = list_commands()
    return SlashCommandsResponse(
        commands=[
            SlashCommandInfo(name=c.name, description=c.description, usage=c.usage)
            for c in cmds
        ]
    )
