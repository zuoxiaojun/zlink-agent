from pydantic import BaseModel, Field


class LLMConfig(BaseModel):
    api_key: str = ""
    base_url: str = "https://api.openai.com/v1"
    model: str = "gpt-4o"
    provider: str = "OpenAI"


class YonSuiteConfig(BaseModel):
    app_key: str = ""
    app_secret: str = ""
    tenant_id: str = ""
    gateway_url: str = "https://c2.yonyoucloud.com/iuap-api-gateway"


class AgentConfig(BaseModel):
    max_iterations: int = Field(default=30, ge=5, le=50)


class ConfigResponse(BaseModel):
    llm: LLMConfig
    yonsuite: YonSuiteConfig
    agent: AgentConfig


class ProviderInfo(BaseModel):
    name: str
    base_url: str
    models: list[str]
    api_key_label: str
    api_key_placeholder: str
