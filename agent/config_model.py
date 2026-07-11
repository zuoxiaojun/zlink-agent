"""Pydantic config model for ZLink Agent persistent settings."""

from __future__ import annotations

import base64
import hashlib
import socket
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

_ENCRYPTED_FIELDS = {"llm_api_key", "ys_app_key", "ys_app_secret"}

# Known ERP secret sub-fields stored under erp_clients.<name>
_ERP_SECRET_FIELDS: dict[str, tuple[str, ...]] = {
    "yonsuite": ("app_key", "app_secret"),
    "nc": ("password",),
}


def _derive_key() -> bytes:
    raw = socket.gethostname() + "::zlink-agent::salt_v1"
    return hashlib.sha256(raw.encode()).digest()


def _encrypt(plain: str) -> str:
    if not plain:
        return ""
    from cryptography.fernet import Fernet

    key = base64.urlsafe_b64encode(_derive_key())
    return Fernet(key).encrypt(plain.encode()).decode()


def _decrypt(cipher: str) -> str:
    if not cipher:
        return ""
    from cryptography.fernet import Fernet

    key = base64.urlsafe_b64encode(_derive_key())
    return Fernet(key).decrypt(cipher.encode()).decode()


class ApprovalMode(str, Enum):
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
    llm_api_key: str = ""
    llm_base_url: str = "https://api.openai.com/v1"
    llm_model: str = "gpt-4o"
    llm_provider: str = "OpenAI"
    ys_app_key: str = ""
    ys_app_secret: str = ""
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

    def model_dump_encrypted(self, **kwargs) -> dict[str, Any]:
        kwargs.setdefault("mode", "json")
        data = self.model_dump(**kwargs)
        for field in _ENCRYPTED_FIELDS:
            val = data.get(field, "")
            if val:
                data[field] = _encrypt(val)
        # 加密 erp_clients 中的 secret 字段
        erp = data.get("erp_clients")
        if isinstance(erp, dict):
            for name, cfg in erp.items():
                if not isinstance(cfg, dict):
                    continue
                for secret_field in _ERP_SECRET_FIELDS.get(name, ()):
                    val = cfg.get(secret_field)
                    if val and not val.startswith("encrypted:"):
                        cfg[secret_field] = "encrypted:" + _encrypt(val)
        return data

    @classmethod
    def model_validate_decrypted(cls, data: dict[str, Any]) -> AppConfig:
        decrypted = dict(data)
        for field in _ENCRYPTED_FIELDS:
            val = decrypted.get(field, "")
            if val and val.startswith("gAAAAA"):
                try:
                    decrypted[field] = _decrypt(val)
                except Exception:
                    decrypted[field] = ""
        # 解密 erp_clients 中的 secret 字段
        erp = decrypted.get("erp_clients")
        if isinstance(erp, dict):
            for name, cfg in erp.items():
                if not isinstance(cfg, dict):
                    continue
                for secret_field in _ERP_SECRET_FIELDS.get(name, ()):
                    val = cfg.get(secret_field)
                    if isinstance(val, str) and val.startswith("encrypted:"):
                        token = val.split(":", 1)[1]
                        try:
                            cfg[secret_field] = _decrypt(token)
                        except Exception:
                            cfg[secret_field] = ""
        return cls.model_validate(decrypted)
