"""Configuration loader for YS-Agent.

Loads settings from .env file (project root) and environment variables.
"""

import os
from pathlib import Path
from dotenv import load_dotenv


def load_config() -> None:
    """Load .env from project root."""
    env_path = Path(__file__).resolve().parent.parent / ".env"
    if env_path.exists():
        load_dotenv(env_path)


def get_llm_config() -> dict:
    """Return LLM API configuration."""
    return {
        "api_key": os.getenv("LLM_API_KEY", ""),
        "base_url": os.getenv("LLM_BASE_URL", "https://api.openai.com/v1"),
        "model": os.getenv("LLM_MODEL", "gpt-4o"),
    }


def get_yonsuite_config() -> dict:
    """Return YonSuite API configuration."""
    return {
        "app_key": os.getenv("YONSUITE_APP_KEY", ""),
        "app_secret": os.getenv("YONSUITE_APP_SECRET", ""),
        "base_url": os.getenv("YONSUITE_BASE_URL", ""),
    }
