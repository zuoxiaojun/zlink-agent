"""Config REST API — wraps config_manager and LLM_PROVIDERS."""

from fastapi import APIRouter

from agent import config_manager
from agent.config_model import MCPServerEntry
from agent.context_compactor import resolve_context_window
from agent.tools.mcp_manager import connect_server, disconnect_server
from backend.llm_providers import LLM_PROVIDERS
from backend.api.system_api import _get_version
from backend.schemas.config import (
    AgentConfig,
    ConfigResponse,
    LLMConfig,
    ModelInfo,
    ProviderInfo,
    YonSuiteConfig,
)

router = APIRouter(prefix="/api/config", tags=["config"])


def _mask(val: str) -> str:
    if not val:
        return ""
    return (val[:4] + "****" + val[-4:]) if len(val) > 8 else (val[:2] + "****")


@router.get("", response_model=ConfigResponse)
def get_config():
    cfg = config_manager.load()
    raw_ctx = cfg.max_context_tokens
    effective_ctx = raw_ctx if raw_ctx > 0 else resolve_context_window(cfg.llm_model)
    return ConfigResponse(
        llm=LLMConfig(
            api_key=_mask(cfg.llm_api_key),
            base_url=cfg.llm_base_url,
            model=cfg.llm_model,
            provider=cfg.llm_provider,
        ),
        yonsuite=YonSuiteConfig(
            app_key=_mask(cfg.ys_app_key),
            app_secret=_mask(cfg.ys_app_secret),
            tenant_id=_mask(cfg.ys_tenant_id),
            gateway_url=cfg.ys_gateway_url,
        ),
        agent=AgentConfig(
            max_iterations=cfg.max_iterations,
            compaction_enabled=cfg.compaction_enabled,
            max_context_tokens=effective_ctx,
            max_context_tokens_auto=(raw_ctx == 0),
            reserve_tokens=cfg.reserve_tokens,
            keep_recent_tokens=cfg.keep_recent_tokens,
            approval_mode=cfg.approval_mode,
        ),
        version=_get_version(),
    )


@router.put("/llm")
def save_llm_config(body: LLMConfig):
    cfg = config_manager.load()
    # 只有非空且不是脱敏占位符时才更新（防前端编辑时误清空）
    if body.api_key and not body.api_key.startswith("***"):
        cfg.llm_api_key = body.api_key
    cfg.llm_base_url = body.base_url
    cfg.llm_model = body.model
    cfg.llm_provider = body.provider
    config_manager.save(cfg)
    return {"ok": True}


@router.put("/yonsuite")
async def save_yonsuite_config(body: YonSuiteConfig):
    cfg = config_manager.load()
    if body.app_key:
        cfg.ys_app_key = body.app_key
    if body.app_secret:
        cfg.ys_app_secret = body.app_secret
    if body.tenant_id:
        cfg.ys_tenant_id = body.tenant_id
    if body.gateway_url:
        cfg.ys_gateway_url = body.gateway_url
    config_manager.save(cfg)

    # Sync updated credentials into the yonsuite MCP server and reconnect
    servers = cfg.mcp_servers
    yonsuite = servers.get("yonsuite")
    if yonsuite:
        yonsuite.env = {
            "YONSUITE_APP_KEY": cfg.ys_app_key or "",
            "YONSUITE_APP_SECRET": cfg.ys_app_secret or "",
            "YONSUITE_TENANT_ID": cfg.ys_tenant_id or "",
            "YONSUITE_GATEWAY_URL": cfg.ys_gateway_url or "https://c2.yonyoucloud.com/iuap-api-gateway",
        }
        cfg.mcp_servers = servers
        config_manager.save(cfg)
        # Reconnect so new env takes effect immediately
        await _reconnect_mcp_yonsuite(yonsuite)

    return {"ok": True}


async def _reconnect_mcp_yonsuite(entry: MCPServerEntry):
    """Disconnect and reconnect the yonsuite MCP server with updated env vars."""
    try:
        await disconnect_server("yonsuite")
    except Exception:
        pass
    try:
        await connect_server("yonsuite", entry.model_dump())
    except Exception:
        pass


@router.put("/agent")
def save_agent_config(body: AgentConfig):
    cfg = config_manager.load()
    cfg.max_iterations = body.max_iterations
    cfg.compaction_enabled = body.compaction_enabled
    cfg.max_context_tokens = 0 if body.max_context_tokens_auto else body.max_context_tokens
    cfg.reserve_tokens = body.reserve_tokens
    cfg.keep_recent_tokens = body.keep_recent_tokens
    cfg.approval_mode = body.approval_mode
    config_manager.save(cfg)
    return {"ok": True}


@router.get("/providers", response_model=list[ProviderInfo])
def get_providers():
    items = [
        ProviderInfo(
            name=name,
            base_url=info["base_url"],
            models=[ModelInfo(**m) for m in info["models"]],
            api_key_label=info["api_key_label"],
            api_key_placeholder=info["api_key_placeholder"],
        )
        for name, info in LLM_PROVIDERS.items()
    ]
    items.append(
        ProviderInfo(
            name="自定义",
            base_url="",
            models=[],
            api_key_label="API Key",
            api_key_placeholder="",
        )
    )
    return items
