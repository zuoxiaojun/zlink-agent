from fastapi import APIRouter

from agent.skill_manager import get_all_skills
from agent.slash_commands import list_commands
from backend.schemas.slash_command import SlashCommandInfo, SlashCommandsResponse

router = APIRouter(prefix="/api/slash-commands", tags=["slash-commands"])


@router.get("", response_model=SlashCommandsResponse)
def get_slash_commands():
    """Return all registered slash commands + skill names for auto-completion."""
    cmds = [
        SlashCommandInfo(name=c.name, description=c.description, usage=c.usage)
        for c in list_commands()
    ]
    # Append all skill names as type="skill" for popup auto-completion
    for s in get_all_skills():
        name = s["name"]
        # Don't duplicate a command with the same name
        if not any(c.name == name for c in cmds):
            cmds.append(
                SlashCommandInfo(
                    name=name,
                    description=s.get("description", ""),
                    usage=f"/{name}",
                    type="skill",
                )
            )
    return SlashCommandsResponse(commands=cmds)
