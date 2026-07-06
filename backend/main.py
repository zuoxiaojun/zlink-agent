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

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from agent.config_model import MCPServerEntry
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

_logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(application: FastAPI):
    # Startup
    from agent import config_manager, search_index
    from agent.tools.mcp_manager import connect_all_servers

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    search_index.init_db()
    if search_index.count_indexed() == 0:
        n = search_index.migrate_from_json()
        if n:
            _logger.info("搜索索引迁移完成: %d 个会话", n)

    cfg = config_manager.load()
    servers_cfg = cfg.mcp_servers

    if "yonsuite" not in servers_cfg:
        py_path = sys.executable
        servers_cfg["yonsuite"] = MCPServerEntry(
            transport="stdio",
            command=py_path,
            args=["-m", "mcp_server.ys_mcp_server"],
            enabled=True,
            timeout=120,
            builtin=True,
        )
        cfg.mcp_servers = servers_cfg
        config_manager.save(cfg)

    if "mcp-server-chart" not in servers_cfg:
        servers_cfg["mcp-server-chart"] = MCPServerEntry(
            transport="stdio",
            enabled=True,
            timeout=120,
            command="npx",
            args=["-y", "@antv/mcp-server-chart"],
            env={},
            builtin=True,
        )

    if servers_cfg:
        import asyncio

        asyncio.ensure_future(connect_all_servers(servers_cfg))

    yield

    # Shutdown
    from agent.tools.mcp_manager import disconnect_all_servers

    await disconnect_all_servers()


app = FastAPI(title="YS-Agent API", version="1.3.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


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

# ── Serve React frontend static files (for production / frozen builds) ──
_STATIC_DIR = Path(__file__).resolve().parent.parent / "web" / "dist"
if _STATIC_DIR.is_dir():
    app.mount("/", StaticFiles(directory=str(_STATIC_DIR), html=True), name="frontend")
