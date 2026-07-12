"""Persistent configuration for ZLink Agent.

All settings (including API keys and passwords) are stored in a single
data/config.json file as plain JSON. Data directory is secured with
owner-only permissions (chmod 0700).

This is the simplest possible storage approach — no encryption, no .env split.
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
ENV_FILE = DATA_DIR / ".env"

# Known secret fields for ERP clients (used by erp_clients_api.py)
ERP_SECRET_FIELDS: dict[str, tuple[str, ...]] = {
    "yonsuite": ("app_key", "app_secret"),
    "nc": ("password",),
}


def _secure_data_dir():
    """Set data directory to owner-only access (0700)."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    try:
        os.chmod(str(DATA_DIR), stat.S_IRWXU)
    except OSError:
        pass


# ── .env helpers (kept for backward compat, no longer used by load/save) ─


def _load_env() -> dict[str, str]:
    """Parse data/.env into a dict of KEY=VALUE."""
    result: dict[str, str] = {}
    if not ENV_FILE.exists():
        return result
    try:
        for line in ENV_FILE.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" not in line:
                continue
            key, _, val = line.partition("=")
            result[key.strip()] = val.strip()
    except OSError:
        pass
    return result


def _save_env_value(key: str, value: str):
    """Write a single key to .env for backward compat with erp_clients_api.py."""
    env = _load_env()
    if value:
        env[key] = value
    else:
        env.pop(key, None)
    _write_env(env)


def _write_env(env: dict[str, str]):
    """Write the .env file. Also syncs values into config.json."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    content = "\n".join(f"{k}={v}" for k, v in sorted(env.items()) if v)
    ENV_FILE.write_text(content + "\n" if content else "", encoding="utf-8")
    try:
        os.chmod(str(ENV_FILE), stat.S_IRUSR | stat.S_IWUSR)
    except OSError:
        pass
    # Sync .env values back into config.json so load() sees them
    _sync_env_to_config(env)


def _save_erp_secret(erp_name: str, field: str, value: str):
    """Save a single ERP secret to both .env and config.json."""
    env_key = f"ERP_{erp_name.upper()}_{field.upper()}"
    _save_env_value(env_key, value)
    # Also update config.json in-place
    _sync_env_to_config({env_key: value})


def _sync_env_to_config(env: dict[str, str]):
    """Migrate .env values into config.json so they survive a load/save cycle."""
    if not CONFIG_FILE.exists():
        return
    try:
        data = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
        changed = False
        # Map .env keys → config.json paths
        env_map: dict[str, tuple[str, ...]] = {
            "LLM_API_KEY": ("llm_api_key",),
            "YS_APP_KEY": ("ys_app_key",),
            "YS_APP_SECRET": ("ys_app_secret",),
            "ERP_YONSUITE_APP_KEY": ("erp_clients", "yonsuite", "app_key"),
            "ERP_YONSUITE_APP_SECRET": ("erp_clients", "yonsuite", "app_secret"),
            "ERP_NC_PASSWORD": ("erp_clients", "nc", "password"),
        }
        for env_key, path in env_map.items():
            if env_key not in env:
                continue
            val = env[env_key]
            d = data
            for p in path[:-1]:
                if p not in d or not isinstance(d[p], dict):
                    d[p] = {}
                d = d[p]
            if d.get(path[-1]) != val:
                d[path[-1]] = val
                changed = True
        if changed:
            atomic_json_write(CONFIG_FILE, data)
    except Exception:
        pass


# ── AppConfig load / save ────────────────────────────────────────────────


def load() -> AppConfig:
    """Load config from config.json (everything is in one place)."""
    _secure_data_dir()
    if not CONFIG_FILE.exists():
        cfg = AppConfig()
        # Check if .env has data (migration path)
        env = _load_env()
        if env:
            _sync_env_to_config(env)
            # Re-read after sync
            try:
                data = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
                cfg = AppConfig.model_validate(data)
            except Exception:
                pass
        return cfg
    try:
        data = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
        return AppConfig.model_validate(data)
    except (json.JSONDecodeError, OSError, ValueError):
        return AppConfig()


def save(cfg: AppConfig):
    """Persist everything to config.json (single file, no .env split)."""
    _secure_data_dir()
    data = cfg.model_dump(mode="json")
    atomic_json_write(CONFIG_FILE, data)

    # Also sync to .env for backward compat with erp_clients_api.py
    env = _load_env()
    changed = False
    llm_key = cfg.llm_api_key or ""
    if llm_key and env.get("LLM_API_KEY") != llm_key:
        env["LLM_API_KEY"] = llm_key
        changed = True
    elif not llm_key and "LLM_API_KEY" in env:
        del env["LLM_API_KEY"]
        changed = True
    for erp_name, fields in ERP_SECRET_FIELDS.items():
        ecfg = cfg.erp_clients.get(erp_name, {})
        if isinstance(ecfg, dict):
            for field in fields:
                val = ecfg.get(field, "") or ""
                env_key = f"ERP_{erp_name.upper()}_{field.upper()}"
                if val and env.get(env_key) != val:
                    env[env_key] = val
                    changed = True
                elif not val and env_key in env:
                    del env[env_key]
                    changed = True
    if changed:
        _write_env(env)
    elif not ENV_FILE.exists() or ENV_FILE.stat().st_size == 0:
        # Ensure .env exists with current values
        _write_env(env)


# ── ERP helpers (backward compatible) ────────────────────────────────────


def get_erp_config(name: str) -> dict:
    """
    获取指定 ERP 客户端的配置 (含 .env 中的 secret).
    """
    cfg = load()
    ecfg = cfg.erp_clients.get(name, {})
    # If ecfg only came from .env (not in config.json), ensure we return it
    result = dict(ecfg) if ecfg else {}
    if not result:
        # Backward compat: old yonsuite top-level fields
        if name == "yonsuite":
            result = {
                "app_key": cfg.ys_app_key or "",
                "app_secret": cfg.ys_app_secret or "",
            }
    return result


# ── Placeholder resolver for MCP env vars ───────────────────────────────


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
