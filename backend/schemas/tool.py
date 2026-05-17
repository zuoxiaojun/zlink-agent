from pydantic import BaseModel


class ToolInfo(BaseModel):
    name: str
    toolset: str
    description: str = ""
    emoji: str = ""
