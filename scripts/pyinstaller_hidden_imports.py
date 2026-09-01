"""PyInstaller hidden imports 集中清单。

维护原则
--------
1. 所有动态导入（函数内 import / try-except ImportError / importlib）必须登记在此。
2. 新增第三方依赖或修改导入方式时，同步更新本文件。
3. 打包脚本 `build-pyinstaller.sh` 直接引用本列表，避免两处维护。

运行 `python scripts/check_dynamic_imports.py` 可自动扫描代码中的动态导入并给出补录建议。
"""

# ── Web 框架 / ASGI ─────────────────────────────────────────────
WEB_FRAMEWORK = [
    "fastapi",
    "starlette",
    "uvicorn",
    "uvicorn.logging",
    "uvicorn.loops",
    "uvicorn.loops.auto",
    "uvicorn.protocols",
    "uvicorn.protocols.http",
    "uvicorn.protocols.http.auto",
    "uvicorn.middleware",
    "uvicorn.middleware.asgi2",
    "uvicorn.middleware.proxy_headers",
    "uvicorn.middleware.wsgi",
    "multipart",  # python-multipart, FastAPI 文件上传依赖
]

# ── 数据校验 / 配置 ─────────────────────────────────────────────
DATA_VALIDATION = [
    "pydantic",
    "pydantic_core",  # Rust 扩展，PyInstaller 容易漏
    "yaml",
    "dotenv",
    "certifi",  # PyInstaller frozen 模式 SSL 证书
]

# ── LLM / AI ────────────────────────────────────────────────────
LLM_PROVIDERS = [
    "openai",
    "anthropic",
    "tiktoken",
    "agent.core.llm_providers.anthropic",  # factory.py 内部延迟导入
]

# ── 数据库 / ERP ────────────────────────────────────────────────
DATABASE = [
    "oracledb",
    "sqlparse",
    "pymssql",
    # cryptography 完整子模块链 —— oracledb thin mode 连接时动态加载
    "cryptography",
    "cryptography.hazmat",
    "cryptography.hazmat.primitives",
    "cryptography.hazmat.primitives.kdf",
    "cryptography.hazmat.primitives.kdf.pbkdf2",
    "cryptography.hazmat.primitives.kdf.scrypt",
    "cryptography.hazmat.primitives.hashes",
    "cryptography.hazmat.primitives.ciphers",
    "cryptography.hazmat.primitives.ciphers.aead",
    "cryptography.hazmat.primitives.ciphers.algorithms",
    "cryptography.hazmat.primitives.ciphers.modes",
    "cryptography.hazmat.primitives.serialization",
    "cryptography.hazmat.primitives.asymmetric",
    "cryptography.hazmat.primitives.asymmetric.padding",
    "cryptography.hazmat.primitives.asymmetric.rsa",
    "cryptography.hazmat.primitives.asymmetric.utils",
    "cryptography.hazmat.backends",
    "cryptography.hazmat.backends.openssl",
]

# ── 监控 / 指标 ─────────────────────────────────────────────────
MONITORING = [
    "prometheus_client",
]

# ── 网络 / HTTP ─────────────────────────────────────────────────
NETWORK = [
    "httpx",
    "requests",
    "websockets",
]

# ── Agent 工具模块 ──────────────────────────────────────────────
AGENT_TOOLS = [
    "agent.tools.binary_extensions",
    "agent.tools.clarify_tool",
    "agent.tools.code_execution_tool",
    "agent.tools.cronjob_tools",
    "agent.tools.erp_nc_tools",
    "agent.tools.erp_u9c_tools",
    "agent.tools.erp_ys_tools",
    "agent.tools.file_mutation_queue",
    "agent.tools.file_tools",
    "agent.tools.mcp_management_tool",
    "agent.tools.mcp_manager",
    "agent.tools.memory_tool",
    "agent.tools.process_tool",
    "agent.tools.project_tools",
    "agent.tools.read_extract",
    "agent.tools.security_hooks",
    "agent.tools.session_search_tool",
    "agent.tools.skills_tool",
    "agent.tools.terminal_tool",
    "agent.tools.todo_tool",
    "agent.tools.tool_search",
    "agent.tools.tool_search_tool",
    "agent.tools.vision_tool",
    "agent.tools.web_extract_tool",
    "agent.tools.web_tools",
]

# ── Agent 扩展模块 ──────────────────────────────────────────────
AGENT_EXTENSIONS = [
    "agent.extensions.audit_log",
    "agent.extensions.log_everything",
    "agent.extensions.monitoring",
    "agent.extensions.security_event",
]

# ── Agent 核心模块 ──────────────────────────────────────────────
AGENT_CORE = [
    "agent.core.agent",
    "agent.core.llm_client",
    "agent.core.message_builder",
    "agent.core.iteration_budget",
    "agent.core.tool_dispatcher",
]

# ── 标准库（动态导入，PyInstaller 可能漏掉）──
STDLIB = [
    "posixpath",  # read_extract.py 中 `import posixpath`
]

# ── 汇总 ────────────────────────────────────────────────────────
HIDDEN_IMPORTS: list[str] = [
    *WEB_FRAMEWORK,
    *DATA_VALIDATION,
    *LLM_PROVIDERS,
    *DATABASE,
    *MONITORING,
    *NETWORK,
    *STDLIB,
    *AGENT_TOOLS,
    *AGENT_EXTENSIONS,
    *AGENT_CORE,
]


def get_hidden_imports() -> list[str]:
    """返回去重后的 hidden imports 列表。"""
    return sorted(set(HIDDEN_IMPORTS))


if __name__ == "__main__":
    for imp in get_hidden_imports():
        print(imp)
