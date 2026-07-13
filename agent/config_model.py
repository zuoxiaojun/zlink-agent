"""Pydantic config model for ZLink Agent persistent settings.

All fields — including secrets (LLM API key, ERP app keys/passwords) — are
persisted as plain JSON in ``data/config.json`` via ``config_manager``.  The
file is written atomically (``atomic_json_write``) and chmod'd to ``0o600``
at save time so it is only readable by the owner.  There is no encryption
layer; the data directory itself is chmod'd ``0o700``.  See
``config_manager.py`` for load/save and permission handling.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class ApprovalMode(StrEnum):
    """Command approval mode for tool execution security."""

    ALLOW_ALL = "allow_all"
    APPROVE_HIGH_RISK = "approve"
    REJECT_ALL = "reject_all"


class MCPServerEntry(BaseModel):
    transport: str = "stdio"
    enabled: bool = True
    timeout: int = 120
    command: str | None = None
    args: list[str] = []
    url: str | None = None
    headers: dict[str, str] = {}
    env: dict[str, str] = {}
    builtin: bool = False


class AppConfig(BaseModel):
    # Non-secret fields
    llm_base_url: str = "https://api.openai.com/v1"
    llm_model: str = "gpt-4o"
    llm_provider: str = "OpenAI"
    ys_tenant_id: str = ""
    ys_gateway_url: str = "https://c2.yonyoucloud.com/iuap-api-gateway"
    max_iterations: int = Field(default=30, ge=5, le=50)
    compaction_enabled: bool = True
    max_context_tokens: int = Field(default=0, ge=0, description="0 = auto-detect from model")
    reserve_tokens: int = Field(default=4000, ge=1000, le=32000)
    keep_recent_tokens: int = Field(default=8000, ge=2000, le=128000)
    mcp_servers: dict[str, MCPServerEntry] = {}
    erp_clients: dict[str, dict[str, Any]] = {}
    disabled_extensions: list[str] = []
    approval_mode: str = "allow_all"

    # Secret fields (empty in model — loaded from .env at runtime)
    llm_api_key: str = ""
    ys_app_key: str = ""
    ys_app_secret: str = ""
