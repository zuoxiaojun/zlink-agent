#!/usr/bin/env python3
"""YS-Agent launcher for PyInstaller packaged builds.

Two modes:
  1. (default)  Start uvicorn serving backend.main:app
  2. --mcp-server  Run the YonSuite MCP server (spawned as subprocess by main process)
"""

import os
import sys
from pathlib import Path


def _setup_frozen_env():
    """Configure runtime paths for frozen (PyInstaller) mode."""
    # Data dir — user's home, writable at runtime
    data_dir = Path.home() / ".ys-agent" / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    os.environ.setdefault("YS_DATA_DIR", str(data_dir))

    # When frozen, _MEIPASS is the _internal/ directory where all files live.
    # sys.path already includes it from PyInstaller bootstrap, but we also
    # add it explicitly for safety.
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        meipass = sys._MEIPASS  # path to _internal/
        if meipass not in sys.path:
            sys.path.insert(0, meipass)


def main():
    _setup_frozen_env()

    # ── MCP server subprocess mode ──────────────────────────────────────
    if "--mcp-server" in sys.argv:
        from mcp_server.ys_mcp_server.server import main as mcp_main
        mcp_main()
        return

    # ── Main server mode ────────────────────────────────────────────────
    from backend.main import app
    from backend.config import HOST, PORT
    import uvicorn

    uvicorn.run(
        app,
        host=HOST,
        port=PORT,
        log_level="info",
        # Don't auto-reload — no source watcher in frozen mode
        reload=False,
    )


if __name__ == "__main__":
    main()
