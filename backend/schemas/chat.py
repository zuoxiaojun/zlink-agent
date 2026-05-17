from pydantic import BaseModel


class TokenUsage(BaseModel):
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int


class ChatDone(BaseModel):
    final_response: str
    messages: list[dict]
    api_calls: int
    token_usage: TokenUsage | None = None
    completed: bool
    error: str | None = None
    session_id: str
    session_title: str = ""
