"""Persistent configuration for ZLink Agent.

Saves/loads LLM and YonSuite settings to data/config.json
so they survive browser refreshes and server restarts.
"""

from __future__ import annotations

import json

from agent.config_model import AppConfig, _decrypt, _encrypt
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


# Known ERP secret fields stored under config.json -> erp_clients.<name>
ERP_SECRET_FIELDS = {
    "yonsuite": ("app_key", "app_secret"),
    "nc": ("password",),
}


def encrypt_secret(plain: str) -> str:
    """Encrypt a user-facing secret and tag it with an explicit prefix."""
    if not plain:
        return ""
    if plain.startswith("encrypted:"):
        return plain
    return "encrypted:" + _encrypt(plain)


def decrypt_secret(value: str) -> str:
    """Decrypt a tagged ERP secret; return the original value if it is not encrypted."""
    if not value:
        return ""
    if value.startswith("encrypted:"):
        token = value.split(":", 1)[1]
        try:
            return _decrypt(token)
        except Exception:
            return ""
    # Backward compatibility with older Fernet-only values used by AppConfig.
    if value.startswith("gAAAAA"):
        try:
            return _decrypt(value)
        except Exception:
            return ""
    return value


def _decrypt_erp_clients(raw: dict) -> dict:
    """Return a copy of raw config with known ERP secret fields decrypted."""
    data = dict(raw)
    erp_clients = data.get("erp_clients")
    if isinstance(erp_clients, dict):
        erp_copy = {}
        for name, cfg in erp_clients.items():
            if not isinstance(cfg, dict):
                erp_copy[name] = cfg
                continue
            item = dict(cfg)
            for field in ERP_SECRET_FIELDS.get(name, ()):  # only known secret fields
                val = item.get(field)
                if isinstance(val, str):
                    item[field] = decrypt_secret(val)
            erp_copy[name] = item
        data["erp_clients"] = erp_copy
    return data


def get_config(*, decrypt_secrets: bool = True) -> dict:
    """Load raw config.json as a dict, optionally decrypting ERP secret fields."""
    try:
        raw = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}
    return _decrypt_erp_clients(raw) if decrypt_secrets else raw


# === v1.5.0 新增: ERP 客户端配置支持 ===


def get_erp_config(name: str) -> dict:
    """
    获取指定 ERP 客户端的配置 (从原始 config.json 读 dict)

    优先级:
    1. erp_clients[name]
    2. yonsuite 字段 (仅 name="yonsuite", 向后兼容)
    3. 返回空 dict
    """
    raw = get_config(decrypt_secrets=True)
    erp_clients = raw.get("erp_clients", {})
    if name in erp_clients:
        return erp_clients[name]
    # 向后兼容: 旧版 yonsuite 字段
    if name == "yonsuite" and "yonsuite" in raw:
        return raw["yonsuite"]
    return {}


def resolve_placeholders(env: dict, config: dict) -> dict:
    """
    解析 env 字典里的 ${path.to.value} 占位符

    例子:
        env = {"ORACLE_HOST": "${nc.host}"}
        config = {"erp_clients": {"nc": {"host": "1.2.3.4"}}}
        → {"ORACLE_HOST": "1.2.3.4"}

    占位符引用不存在路径时, 保留字面量 (启动时报错定位更明确)
    """
    import re

    pattern = re.compile(r"\$\{([^}]+)\}")

    def resolve_value(value):
        if not isinstance(value, str):
            return value

        def replacer(match):
            path = match.group(1)
            # 智能前缀: 如果第一段是 "nc"/"yonsuite" 等已知 ERP 名, 自动补 "erp_clients." 前缀
            erp_names = {"nc", "yonsuite", "sap", "kingdee"}  # 可扩展
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
            if isinstance(current, str):
                current = decrypt_secret(current)
            return str(current)

        return pattern.sub(replacer, value)

    return {k: resolve_value(v) for k, v in env.items()}
