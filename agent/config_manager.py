"""Persistent configuration for ZLink Agent.

ALL settings (API keys, passwords, ERP config) go into a single
data/config.json as plain JSON. Data directory is chmod 0700.

This is the simplest possible storage — no encryption, no .env split,
no two-file sync, no field stripping.
"""

from __future__ import annotations

import json
import logging
import os
import stat

from agent.config_model import AppConfig
from agent.utils import DATA_DIR, atomic_json_write

logger = logging.getLogger(__name__)

CONFIG_FILE = DATA_DIR / "config.json"


def _secure_data_dir():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    try:
        os.chmod(str(DATA_DIR), stat.S_IRWXU)
    except OSError:
        pass


def load() -> AppConfig:
    """Read everything from config.json — single source of truth."""
    _secure_data_dir()
    if not CONFIG_FILE.exists():
        return AppConfig()
    try:
        data = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
        return AppConfig.model_validate(data)
    except (json.JSONDecodeError, OSError, ValueError):
        return AppConfig()


def save(cfg: AppConfig):
    """Write everything to config.json — no stripping, no split, no sync."""
    _secure_data_dir()
    data = cfg.model_dump(mode="json")
    atomic_json_write(CONFIG_FILE, data)


# ── ERP helpers ─────────────────────────────────────────────────────


def get_erp_config(name: str) -> dict:
    cfg = load()
    ecfg = cfg.erp_clients.get(name, {})
    if isinstance(ecfg, dict):
        return dict(ecfg)
    if name == "yonsuite":
        return {
            "app_key": cfg.ys_app_key or "",
            "app_secret": cfg.ys_app_secret or "",
        }
    return {}


# ── Placeholder resolver for MCP env vars ──────────────────────────


def resolve_placeholders(env: dict, config: dict) -> dict:
    """Resolve ${path.to.value} placeholders in env values."""
    import re

    pattern = re.compile(r"\$\{([^}]+)\}")

    def resolve_value(value):
        if not isinstance(value, str):
            return value

        def replacer(match):
            path = match.group(1)
            erp_names = {"nc", "yonsuite", "sap", "kingdee"}
            parts = path.split(".")
            if parts[0] in erp_names and not path.startswith("erp_clients."):
                full_path = "erp_clients." + path
            else:
                full_path = path
            full_parts = full_path.split(".")
            current = config
            for part in full_parts:
                if isinstance(current, dict) and part in current:
                    current = current[part]
                else:
                    return match.group(0)
            return str(current) if not isinstance(current, (dict, list)) else match.group(0)

        return pattern.sub(replacer, value)

    return {k: resolve_value(v) for k, v in env.items()}