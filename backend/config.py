"""Server-level configuration."""

import os
from pathlib import Path

from dotenv import load_dotenv

from agent.utils import DATA_DIR


def _load_env_files() -> None:
    """Load .env candidates in order (override=False — env wins).

    User-level ``~/.zlink-agent/.env`` (``DATA_DIR.parent``) is the
    packaged/production source for keys like TAVILY_API_KEY (never bundled
    into the PyInstaller build); the repo-root ``.env`` remains the dev
    fallback.
    """
    candidates = [
        DATA_DIR.parent / ".env",                        # ~/.zlink-agent/.env
        Path(__file__).resolve().parent.parent / ".env",  # repo root (dev)
    ]
    for p in candidates:
        if p.exists():
            load_dotenv(p, override=False)


_load_env_files()

HOST = os.environ.get("ZLINK_AGENT_HOST", "0.0.0.0")
PORT = int(os.environ.get("ZLINK_AGENT_PORT", "8089"))
CORS_ORIGINS = os.environ.get("ZLINK_AGENT_CORS", "http://localhost:8088").split(",")
