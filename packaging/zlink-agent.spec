"""PyInstaller spec for ZLink Agent desktop app.

Build:  pyinstaller packaging/zlink-agent.spec --clean --noconfirm
Output: dist/ZLink-Agent/  (onedir: one directory, double-clickable binary inside)

Prerequisites:
  - web/dist/  (frontend already built — run `npm run build` in web/ first)
"""

from pathlib import Path

# ── Project root (where pyproject.toml lives) ────────────────────────────
# SPEC is a built-in PyInstaller variable pointing to the spec file path.
PROJECT_ROOT = Path(SPEC).resolve().parent.parent

# ── Block cipher ─────────────────────────────────────────────────────────
# Ensures deterministic builds.  Can keep as-is since this is an open-source
# project; for distribution replace with a project-specific value.
block_cipher = None

# ── Collected modules ────────────────────────────────────────────────────
a = Analysis(
    # Entry point — handles both main server and --mcp-server
    [str(PROJECT_ROOT / "packaging" / "launcher.py")],

    # Paths searched for imports
    pathex=[str(PROJECT_ROOT)],

    # Binaries to bundle (none for pure-Python, but httpx/h2 may bring .so)
    binaries=[],

    # Data files: static assets bundled alongside the binary
    datas=[],

    # Hidden imports — modules PyInstaller can't auto-detect
    hiddenimports=[
        # ── Backend API routers (imported inline in main.py) ──
        "backend.api.chat",
        "backend.api.config_api",
        "backend.api.extensions_api",
        "backend.api.mcp_api",
        "backend.api.memory_api",
        "backend.api.metrics_api",
        "backend.api.sessions",
        "backend.api.skills_api",
        "backend.api.system_api",
        "backend.api.tools_api",

        # ── Agent tool modules (discovered dynamically via discover_tools) ──
        "agent.tools.terminal_tool",
        "agent.tools.file_tools",
        "agent.tools.web_tools",
        "agent.tools.web_extract_tool",
        "agent.tools.skills_tool",
        "agent.tools.todo_tool",
        "agent.tools.clarify_tool",
        "agent.tools.memory_tool",
        "agent.tools.session_search_tool",
        "agent.tools.file_mutation_queue",
        "agent.tools.mcp_manager",
        "agent.tools.security_hooks",
        "agent.tools.delegate_tool",
        "agent.tools.browser_tool",

        # ── MCP server (NC) ──
        "mcp_server.nc_mcp_server",
        "mcp_server.nc_mcp_server.server",
        "mcp_server.nc_mcp_server.config",
        "mcp_server.nc_mcp_server.data_dictionary",
        "mcp_server.nc_mcp_server.queries.sales_order",
        "mcp_server.nc_mcp_server.queries.purchase_order",
        "mcp_server.nc_mcp_server.queries.customer",
        "mcp_server.nc_mcp_server.queries.supplier",
        "mcp_server.nc_mcp_server.queries.material",
        "mcp_server.nc_mcp_server.queries.organization",
        "mcp_server.nc_mcp_server.queries.stock",

        # ── MCP server (YonSuite) ──
        "mcp_server.ys_mcp_server",
        "mcp_server.ys_mcp_server.server",
        "mcp_server.ys_mcp_server.tools",
        "mcp_server.ys_mcp_server.paginate",
        "mcp_server.ys_mcp_server.utils",
        "mcp_server.ys_mcp_server.constants",
        "mcp_server.ys_mcp_server.handlers",
        "mcp_server.ys_mcp_server.handlers.ys_api",
        "mcp_server.ys_mcp_server.handlers.sale_orders",
        "mcp_server.ys_mcp_server.handlers.purchase_orders",
        "mcp_server.ys_mcp_server.handlers.production_orders",
        "mcp_server.ys_mcp_server.handlers.stock",
        "mcp_server.ys_mcp_server.handlers.products",
        "mcp_server.ys_mcp_server.handlers.customers",
        "mcp_server.ys_mcp_server.handlers.vendors",
        "mcp_server.ys_mcp_server.handlers.opportunities",
        "mcp_server.ys_mcp_server.handlers.user_todos",
        "mcp_server.ys_mcp_server.handlers.vouchers",

        # ── Agent core modules ──
        "agent.core.agent",
        "agent.core.llm_client",
        "agent.core.message_builder",
        "agent.core.tool_dispatcher",
        "agent.core.iteration_budget",
        "agent.core.llm_providers.base",
        "agent.core.llm_providers.openai_compat",
        "agent.core.llm_providers.anthropic",

        # ── Other agent modules ──
        "agent.events",
        "agent.extensions",
        "agent.skill_manager",
        "agent.session_manager",
        "agent.search_index",
        "agent.memory_manager",
        "agent.fact_memory",
        "agent.context_compactor",
        "agent.slash_commands",
        "agent.config_manager",
        "agent.erp_clients.yonsuite",

        # ── Uvicorn internals (PyInstaller often misses protocol loops) ──
        "uvicorn.logging",
        "uvicorn.protocols.http.auto",
        "uvicorn.protocols.http.h11_impl",
        "uvicorn.protocols.http.httptools_impl",
        "uvicorn.protocols.websockets.auto",
        "uvicorn.protocols.websockets.websockets_impl",
        "uvicorn.loops.auto",
        "uvicorn.loops.asyncio",
        "uvicorn.middleware.proxy_headers",

        # ── FastAPI extras ──
        "python_multipart",
        "multipart",
        "pydantic",
        "pydantic._internal",
        "pydantic.deprecated",
        "pydantic.fields",
        "pydantic.networks",
        "tiktoken_ext.openai_public",

        # ── cryptography backends ──
        "cryptography.hazmat.backends.openssl",
        "cryptography.hazmat.primitives.ciphers.algorithms",
        "cryptography.hazmat.primitives.kdf.pbkdf2",
    ],

    # Exclude what we definitely don't need
    excludes=[
        "tkinter",
        "PyQt5",
        "PyQt6",
        "PySide2",
        "PySide6",
        "notebook",
        "ipykernel",
        "jupyter",
        "matplotlib",
        "scipy",
        "pandas",
        "numpy",
        "PIL",
        "cv2",
        "tensorflow",
        "torch",
        # playwright 是 browser_tool 的可选依赖, 不打包进 exe
    ],

    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
)

# ── Frontend static files (from web/dist/) ───────────────────────────────
# Places web/dist/ into _internal/web/dist/ so backend/main.py's
#   _STATIC_DIR = Path(__file__).parent.parent / "web" / "dist"
# resolves correctly inside the bundle.
frontend_dist = PROJECT_ROOT / "web" / "dist"
if frontend_dist.is_dir():
    a.datas += Tree(frontend_dist, prefix="web/dist")

# ── VERSION 文件 (让 _get_version() 在 frozen 模式下能读到) ──────────
version_file = PROJECT_ROOT / "VERSION"
if version_file.is_file():
    # PyInstaller 6.x: datas 是 list of (dest_name, source_path, typecode)
    a.datas += [("VERSION", str(version_file), "DATA")]

# ── Builtin skills (agent/skills/ directory) ────────────────────────────
# Skills are loaded dynamically at runtime, so PyInstaller can't
# follow them as imports.  Bundle them as data files.
skills_src = PROJECT_ROOT / "agent" / "skills"
if skills_src.is_dir():
    a.datas += Tree(skills_src, prefix="agent/skills")

# ── PyZ (compressed Python modules bundle) ──────────────────────────────
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

# ── EXE (bootloader only; COLLECT handles binaries/datas) ──────────────
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="zlink-agent",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

# ── COLLECT (onedir output: dist/ZLink-Agent/) ──────────────────────────────
# Creates dist/ZLink-Agent/ with:
#   zlink-agent       ← 启动入口
#   _internal/        ← 所有 Python 模块 + 原生库 + 数据文件
#
# 这样 MCP 子进程（sys.executable --mcp-server）在同一个目录下就能
# 找到 _internal/，不需要重新解压。
coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="ZLink-Agent",
)

# ── macOS .app bundle wrapper (optional) ─────────────────────────────────
# Uncomment the BUNDLE block and provide an app.icns icon file to
# generate a real double-clickable .app on macOS.
# APP = BUNDLE(
#     coll,
#     name="ZLink-Agent.app",
#     icon=str(PROJECT_ROOT / "packaging" / "app.icns"),
#     bundle_identifier="cn.zlink.agent",
#     info_plist={
#         "CFBundleShortVersionString": "1.3.1",
#         "CFBundleDisplayName": "ZLink Agent",
#         "CFBundleName": "ZLink Agent",
#         "NSHighResolutionCapable": True,
#     },
# )
