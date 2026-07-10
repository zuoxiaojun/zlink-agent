"""YS-Agent backend — entry point for `python -m backend`."""

import sys
from pathlib import Path

# Add project root to sys.path
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

# If frozen (PyInstaller), handle --mcp-server mode
if getattr(sys, "frozen", False):
    if "--mcp-server" in sys.argv:
        from mcp_server.ys_mcp_server.server import main as mcp_main

        mcp_main()
        sys.exit(0)

import uvicorn

from backend.config import HOST, PORT
from backend.main import app

uvicorn.run(app, host=HOST, port=PORT, log_level="info")
