"""PyInstaller entry point — starts uvicorn with the FastAPI app.

This script is only used when building the PyInstaller binary.
It is NOT part of the normal source code import chain.
"""
import os
import sys
import time

_T0 = time.monotonic()


def _log_startup(stage: str) -> None:
    print(f"[startup] {stage}: {(time.monotonic() - _T0) * 1000:.0f}ms", file=sys.stderr)


# PyInstaller frozen mode: point SSL to certifi's CA bundle
# macOS 钥匙串证书在 PyInstaller 中不可用，必须使用 certifi 自带的证书
if getattr(sys, "frozen", False):
    import certifi

    os.environ.setdefault("SSL_CERT_FILE", certifi.where())
    os.environ.setdefault("REQUESTS_CA_BUNDLE", certifi.where())

from pathlib import Path  # noqa: E402

# Ensure project root is on sys.path so agent/ imports work
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

import uvicorn  # noqa: E402

_log_startup("import uvicorn")

from backend.main import app  # noqa: E402

_log_startup("import backend.main")

port = int(os.environ.get("ZLINK_AGENT_PORT", "8089"))
# 桌面端只监听本机回环：0.0.0.0 会把无鉴权的 agent API（terminal/文件工具）
# 暴露给整个局域网。服务器部署场景可通过 ZLINK_AGENT_HOST 显式放开。
host = os.environ.get("ZLINK_AGENT_HOST", "127.0.0.1")

_log_startup("uvicorn.run begin")

uvicorn.run(
    app,
    host=host,
    port=port,
    log_level="warning",
    access_log=False,
)
