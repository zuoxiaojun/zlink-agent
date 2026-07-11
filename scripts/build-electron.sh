#!/bin/bash
# ===========================================================================
# build-electron.sh — ZLink Agent Electron 打包脚本
#
# 用法：
#   bash scripts/build-electron.sh            默认打包当前平台
#   bash scripts/build-electron.sh --mac      打包 macOS .dmg
#   bash scripts/build-electron.sh --win      打包 Windows .exe
#   bash scripts/build-electron.sh --linux    打包 Linux .AppImage
#   bash scripts/build-electron.sh --all      打包全部平台
#   bash scripts/build-electron.sh --no-frontend  跳过前端构建
#
# 前置条件：
#   - Node.js >= 18 + npm
#   - Windows 打包需要安装 wine（brew install wine）
# ===========================================================================

set -euo pipefail

cd "$(dirname "$0")/.."

PLATFORM="${1:-}"
SKIP_FRONTEND=false

case "$PLATFORM" in
  --mac)      PLATFORM="--mac" ;;
  --win)      PLATFORM="--win" ;;
  --linux)    PLATFORM="--linux" ;;
  --all)      PLATFORM="--mac --win --linux" ;;
  --no-frontend) PLATFORM="--mac"; SKIP_FRONTEND=true ;;
  "")         PLATFORM="--mac" ;;
  *)          echo "用法: $0 [--mac|--win|--linux|--all|--no-frontend]"; exit 1 ;;
esac

echo "╔══════════════════════════════════════════════╗"
echo "║     ZLink Agent Electron 打包                ║"
echo "║     平台: $PLATFORM"
echo "╚══════════════════════════════════════════════╝"

if [ "$SKIP_FRONTEND" = false ]; then
  echo ""
  echo "[1/2] 构建前端..."
  cd web && npm ci && npm run build && cd ..
  echo "✅ 前端构建完成"
fi

echo ""
echo "[2/2] 打包 Electron..."
npx electron-builder $PLATFORM --config electron-builder.yml
echo "✅ 打包完成: dist-electron/"
