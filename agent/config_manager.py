"""Persistent configuration for YS-Agent.

Saves/loads LLM and YonSuite settings to data/config.json
so they survive browser refreshes and server restarts.
"""

import json
from pathlib import Path

from agent.utils import atomic_json_write, DATA_DIR

CONFIG_FILE = DATA_DIR / "config.json"

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
}


def load() -> dict:
    """Load persisted config, filling missing keys with defaults."""
    if not CONFIG_FILE.exists():
        return dict(_DEFAULT_CONFIG)
    try:
        data = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
        result = dict(_DEFAULT_CONFIG)
        result.update(data)
        return result
    except (json.JSONDecodeError, OSError):
        return dict(_DEFAULT_CONFIG)


def save(data: dict):
    """Persist config dict to disk (only known keys)."""
    payload = {k: data.get(k, v) for k, v in _DEFAULT_CONFIG.items()}
    CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
    atomic_json_write(CONFIG_FILE, payload)
