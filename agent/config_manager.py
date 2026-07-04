"""Persistent configuration for YS-Agent.

Saves/loads LLM and YonSuite settings to data/config.json
so they survive browser refreshes and server restarts.
"""

from __future__ import annotations

import json

from agent.config_model import AppConfig
from agent.utils import DATA_DIR, atomic_json_write

CONFIG_FILE = DATA_DIR / "config.json"


def load() -> AppConfig:
    """Load persisted config as a validated AppConfig."""
    if not CONFIG_FILE.exists():
        return AppConfig()
    try:
        data = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
        return AppConfig.model_validate_decrypted(data)
    except (json.JSONDecodeError, OSError, ValueError):
        return AppConfig()


def save(cfg: AppConfig):
    """Persist an AppConfig to disk."""
    CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
    atomic_json_write(CONFIG_FILE, cfg.model_dump_encrypted())
