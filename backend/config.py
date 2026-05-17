"""Server-level configuration."""

import os
from pathlib import Path
from dotenv import load_dotenv

# 从项目根目录 .env 加载环境变量
load_dotenv(Path(__file__).resolve().parent.parent / ".env")

HOST = os.environ.get("YS_AGENT_HOST", "0.0.0.0")
PORT = int(os.environ.get("YS_AGENT_PORT", "8089"))
CORS_ORIGINS = os.environ.get("YS_AGENT_CORS", "http://localhost:8088").split(",")
