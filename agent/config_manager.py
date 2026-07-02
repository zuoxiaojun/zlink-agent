"""Persistent configuration for YS-Agent.

Saves/loads LLM and YonSuite settings to data/config.json
so they survive browser refreshes and server restarts.
"""

import base64
import hashlib
import json
import socket

from agent.utils import DATA_DIR, atomic_json_write

CONFIG_FILE = DATA_DIR / "config.json"

_ENCRYPTED_FIELDS = {"llm_api_key"}

_DEFAULT_CONFIG = {
    "llm_api_key": "",
    "llm_base_url": "https://api.openai.com/v1",
    "llm_model": "gpt-4o",
    "llm_provider": "OpenAI",
    "ys_app_key": "",
    "ys_app_secret": "",
    "ys_tenant_id": "",
    "ys_gateway_url": "https://c2.yonyoucloud.com/iuap-api-gateway",
    "max_iterations": 30,
    "compaction_enabled": True,
    "max_context_tokens": 0,  # 0 = auto-detect from model
    "reserve_tokens": 4000,
    "keep_recent_tokens": 8000,
    "mcp_servers": {},
    "disabled_extensions": [],  # M5+: names of extensions the user turned off
}


def _derive_key() -> bytes:
    raw = socket.gethostname() + "::ys-agent::salt_v1"
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


def load() -> dict:
    """Load persisted config, filling missing keys with defaults."""
    if not CONFIG_FILE.exists():
        return dict(_DEFAULT_CONFIG)
    try:
        data = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
        result = dict(_DEFAULT_CONFIG)
        result.update(data)
        for field in _ENCRYPTED_FIELDS:
            val = result.get(field, "")
            if val and not val.startswith("gAAAAA"):
                continue
            try:
                result[field] = _decrypt(val) if val else ""
            except Exception:
                result[field] = ""
        return result
    except (json.JSONDecodeError, OSError):
        return dict(_DEFAULT_CONFIG)


def save(data: dict):
    """Persist config dict to disk (only known keys)."""
    payload = {k: data.get(k, v) for k, v in _DEFAULT_CONFIG.items()}
    for field in _ENCRYPTED_FIELDS:
        val = payload.get(field, "")
        if val:
            payload[field] = _encrypt(val)
    CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
    atomic_json_write(CONFIG_FILE, payload)
