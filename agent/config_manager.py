"""Persistent configuration for ZLink Agent.

ALL settings (API keys, passwords, ERP config) go into a single
data/config.json as plain JSON. The data directory is chmod 0700 and
the config file is chmod 0600 (owner-only) every time it is written.

This is the simplest possible storage — no encryption, no .env split,
no two-file sync, no field stripping. Operators who require at-rest
encryption should run ZLink Agent on an encrypted filesystem (e.g.
FileVault / LUKS / BitLocker) or front it with an OS-level secret store.
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
    """Ensure the data directory has owner-only (0700) permissions.

    Best-effort: silently no-ops on filesystems that do not support
    chmod (e.g. some Windows volumes, certain network mounts).
    """
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    try:
        os.chmod(str(DATA_DIR), stat.S_IRWXU)
    except OSError:
        pass


def _secure_config_file():
    """Tighten CONFIG_FILE to owner-only (0600).

    Best-effort.  Called from :func:`save` after every write so that
    secrets stored as plain JSON are not readable by other local users.
    """
    if not CONFIG_FILE.exists():
        return
    try:
        # 0o600 = owner read + owner write. Do NOT grant execute.
        os.chmod(CONFIG_FILE, stat.S_IRUSR | stat.S_IWUSR)
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
    """Write everything to config.json — no stripping, no split, no sync.

    After writing, the file is chmod'd to 0600 (owner read/write only)
    so plain-text secrets are not accessible to other local users.
    """
    _secure_data_dir()
    data = cfg.model_dump(mode="json")
    atomic_json_write(CONFIG_FILE, data)
    _secure_config_file()


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
