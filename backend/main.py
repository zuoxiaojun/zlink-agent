"""YS-Agent FastAPI backend — serves REST API + WebSocket for the React frontend."""

import logging
import sys
from pathlib import Path

# Ensure project root is on sys.path so agent/ imports work
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

# v1.4.0: 数据目录统一为 ~/.ys-agent/data/,源码与 .app 行为一致。
# 唯一可覆盖方式: export YS_DATA_DIR=/path/to/data (由 agent/utils.py 处理)
# 旧位置的检测与迁移也在 agent/utils.py 完成 (自动迁移仅在新位置完全为空时执行)

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from agent.config_model import MCPServerEntry
from agent.utils import DATA_DIR, detect_legacy_data_dirs
from backend.config import CORS_ORIGINS

# v1.4.0: 启动时清晰打印数据目录,消除"我设置存哪了"的不确定性
print(f"[YS-Agent] Data directory: {DATA_DIR}", file=sys.stderr)
_legacy = detect_legacy_data_dirs()
if _legacy:
    print(
        f"[YS-Agent] ⚠ 检测到旧位置有数据: {[str(p) for p in _legacy]}\n"
        f"           数据目录已统一为 {DATA_DIR},如需合并运行: ys-agent migrate-data-path",
        file=sys.stderr,
    )

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
        if getattr(sys, "frozen", False):
            # PyInstaller: use the same binary with --mcp-server flag
            mcp_args = ["--mcp-server"]
        else:
            mcp_args = ["-m", "mcp_server.ys_mcp_server"]
        servers_cfg["yonsuite"] = MCPServerEntry(
            transport="stdio",
            command=py_path,
            args=mcp_args,
            enabled=True,
            timeout=120,
            builtin=True,
        )
        cfg.mcp_servers = servers_cfg
        config_manager.save(cfg)

    # Inject YonSuite credentials into yonsuite MCP server's env so its subprocess
    # can read YONSUITE_APP_KEY / YONSUITE_APP_SECRET / YONSUITE_TENANT_ID.
    # Otherwise _connect_stdio's safe_env whitelist drops them.
    yonsuite_cfg = servers_cfg.get("yonsuite")
    if yonsuite_cfg:
        yonsuite_cfg.env = {
            "YONSUITE_APP_KEY": cfg.ys_app_key or "",
            "YONSUITE_APP_SECRET": cfg.ys_app_secret or "",
            "YONSUITE_TENANT_ID": cfg.ys_tenant_id or "",
            "YONSUITE_GATEWAY_URL": cfg.ys_gateway_url or "https://c2.yonyoucloud.com/iuap-api-gateway",
        }
        cfg.mcp_servers = servers_cfg
        config_manager.save(cfg)

    # Chart MCP server (npx-based) — skip if npx unavailable in frozen mode
    _chart_enabled = True
    if getattr(sys, "frozen", False):
        import shutil

        if not shutil.which("npx"):
            # .app 用户预期没装 Node.js, 静默跳过 chart MCP
            _logger.info("未检测到 npx, MCP chart 服务器已跳过 (用户可通过 MCP 管理页自装 @antv/mcp-server-chart)")
            _chart_enabled = False
    else:
        # 开发模式: npx 缺失是异常, 提醒
        import shutil

        if not shutil.which("npx"):
            _logger.warning("npx 未安装, MCP chart 服务器已跳过 (运行 npm i -g npx 修复)")

    if _chart_enabled:
        if "mcp-server-chart" not in servers_cfg:
            servers_cfg["mcp-server-chart"] = MCPServerEntry(
                transport="stdio",
                enabled=True,
                timeout=120,
                command="npx",
                # --prefer-offline: 已缓存的包不走网络，加速启动
                args=["--prefer-offline", "-y", "@antv/mcp-server-chart"],
                env={},
                builtin=True,
            )
        else:
            # Ensure existing entry has builtin flag (migration from older configs)
            servers_cfg["mcp-server-chart"].builtin = True
            # Also patch args to add --prefer-offline if missing (migration)
            if "mcp-server-chart" in servers_cfg:
                chart = servers_cfg["mcp-server-chart"]
                if chart.args and "-y" in chart.args and "--prefer-offline" not in chart.args:
                    chart.args = ["--prefer-offline"] + chart.args

    # Guard: ensure both builtin servers have builtin=True even if loaded from old config
    builtin_names = {"yonsuite", "mcp-server-chart"}
    _builtin_fixed = False
    for name in builtin_names:
        entry = servers_cfg.get(name)
        if entry and not entry.builtin:
            entry.builtin = True
            _logger.info("已修复内置 MCP 服务器「%s」的 builtin 标记", name)
            _builtin_fixed = True
    if _builtin_fixed:
        cfg.mcp_servers = servers_cfg
        config_manager.save(cfg)

    if servers_cfg:
        import asyncio

        asyncio.ensure_future(connect_all_servers(servers_cfg))

    yield

    # Shutdown
    from agent.tools.mcp_manager import disconnect_all_servers

    await disconnect_all_servers()


from backend.api.system_api import _get_version  # noqa: E402

app = FastAPI(title="YS-Agent API", version=_get_version(), lifespan=lifespan)

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
