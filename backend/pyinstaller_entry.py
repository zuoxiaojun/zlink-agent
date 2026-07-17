"""PyInstaller entry point — starts uvicorn with the FastAPI app.

This script is only used when building the PyInstaller binary.
It is NOT part of the normal source code import chain.
"""
import os
import sys
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