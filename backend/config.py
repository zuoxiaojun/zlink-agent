"""Server-level configuration."""

import os
import sys
from pathlib import Path

from dotenv import load_dotenv

# 从项目根目录 .env 加载环境变量（PyInstaller 打包后忽略）
if not getattr(sys, "frozen", False):
    load_dotenv(Path(__file__).resolve().parent.parent / ".env")

HOST = os.environ.get("ZLINK_AGENT_HOST", "0.0.0.0")
PORT = int(os.environ.get("ZLINK_AGENT_PORT", "8089"))
CORS_ORIGINS = (
    ["*"] if getattr(sys, "frozen", False) else os.environ.get("ZLINK_AGENT_CORS", "http://localhost:8088").split(",")
)
