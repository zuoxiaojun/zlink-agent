"""PyInstaller entry point — runs the FastAPI app via uvicorn.

This module is a thin wrapper so PyInstaller can produce a single binary
that bootstraps the entire backend (FastAPI + agent + tools + static files).
"""

import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

import uvicorn

if __name__ == "__main__":
    host = "127.0.0.1"
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8089
    uvicorn.run("backend.main:app", host=host, port=port, log_level="info")
