"""ZLink Agent FastAPI backend — serves REST API + WebSocket for the React frontend."""

import logging
import os
import shutil
import sys
from pathlib import Path

# Ensure project root is on sys.path so agent/ imports work
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

# 数据目录: ZLINK_DATA_DIR 环境变量 > ~/.zlink-agent/data/

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from agent.config_model import MCPServerEntry
from agent.utils import DATA_DIR
from backend.config import CORS_ORIGINS

# 启动时打印数据目录,消除"我设置存哪了"的不确定性
print(f"[ZLink Agent] Data directory: {DATA_DIR}", file=sys.stderr)

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

    # ── 强制覆盖内置 MCP 服务器的 command/args ─────────────────────────
    # 避免 config.json 中残留的绝对路径（如 Electron .app 内部路径）
    # 导致开发环境启动失败。每次启动都用当前运行环境覆盖并持久化。
    py_path = sys.executable
    if getattr(sys, "frozen", False):
        ys_mcp_args = ["--mcp-server"]
    else:
        ys_mcp_args = ["-m", "mcp_server.ys_mcp_server"]

    servers_cfg.setdefault("yonsuite", MCPServerEntry(
        transport="stdio",
        command=py_path,
        args=ys_mcp_args,
        enabled=True,
        timeout=120,
        builtin=True,
    ))
    ys_entry = servers_cfg["yonsuite"]
    ys_entry.command = py_path
    ys_entry.args = ys_mcp_args
    ys_entry.builtin = True

    # nc MCP — 内置，用当前 Python
    servers_cfg.setdefault("mcp-nc", MCPServerEntry(
        transport="stdio",
        command=py_path,
        args=["-m", "mcp_server.nc_mcp_server"],
        enabled=False,
        timeout=120,
        builtin=True,
        env={},
    ))
    nc_entry = servers_cfg["mcp-nc"]
    nc_entry.command = py_path
    nc_entry.args = ["-m", "mcp_server.nc_mcp_server"]
    nc_entry.builtin = True

    # ── 从 erp_clients 读取配置，覆盖内置 MCP 服务器的 env ──────────
    # YonSuite
    ys_cfg_erp = cfg.erp_clients.get("yonsuite", {})
    ys_app_key = ys_cfg_erp.get("app_key") or cfg.ys_app_key or ""
    ys_app_secret = ys_cfg_erp.get("app_secret") or cfg.ys_app_secret or ""
    ys_tenant_id = ys_cfg_erp.get("tenant_id") or cfg.ys_tenant_id or ""
    ys_gateway_url = ys_cfg_erp.get("base_url") or cfg.ys_gateway_url or "https://c2.yonyoucloud.com/iuap-api-gateway"
    if isinstance(ys_cfg_erp, dict) and ys_app_key:
        ys_entry = servers_cfg["yonsuite"]
        ys_entry.env = {
            "YONSUITE_APP_KEY": ys_app_key,
            "YONSUITE_APP_SECRET": ys_app_secret,
            "YONSUITE_TENANT_ID": ys_tenant_id,
            "YONSUITE_GATEWAY_URL": ys_gateway_url,
        }
    # Always set os.environ (YonSuite client code reads these at import time)
    os.environ.setdefault("YONSUITE_APP_KEY", ys_app_key)
    os.environ.setdefault("YONSUITE_APP_SECRET", ys_app_secret)
    os.environ.setdefault("YONSUITE_TENANT_ID", ys_tenant_id)
    os.environ.setdefault("YONSUITE_GATEWAY_URL", ys_gateway_url)
    os.environ.setdefault("YONSUITE_CACHE_DIR", str(DATA_DIR / "yonsuite_cache"))

    # NC
    nc_cfg_erp = cfg.erp_clients.get("nc", {})
    if isinstance(nc_cfg_erp, dict):
        nc_entry.enabled = bool(nc_cfg_erp.get("enabled", False))
        nc_host = nc_cfg_erp.get("host", "") or ""
        if nc_host:
            nc_entry.env = {
                "ORACLE_HOST": nc_host,
                "ORACLE_PORT": str(nc_cfg_erp.get("port", "") or ""),
                "ORACLE_SERVICE": str(nc_cfg_erp.get("service", "") or ""),
                "ORACLE_USER": str(nc_cfg_erp.get("user", "") or ""),
                "ORACLE_PASSWORD": str(nc_cfg_erp.get("password", "") or ""),
                "NC_MCP_MAX_ROWS": str(nc_cfg_erp.get("max_rows", 200) or 200),
            }

    # Chart MCP server
    _chart_entry = _PROJECT_ROOT / "node_modules" / "@antv" / "mcp-server-chart" / "build" / "index.js"
    _node_path = shutil.which("node") if _chart_entry.exists() else None
    if _node_path:
        servers_cfg.setdefault("mcp-server-chart", MCPServerEntry(
            transport="stdio",
            command=_node_path,
            args=[str(_chart_entry)],
            enabled=True,
            timeout=120,
            builtin=True,
            env={},
        ))
        chart_entry = servers_cfg["mcp-server-chart"]
        chart_entry.command = _node_path
        chart_entry.args = [str(_chart_entry)]
        chart_entry.builtin = True
    elif _chart_entry.exists():
        _logger.warning("node 未安装, Chart MCP 服务器已跳过")
    elif not getattr(sys, "frozen", False):
        _logger.warning(
            "@antv/mcp-server-chart 未安装 (node_modules/@antv/mcp-server-chart 不存在), "
            "Chart MCP 服务器已跳过。运行 cd web && npm ci 安装。"
        )

    # 持久化内置服务器路径配置到 config.json
    cfg.mcp_servers = servers_cfg
    config_manager.save(cfg)

    if servers_cfg:
        import asyncio

        asyncio.ensure_future(connect_all_servers(servers_cfg))

    # Start cron job scheduler
    try:
        from agent.tools.cronjob_tools import start_scheduler

        start_scheduler()
    except Exception as e:
        _logger.warning("无法启动定时任务调度器: %s", e)

    yield

    # Shutdown
    from agent.tools.mcp_manager import disconnect_all_servers

    await disconnect_all_servers()
    try:
        from agent.tools.cronjob_tools import stop_scheduler

        stop_scheduler()
    except Exception:
        pass


from backend.api.system_api import _get_version  # noqa: E402

app = FastAPI(title="ZLink Agent API", version=_get_version(), lifespan=lifespan)

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
from backend.api.cronjob_api import router as cronjob_router
from backend.api.extensions_api import router as extensions_router
from backend.api.mcp_api import router as mcp_router
from backend.api.memory_api import router as memory_router
from backend.api.metrics_api import router as metrics_router
from backend.api.sessions import router as sessions_router
from backend.api.skills_api import router as skills_router
from backend.api.slash_commands_api import router as slash_commands_router
from backend.api.system_api import router as system_router
from backend.api.tools_api import router as tools_router

app.include_router(sessions_router)
app.include_router(config_router)
app.include_router(memory_router)
app.include_router(metrics_router)
app.include_router(skills_router)
app.include_router(tools_router)
app.include_router(slash_commands_router)
app.include_router(cronjob_router)
app.include_router(chat_router)
app.include_router(mcp_router)
app.include_router(extensions_router)
app.include_router(system_router)
from backend.api.erp_clients_api import router as erp_clients_router

app.include_router(erp_clients_router)

# ── Serve React frontend static files (for production / frozen builds) ──
_STATIC_DIR = Path(__file__).resolve().parent.parent / "web" / "dist"
if _STATIC_DIR.is_dir():
    app.mount("/", StaticFiles(directory=str(_STATIC_DIR), html=True), name="frontend")
