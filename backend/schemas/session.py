from pydantic import BaseModel


class SessionSummary(BaseModel):
    id: str
    title: str
    created_at: str
    updated_at: str
    message_count: int


class SessionDetail(BaseModel):
    id: str
    title: str
    messages: list[dict]


class SessionCreate(BaseModel):
    title: str = ""


class SessionRename(BaseModel):
    title: str
