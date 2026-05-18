#!/usr/bin/env python3
"""Backward-compat shim: delegates to mcp_server.ys_mcp_server package.

Previously the entire MCP server lived in this single file.
Now it's split into mcp_server/ys_mcp_server/ with one handler per tool.
"""

import sys
from pathlib import Path

# Ensure project root on sys.path for mcp_server import
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from mcp_server.ys_mcp_server.server import main

if __name__ == "__main__":
    main()
