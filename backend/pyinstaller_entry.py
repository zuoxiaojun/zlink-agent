"""PyInstaller entry point — starts uvicorn with the FastAPI app.

This script is only used when building the PyInstaller binary.
It is NOT part of the normal source code import chain.
"""
import os
import sys

# PyInstaller frozen mode: point SSL to certifi's CA bundle
# macOS 钥匙串证书在 PyInstaller 中不可用，必须使用 certifi 自带的证书
if getattr(sys, "frozen", False):
    import certifi

    os.environ.setdefault("SSL_CERT_FILE", certifi.where())
    os.environ.setdefault("REQUESTS_CA_BUNDLE", certifi.where())

from pathlib import Path

# Ensure project root is on sys.path so agent/ imports work
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from backend.main import app
import uvicorn

port = int(os.environ.get("ZLINK_AGENT_PORT", "8089"))

uvicorn.run(
    app,
    host="0.0.0.0",
    port=port,
    log_level="info",
    access_log=False,
)