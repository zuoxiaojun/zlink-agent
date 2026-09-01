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
    import time

    _t = time.monotonic()

    def _lap(stage: str) -> None:
        nonlocal _t
        now = time.monotonic()
        _logger.info("[startup] lifespan %s: %.0fms", stage, (now - _t) * 1000)
        _t = now

    # Startup
    from agent import config_manager, search_index
    from agent.tools.mcp_manager import connect_all_servers

    DATA_DIR.mkdir(parents=True, exist_ok=True)

    # 会话布局：扁平 <sid>.json → <sid>/session.json + artifacts/（幂等，失败不阻塞启动）
    from agent import session_manager

    n_moved = session_manager.migrate_session_layout()
    if n_moved:
        _logger.info("会话布局迁移完成: %d 个会话 → 目录布局", n_moved)
    _lap("session_layout")

    search_index.init_db()
    if search_index.count_indexed() == 0:
        n = search_index.migrate_from_json()
        if n:
            _logger.info("搜索索引迁移完成: %d 个会话", n)
    _lap("search_index")

    cfg = config_manager.load()
    servers_cfg = cfg.mcp_servers
    _lap("config_load")

    # ── YonSuite: 注入环境变量（内置工具 agent/tools/erp_ys_tools.py 读取） ──
    ys_cfg_erp = cfg.erp_clients.get("yonsuite", {})
    ys_app_key = ys_cfg_erp.get("app_key") or cfg.ys_app_key or ""
    ys_app_secret = ys_cfg_erp.get("app_secret") or cfg.ys_app_secret or ""
    ys_tenant_id = ys_cfg_erp.get("tenant_id") or cfg.ys_tenant_id or ""
    ys_gateway_url = ys_cfg_erp.get("base_url") or cfg.ys_gateway_url or "https://c2.yonyoucloud.com/iuap-api-gateway"
    os.environ.setdefault("YONSUITE_APP_KEY", ys_app_key)
    os.environ.setdefault("YONSUITE_APP_SECRET", ys_app_secret)
    os.environ.setdefault("YONSUITE_TENANT_ID", ys_tenant_id)
    os.environ.setdefault("YONSUITE_GATEWAY_URL", ys_gateway_url)
    os.environ.setdefault("YONSUITE_CACHE_DIR", str(DATA_DIR / "yonsuite_cache"))

    # ── NC: 注入环境变量（内置工具 agent/tools/erp_nc_tools.py 读取） ──
    nc_cfg_erp = cfg.erp_clients.get("nc", {})
    if isinstance(nc_cfg_erp, dict):
        nc_host = nc_cfg_erp.get("host", "") or ""
        if nc_host:
            os.environ.setdefault("ORACLE_HOST", nc_host)
            os.environ.setdefault("ORACLE_PORT", str(nc_cfg_erp.get("port", "") or ""))
            os.environ.setdefault("ORACLE_SERVICE", str(nc_cfg_erp.get("service", "") or ""))
            os.environ.setdefault("ORACLE_USER", str(nc_cfg_erp.get("user", "") or ""))
            os.environ.setdefault("ORACLE_PASSWORD", str(nc_cfg_erp.get("password", "") or ""))
            os.environ.setdefault("NC_MCP_MAX_ROWS", str(nc_cfg_erp.get("max_rows", 200) or 200))

    # ── U8: 注入环境变量（内置工具 agent/tools/erp_u8_tools.py 读取） ──
    u8_cfg_erp = cfg.erp_clients.get("u8", {})
    if isinstance(u8_cfg_erp, dict):
        u8_host = u8_cfg_erp.get("host", "") or ""
        if u8_host:
            os.environ.setdefault("U8_HOST", u8_host)
            os.environ.setdefault("U8_PORT", str(u8_cfg_erp.get("port", "") or ""))
            os.environ.setdefault("U8_DATABASE", str(u8_cfg_erp.get("database", "") or ""))
            os.environ.setdefault("U8_USER", str(u8_cfg_erp.get("user", "") or ""))
            os.environ.setdefault("U8_PASSWORD", str(u8_cfg_erp.get("password", "") or ""))
            os.environ.setdefault("U8_MAX_ROWS", str(u8_cfg_erp.get("max_rows", 500) or 500))
    # ── U9C: 注入环境变量（内置工具 agent/tools/erp_u9c_tools.py 读取） ──
    u9c_cfg_erp = cfg.erp_clients.get("u9c", {})
    if isinstance(u9c_cfg_erp, dict):
        u9c_host = u9c_cfg_erp.get("host", "") or ""
        if u9c_host:
            os.environ.setdefault("U9C_HOST", u9c_host)
            os.environ.setdefault("U9C_PORT", str(u9c_cfg_erp.get("port", "") or ""))
            os.environ.setdefault("U9C_DATABASE", str(u9c_cfg_erp.get("database", "") or ""))
            os.environ.setdefault("U9C_USER", str(u9c_cfg_erp.get("user", "") or ""))
            os.environ.setdefault("U9C_PASSWORD", str(u9c_cfg_erp.get("password", "") or ""))
            os.environ.setdefault("U9C_MAX_ROWS", str(u9c_cfg_erp.get("max_rows", 500) or 500))
    _lap("erp_env")

    # ── Chart MCP server（预置，打包在 Resources/mcp-chart/） ──
    # 开发模式: node_modules/@antv/mcp-server-chart/build/index.js
    # 生产模式: Resources/mcp-chart/build/index.js
    _chart_paths = [
        _PROJECT_ROOT / "node_modules" / "@antv" / "mcp-server-chart" / "build" / "index.js",
    ]
    # 检查是否是 Electron 打包环境（Resources/mcp-chart/）
    # PyInstaller frozen 模式:
    #   onefile: sys.executable = Resources/zlink-backend → parent = Resources/
    #   onedir:  sys.executable = Resources/zlink-backend/zlink-backend → parent.parent = Resources/
    if getattr(sys, "frozen", False):
        _exe_dir = Path(sys.executable).resolve().parent
        if (_exe_dir / "mcp-chart").exists():
            _resources_dir = _exe_dir
        else:
            _resources_dir = _exe_dir.parent
    else:
        _resources_dir = Path(__file__).resolve().parent.parent.parent / "Resources"
    _resources_chart = _resources_dir / "mcp-chart" / "build" / "index.js"
    if _resources_chart.exists():
        _chart_paths.insert(0, _resources_chart)

    _chart_entry = None
    for p in _chart_paths:
        if p.exists():
            _chart_entry = p
            break

    if _chart_entry:
        # Electron 自带 Node.js 优先（ELECTRON_NODE_PATH 由 electron/main.js 注入；
        # 用 Electron 二进制跑 JS 必须带 ELECTRON_RUN_AS_NODE=1，否则会再开一个应用实例）
        _electron_node = os.environ.get("ELECTRON_NODE_PATH", "")
        _chart_env: dict = {}
        if _electron_node and Path(_electron_node).exists():
            _node_path = _electron_node
            _chart_env["ELECTRON_RUN_AS_NODE"] = "1"
        else:
            _node_path = shutil.which("node")
        if _node_path:
            # 内置 chart 条目由应用托管：每次启动都刷新 command/args/env。
            # 不能用 setdefault —— 旧条目残留后（app 被移动、从 DMG 直接运行过、
            # 旧版本升级）路径失效，chart 会永久坏掉。仅保留用户的 enabled 选择。
            _prev = servers_cfg.get("mcp-server-chart")
            servers_cfg["mcp-server-chart"] = MCPServerEntry(
                transport="stdio",
                command=_node_path,
                args=[str(_chart_entry)],
                enabled=_prev.enabled if _prev is not None else True,
                timeout=120,
                builtin=True,
                env=_chart_env,
            )
        else:
            _logger.warning("Chart MCP 服务器已跳过（未找到 node）")
    else:
        _logger.info("Chart MCP 未安装，跳过（用户可自行 npx 启动）")

    # 从 servers_cfg 中移除已内置化的 ERP MCP 条目（保留用户自己添加的第三方 MCP）
    for _erp_key in ("yonsuite", "mcp-nc"):
        servers_cfg.pop(_erp_key, None)

    # 持久化配置（不含已移除的 ERP 条目）
    cfg.mcp_servers = servers_cfg
    config_manager.save(cfg)
    _lap("chart_mcp_config")

    if servers_cfg:
        import asyncio

        asyncio.ensure_future(connect_all_servers(servers_cfg))
    _lap("mcp_connect_scheduled")

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

# ── Serve React frontend static files (for production builds) ──
_STATIC_DIR = Path(__file__).resolve().parent.parent / "web" / "dist"
if _STATIC_DIR.is_dir():
    app.mount("/", StaticFiles(directory=str(_STATIC_DIR), html=True), name="frontend")
