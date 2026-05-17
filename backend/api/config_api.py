"""Config REST API — wraps config_manager and LLM_PROVIDERS."""

from fastapi import APIRouter
from backend.schemas.config import LLMConfig, YonSuiteConfig, AgentConfig, ConfigResponse, ProviderInfo
from backend.llm_providers import LLM_PROVIDERS
from agent import config_manager

router = APIRouter(prefix="/api/config", tags=["config"])


def _mask(val: str) -> str:
    if not val:
        return ""
    return (val[:4] + "****" + val[-4:]) if len(val) > 8 else (val[:2] + "****")


@router.get("", response_model=ConfigResponse)
def get_config():
    cfg = config_manager.load()
    return ConfigResponse(
        llm=LLMConfig(
            api_key=_mask(cfg.get("llm_api_key", "")),
            base_url=cfg.get("llm_base_url", "https://api.openai.com/v1"),
            model=cfg.get("llm_model", "gpt-4o"),
            provider=cfg.get("llm_provider", "OpenAI"),
        ),
        yonsuite=YonSuiteConfig(
            app_key=_mask(cfg.get("ys_app_key", "")),
            app_secret=_mask(cfg.get("ys_app_secret", "")),
            tenant_id=_mask(cfg.get("ys_tenant_id", "")),
            gateway_url=cfg.get("ys_gateway_url", "https://c2.yonyoucloud.com/iuap-api-gateway"),
        ),
        agent=AgentConfig(max_iterations=cfg.get("max_iterations", 30)),
    )


@router.put("/llm")
def save_llm_config(body: LLMConfig):
    cfg = config_manager.load()
    cfg["llm_api_key"] = body.api_key
    cfg["llm_base_url"] = body.base_url
    cfg["llm_model"] = body.model
    cfg["llm_provider"] = body.provider
    config_manager.save(cfg)
    return {"ok": True}


@router.put("/yonsuite")
def save_yonsuite_config(body: YonSuiteConfig):
    cfg = config_manager.load()
    cfg["ys_app_key"] = body.app_key
    cfg["ys_app_secret"] = body.app_secret
    cfg["ys_tenant_id"] = body.tenant_id
    cfg["ys_gateway_url"] = body.gateway_url
    config_manager.save(cfg)
    return {"ok": True}


@router.put("/agent")
def save_agent_config(body: AgentConfig):
    cfg = config_manager.load()
    cfg["max_iterations"] = body.max_iterations
    config_manager.save(cfg)
    return {"ok": True}


@router.get("/providers", response_model=list[ProviderInfo])
def get_providers():
    return [
        ProviderInfo(
            name=name,
            base_url=info["base_url"],
            models=info["models"],
            api_key_label=info["api_key_label"],
            api_key_placeholder=info["api_key_placeholder"],
        )
        for name, info in LLM_PROVIDERS.items()
    ]
