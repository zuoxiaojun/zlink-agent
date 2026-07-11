"""Entry point: python -m nc_mcp_server"""

import asyncio

from .server import main

asyncio.run(main())
