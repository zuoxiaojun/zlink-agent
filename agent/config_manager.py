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

# === v1.5.0 新增: ERP 客户端配置支持 ===

def get_erp_config(name: str) -> dict:
    """
    获取指定 ERP 客户端的配置 (从原始 config.json 读 dict)

    优先级:
    1. erp_clients[name]
    2. yonsuite 字段 (仅 name="yonsuite", 向后兼容)
    3. 返回空 dict
    """
    import json
    try:
        raw = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}
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
            parts = path.split(".")
            current = config
            for part in parts:
                if isinstance(current, dict) and part in current:
                    current = current[part]
                else:
                    return match.group(0)
            return str(current)
        return pattern.sub(replacer, value)

    return {k: resolve_value(v) for k, v in env.items()}

