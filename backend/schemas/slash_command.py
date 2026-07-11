from pydantic import BaseModel


class SlashCommandInfo(BaseModel):
    name: str
    description: str = ""
    usage: str = ""
    type: str = "command"  # "command" or "skill"


class SlashCommandsResponse(BaseModel):
    commands: list[SlashCommandInfo]
