from pydantic import BaseModel


class SlashCommandInfo(BaseModel):
    name: str
    description: str = ""
    usage: str = ""


class SlashCommandsResponse(BaseModel):
    commands: list[SlashCommandInfo]
