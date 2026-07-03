"""YS-Agent FastAPI backend — serves REST API + WebSocket for the React frontend."""

import logging
import sys
from pathlib import Path

# Ensure project root is on sys.path so agent/ imports work
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

if getattr(sys, "frozen", False):
    import os

    os.environ.setdefault("YS_DATA_DIR", str(Path.home() / ".ys-agent" / "data"))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from agent.utils import DATA_DIR
from backend.config import CORS_ORIGINS

# Logging setup
_LOG_DIR = DATA_DIR / "logs"
_LOG_DIR.mkdir(parents=True, exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
    handlers=[
        logging.StreamHandler(sys.stderr),
        logging.FileHandler(str(_LOG_DIR / "app.log"), encoding="utf-8"),
    ],
    force=True,
)

app = FastAPI(title="YS-Agent API", version="1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def on_startup():
    from agent import config_manager, search_index
    from agent.tools.mcp_manager import connect_all_servers
    from agent.utils import DATA_DIR

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    search_index.init_db()
    if search_index.count_indexed() == 0:
        n = search_index.migrate_from_json()
        if n:
            import logging

            logging.getLogger(__name__).info("搜索索引迁移完成: %d 个会话", n)

    # Connect to enabled MCP servers in background
    cfg = config_manager.load()
    servers_cfg = cfg.get("mcp_servers", {})

    # Ensure built-in MCP servers are configured
    if "yonsuite" not in servers_cfg:
        py_path = sys.executable
        servers_cfg["yonsuite"] = {
            "transport": "stdio",
            "command": py_path,
            "args": ["-m", "mcp_server.ys_mcp_server"],
            "enabled": True,
            "timeout": 120,
        }
        cfg["mcp_servers"] = servers_cfg
        config_manager.save(cfg)

    if "mcp-server-chart" not in servers_cfg:
        servers_cfg["mcp-server-chart"] = {
            "transport": "stdio",
            "enabled": True,
            "timeout": 120,
            "command": "npx",
            "args": ["-y", "@antv/mcp-server-chart"],
            "env": {},
        }
        # Don't save here — _DEFAULT_CONFIG already has it, so
        # load() will deep-merge it into the next persisted config.

    if servers_cfg:
        import asyncio

        asyncio.ensure_future(connect_all_servers(servers_cfg))


@app.on_event("shutdown")
async def on_shutdown():
    from agent.tools.mcp_manager import disconnect_all_servers

    await disconnect_all_servers()


# Register routers
from backend.api.chat import router as chat_router
from backend.api.config_api import router as config_router
from backend.api.extensions_api import router as extensions_router
from backend.api.mcp_api import router as mcp_router
from backend.api.memory_api import router as memory_router
from backend.api.metrics_api import router as metrics_router
from backend.api.sessions import router as sessions_router
from backend.api.skills_api import router as skills_router
from backend.api.system_api import router as system_router
from backend.api.tools_api import router as tools_router

app.include_router(sessions_router)
app.include_router(config_router)
app.include_router(memory_router)
app.include_router(metrics_router)
app.include_router(skills_router)
app.include_router(tools_router)
app.include_router(chat_router)
app.include_router(mcp_router)
app.include_router(extensions_router)
app.include_router(system_router)
