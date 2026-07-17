#!/bin/bash
# build-pyinstaller.sh — PyInstaller 打包 ZLink Agent Python 后端
#
# 用法:
#   bash scripts/build-pyinstaller.sh            # 打包为单文件
#   bash scripts/build-pyinstaller.sh --onedir   # 打包为单目录（调试用）
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$(dirname "$0")/.."

MODE="${1:---onefile}"
PLATFORM_TAG=""
case "$(uname -s)" in
  Darwin) PLATFORM_TAG="macos-$(uname -m)" ;;
  Linux)  PLATFORM_TAG="linux-$(uname -m)" ;;
  MINGW*|MSYS*) PLATFORM_TAG="win" ;;
esac

echo "╔══════════════════════════════════════════════╗"
echo "║     PyInstaller 打包 ZLink 后端              ║"
echo "║     模式: $MODE"
echo "║     平台: $PLATFORM_TAG"
echo "╚══════════════════════════════════════════════╝"

# 确保 venv 里有 pyinstaller
if ! python3 -c "import PyInstaller" 2>/dev/null; then
    echo "安装 PyInstaller..."
    pip install pyinstaller
fi

echo ""
echo "▶ 打包中..."

# --add-data separator: macOS/Linux use ":", Windows uses ";"
if [[ "$(uname -s)" =~ MINGW*|MSYS* ]]; then
    ADD_DATA_SEP=";"
else
    ADD_DATA_SEP=":"
fi

python3 -m PyInstaller \
    --clean \
    --noconfirm \
    $MODE \
    --name zlink-backend \
    --add-data "agent/skills${ADD_DATA_SEP}agent/skills" \
    --hidden-import uvicorn \
    --hidden-import uvicorn.logging \
    --hidden-import uvicorn.loops \
    --hidden-import uvicorn.loops.auto \
    --hidden-import uvicorn.protocols \
    --hidden-import uvicorn.protocols.http \
    --hidden-import uvicorn.protocols.http.auto \
    --hidden-import uvicorn.middleware \
    --hidden-import uvicorn.middleware.asgi2 \
    --hidden-import uvicorn.middleware.proxy_headers \
    --hidden-import uvicorn.middleware.wsgi \
    --hidden-import oracledb \
    --hidden-import yaml \
    --hidden-import httpx \
    --hidden-import dotenv \
    --hidden-import pydantic \
    --hidden-import websockets \
    --hidden-import agent.tools.browser_tool \
    --hidden-import agent.tools.clarify_tool \
    --hidden-import agent.tools.code_execution_tool \
    --hidden-import agent.tools.cronjob_tools \
    --hidden-import agent.tools.delegate_tool \
    --hidden-import agent.tools.erp_nc_tools \
    --hidden-import agent.tools.erp_ys_tools \
    --hidden-import agent.tools.file_mutation_queue \
    --hidden-import agent.tools.file_tools \
    --hidden-import agent.tools.mcp_management_tool \
    --hidden-import agent.tools.mcp_manager \
    --hidden-import agent.tools.memory_tool \
    --hidden-import agent.tools.process_tool \
    --hidden-import agent.tools.project_tools \
    --hidden-import agent.tools.security_hooks \
    --hidden-import agent.tools.session_search_tool \
    --hidden-import agent.tools.skills_tool \
    --hidden-import agent.tools.terminal_tool \
    --hidden-import agent.tools.todo_tool \
    --hidden-import agent.tools.vision_tool \
    --hidden-import agent.tools.web_extract_tool \
    --hidden-import agent.tools.web_tools \
    --hidden-import agent.extensions.audit_log \
    --hidden-import agent.extensions.log_everything \
    --hidden-import agent.extensions.monitoring \
    --hidden-import agent.extensions.security_event \
    --hidden-import agent.core.agent \
    --hidden-import agent.core.llm_client \
    --hidden-import agent.core.message_builder \
    --hidden-import agent.core.metrics \
    --hidden-import agent.core.iteration_budget \
    --hidden-import agent.core.tool_dispatcher \
    backend/main.py

echo ""
echo "✅ PyInstaller 打包完成"
ls -lh dist/zlink-backend*
