from pydantic import BaseModel


class SkillInfo(BaseModel):
    name: str
    description: str = ""
    version: str = ""
    tags: list[str] = []
    active: bool = False


class SkillToggle(BaseModel):
    active: bool
