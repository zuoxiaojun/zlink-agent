from pydantic import BaseModel


class SkillInfo(BaseModel):
    name: str
    description: str = ""
    version: str = ""
    tags: list[str] = []
    active: bool = True
    builtin: bool = False


class SkillUpdate(BaseModel):
    content: str
