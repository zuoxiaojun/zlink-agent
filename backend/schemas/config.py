from pydantic import BaseModel, Field


class ModelInfo(BaseModel):
    id: str
    context_length: int
    max_output: int | None = None


class LLMConfig(BaseModel):
    api_key: str = ""
    base_url: str = "https://api.openai.com/v1"
    model: str = "gpt-4o"
    provider: str = "OpenAI"


class YonSuiteConfig(BaseModel):
    app_key: str = ""
    app_secret: str = ""
    tenant_id: str = ""
    gateway_url: str = ""


class AgentConfig(BaseModel):
    max_iterations: int = Field(default=30, ge=5, le=50)
    compaction_enabled: bool = Field(default=True)
    max_context_tokens: int = Field(default=0, ge=0, le=2000000, description="0 = auto-detect from model")
    max_context_tokens_auto: bool = Field(default=True, description="True when context window is auto-detected")
    reserve_tokens: int = Field(default=4000, ge=1000, le=32000)
    keep_recent_tokens: int = Field(default=8000, ge=2000, le=128000)
    approval_mode: str = Field(default="allow_all", description="allow_all / approve / reject_all")


class ConfigResponse(BaseModel):
    llm: LLMConfig
    yonsuite: YonSuiteConfig
    agent: AgentConfig
    version: str = ""


class ProviderInfo(BaseModel):
    name: str
    base_url: str
    models: list[ModelInfo]
    api_key_label: str
    api_key_placeholder: str
