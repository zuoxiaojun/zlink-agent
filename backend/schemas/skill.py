from pydantic import BaseModel


class SkillInfo(BaseModel):
    name: str
    description: str = ""
    version: str = ""
    tags: list[str] = []
    active: bool = False
    builtin: bool = False


class SkillToggle(BaseModel):
    active: bool


class SkillUpdate(BaseModel):
    content: str
