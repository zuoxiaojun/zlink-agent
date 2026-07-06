# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for YS-Agent backend.

Usage:
    pyinstaller backend/ys-agent.spec --clean --noconfirm

Produces a single directory (or single file) under dist/ys-agent-backend/
that contains all Python dependencies + the static frontend dist.
"""

import sys
from pathlib import Path

PROJECT_ROOT = Path.cwd()
WEB_DIST = PROJECT_ROOT / "web" / "dist"

# ── Collect hidden imports that PyInstaller's hook scanner misses ──
hidden_imports = [
    "uvicorn.logging",
    "uvicorn.loops.auto",
    "uvicorn.protocols.http.auto",
    "uvicorn.protocols.websockets.auto",
    "uvicorn.middleware.wsgi",
    "uvicorn.middleware.proxy_headers",
    "backend.main",
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
    "backend.schemas.config",
    "agent.agent",
    "agent.utils",
    "agent.config_manager",
    "agent.config_model",
    "agent.context_compactor",
    "agent.fact_memory",
    "agent.memory_manager",
    "agent.search_index",
    "agent.session_manager",
    "agent.skill_manager",
    "agent.slash_commands",
    "agent.core.agent",
    "agent.core.llm_client",
    "agent.core.message_builder",
    "agent.core.tool_dispatcher",
    "agent.core.iteration_budget",
    "agent.core.llm_providers.base",
    "agent.core.llm_providers.openai_compat",
    "agent.core.llm_providers.anthropic",
    "agent.events",
    "agent.events.event_bus",
    "agent.events.types",
    "agent.events.extensions",
    "agent.extensions",
    "agent.tools.registry",
    "agent.tools.terminal_tool",
    "agent.tools.file_tools",
    "agent.tools.web_tools",
    "agent.tools.web_extract_tool",
    "agent.tools.browser_tool",
    "agent.tools.skills_tool",
    "agent.tools.todo_tool",
    "agent.tools.clarify_tool",
    "agent.tools.memory_tool",
    "agent.tools.session_search_tool",
    "agent.tools.mcp_manager",
    "agent.tools.security_hooks",
    "agent.yonsuite_client",
    "agent.plugin_system",
    "prometheus_client",
    "prometheus_client.openmetrics",
]

# ── Data files: static frontend ──
datas = []
if WEB_DIST.is_dir():
    for f in WEB_DIST.rglob("*"):
        if f.is_file():
            datas.append((str(f), str(f.relative_to(WEB_DIST.parent))))

a = Analysis(
    ["__main__.py"],
    pathex=[str(PROJECT_ROOT)],
    binaries=[],
    datas=datas,
    hiddenimports=hidden_imports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "tkinter",
        "turtle",
        "test",
        "unittest",
        "setuptools",
        "pdb",
        "py_compile",
        "compileall",
        "doctest",
        "pydoc",
        "http.server",
        "socketserver",
        "email",
    ],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="ys-agent-backend",
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
