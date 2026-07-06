"""PyInstaller hook: ensure web/dist is collected as data for frozen backend."""

import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_WEB_DIST = _PROJECT_ROOT / "web" / "dist"

if _WEB_DIST.is_dir() and getattr(sys, "frozen", False):
    import os

    os.environ.setdefault("YS_STATIC_DIR", str(_WEB_DIST))
