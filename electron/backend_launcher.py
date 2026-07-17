"""Launcher script for the bundled Python backend in Electron.

This script is run by the bundled Python interpreter.  It adds the
project source directory to sys.path so that backend.main can be
imported, then starts uvicorn.
"""

import os
import sys
from pathlib import Path

# When running from Electron.app/Contents/Resources/
# this script is at Resources/backend_launcher.py
# The project source is at Resources/app/ (from electron-builder extraResources)
LAUNCHER_DIR = Path(__file__).resolve().parent
PROJECT_DIR = LAUNCHER_DIR / "app"

if PROJECT_DIR.is_dir():
    sys.path.insert(0, str(PROJECT_DIR))
else:
    # Fallback: development layout (script is in electron/ next to the project)
    sys.path.insert(0, str(LAUNCHER_DIR.parent))

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "backend.main:app",
        host="0.0.0.0",
        port=int(os.environ.get("ZLINK_AGENT_PORT", "8089")),
        log_level="info",
        access_log=False,
    )