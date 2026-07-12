"""Persistent configuration for ZLink Agent.

Non-secret settings → data/config.json (plain JSON).
Secrets (API keys, passwords) → data/.env (plaintext, chmod 0600).

This matches Hermes Agent's approach: no encryption, OS file permissions.
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

# Fields stored in .env instead of config.json
_SECRET_FIELDS: dict[str, str] = {
    "llm_api_key": "LLM_API_KEY",
    "ys_app_key": "YS_APP_KEY",
    "ys_app_secret": "YS_APP_SECRET",
}

# ERP secret sub-fields stored under erp_clients.<name>
ERP_SECRET_FIELDS: dict[str, tuple[str, ...]] = {
    "yonsuite": ("app_key", "app_secret"),
    "nc": ("password",),
}

# ── .env helpers ─────────────────────────────────────────────────────────


def _env_path() -> str:
    return str(ENV_FILE)


def _ensure_env():
    """Create data/ dir and .env with secure permissions."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    if not ENV_FILE.exists():
        ENV_FILE.write_text("", encoding="utf-8")
    _secure_file(str(ENV_FILE))


def _secure_file(path: str):
    """Set file to owner-only read/write (0o600).  No-op on Windows."""
    try:
        os.chmod(path, stat.S_IRUSR | stat.S_IWUSR)
    except OSError:
        pass


def _load_env() -> dict[str, str]:
    """Parse data/.env into a dict of KEY=VALUE."""
    _ensure_env()
    result: dict[str, str] = {}
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
    """Update a single key in data/.env, preserving other entries."""
    _ensure_env()
    try:
        lines = ENV_FILE.read_text(encoding="utf-8").splitlines()
    except OSError:
        lines = []
    # Remove existing entry for this key
    lines = [line for line in lines if not line.strip().startswith(f"{key}=")]
    if value:
        lines.append(f"{key}={value}")
    ENV_FILE.write_text("\n".join(lines) + "\n", encoding="utf-8")
    _secure_file(str(ENV_FILE))


def _save_env_batch(updates: dict[str, str]):
    """Replace the entire .env with the given key-value pairs."""
    _ensure_env()
    content = "\n".join(f"{k}={v}" for k, v in sorted(updates.items()) if v)
    ENV_FILE.write_text(content + "\n", encoding="utf-8")
    _secure_file(str(ENV_FILE))


def _load_env_erp_secrets() -> dict[str, dict[str, str]]:
    """Load ERP secret fields from .env (stored as ERP_{NAME}_{FIELD})."""
    env = _load_env()
    result: dict[str, dict[str, str]] = {}
    for erp_name, fields in ERP_SECRET_FIELDS.items():
        prefix = f"ERP_{erp_name.upper()}_"
        secrets: dict[str, str] = {}
        for field in fields:
            key = f"{prefix}{field.upper()}"
            val = env.get(key, "")
            if val:
                secrets[field] = val
        if secrets:
            result[erp_name] = secrets
    return result


def _save_erp_secret(erp_name: str, field: str, value: str):
    """Save a single ERP secret to .env."""
    key = f"ERP_{erp_name.upper()}_{field.upper()}"
    _save_env_value(key, value)


# ── AppConfig load / save ────────────────────────────────────────────────


def load() -> AppConfig:
    """Load config.json + overlay secrets from .env."""
    if not CONFIG_FILE.exists():
        cfg = AppConfig()
    else:
        try:
            data = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
            cfg = AppConfig.model_validate(data)
        except (json.JSONDecodeError, OSError, ValueError):
            cfg = AppConfig()

    # Overlay secrets from .env
    env = _load_env()
    for model_field, env_key in _SECRET_FIELDS.items():
        if env_key in env:
            setattr(cfg, model_field, env[env_key])

    # Overlay ERP secrets from .env
    erp_secrets = _load_env_erp_secrets()
    for erp_name, secrets in erp_secrets.items():
        if erp_name not in cfg.erp_clients:
            cfg.erp_clients[erp_name] = {}
        cfg.erp_clients[erp_name].update(secrets)

    return cfg


def save(cfg: AppConfig):
    """Persist non-secret fields to config.json, secrets to .env."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    # Save non-secret fields to config.json
    data = cfg.model_dump(mode="json")
    for field in _SECRET_FIELDS:
        data.pop(field, None)
    # Also strip ERP secrets from erp_clients before saving to json
    erp = data.get("erp_clients", {})
    if isinstance(erp, dict):
        for erp_name, fields in ERP_SECRET_FIELDS.items():
            ecfg = erp.get(erp_name)
            if isinstance(ecfg, dict):
                for f in fields:
                    ecfg.pop(f, None)
    atomic_json_write(CONFIG_FILE, data)

    # Save secrets to .env
    env = _load_env()
    for model_field, env_key in _SECRET_FIELDS.items():
        val = getattr(cfg, model_field, "")
        if val:
            env[env_key] = val
        else:
            env.pop(env_key, None)
    # Save ERP secrets
    for erp_name, fields in ERP_SECRET_FIELDS.items():
        ecfg = cfg.erp_clients.get(erp_name, {})
        if isinstance(ecfg, dict):
            for field in fields:
                val = ecfg.get(field, "")
                env_key = f"ERP_{erp_name.upper()}_{field.upper()}"
                if val:
                    env[env_key] = val
                else:
                    env.pop(env_key, None)
    _save_env_batch(env)


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
