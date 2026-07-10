"""Shared utilities: rounding, name parsing, result builders, config loading, client singleton."""

import json
import os
import sys
from pathlib import Path

# Ensure project root on sys.path so agent/ imports work
if getattr(sys, "frozen", False):
    _PROJECT_ROOT = Path(sys._MEIPASS)
else:
    _PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))


def _load_ys_config() -> dict:
    # v1.4.0: 数据目录统一由 agent.utils 解析 (YS_DATA_DIR > ~/.ys-agent/data/)
    from agent.utils import DATA_DIR

    config_path = DATA_DIR / "config.json"
    if config_path.exists():
        try:
            cfg = json.loads(config_path.read_text("utf-8"))
        except (json.JSONDecodeError, OSError):
            cfg = {}
    else:
        cfg = {}

    for key, env_key in [
        ("ys_app_key", "YONSUITE_APP_KEY"),
        ("ys_app_secret", "YONSUITE_APP_SECRET"),
        ("ys_tenant_id", "YONSUITE_TENANT_ID"),
        ("ys_gateway_url", "YONSUITE_GATEWAY_URL"),
    ]:
        val = cfg.get(key, "")
        if val and not os.environ.get(env_key):
            os.environ[env_key] = val

    return cfg


_load_ys_config()

_ys_client = None


def get_client():
    global _ys_client
    if _ys_client is not None:
        return _ys_client
    from agent.yonsuite_client.config import config as ys_config

    if not ys_config.is_configured():
        return None
    from agent.yonsuite_client.ys_client import YonSuiteClient

    _ys_client = YonSuiteClient()
    return _ys_client


def r2(v) -> float:
    try:
        return round(float(v), 2)
    except (TypeError, ValueError):
        return 0.0


def parse_name(raw) -> str:
    """Customer/vendor name field is a nested dict, not a string."""
    if isinstance(raw, dict):
        return raw.get("simplifiedName") or raw.get("name") or ""
    return str(raw) if raw else ""


def tool_result(**kwargs) -> dict:
    return {"content": [{"type": "text", "text": json.dumps(kwargs, ensure_ascii=False, default=str)}]}


def tool_error(msg: str) -> dict:
    return {"content": [{"type": "text", "text": json.dumps({"error": msg}, ensure_ascii=False)}]}
