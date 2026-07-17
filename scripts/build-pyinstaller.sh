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

python3 -m PyInstaller \
    --clean \
    --noconfirm \
    $MODE \
    --name zlink-backend \
    --add-data "agent/skills:skills" \
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
    backend/main.py

echo ""
echo "✅ PyInstaller 打包完成"
echo "   产物: dist/zlink-backend"
ls -lh dist/zlink-backend*
