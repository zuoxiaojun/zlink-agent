#!/bin/bash
# ===========================================================================
# build-electron.sh — ZLink Agent Electron 全自包含打包脚本
#
# 用法：
#   bash scripts/build-electron.sh              默认 macOS
#   bash scripts/build-electron.sh --win        Windows .exe
#   bash scripts/build-electron.sh --linux      Linux .AppImage
#   bash scripts/build-electron.sh --all        全部平台
#
# 前置条件：
#   - Python 3.11+、Node.js 18+、npm
#   - Windows 打包需要 wine（brew install wine）
# ===========================================================================

set -euo pipefail

cd "$(dirname "$0")/.."

PLATFORM="${1:-}"
case "$PLATFORM" in
  --win)   PLATFORM="--win" ;;
  --linux) PLATFORM="--linux" ;;
  --all)   PLATFORM="--mac --win --linux" ;;
  "")      PLATFORM="--mac" ;;
  *) echo "用法: $0 [--win|--linux|--all]"; exit 1 ;;
esac

echo "╔══════════════════════════════════════════════╗"
echo "║     ZLink Agent 全自包含打包                  ║"
echo "║     平台: $PLATFORM"
echo "╚══════════════════════════════════════════════╝"

echo ""
echo "[1/4] 构建前端..."
cd web && npm ci && npm run build && cd ..
echo "✅ 前端构建完成"

echo ""
echo "[2/4] 打包 Python 运行环境..."
bash scripts/bundle-python.sh
echo "✅ Python 环境打包完成"

echo ""
echo "[3/4] 打包 Electron 应用..."
npx electron-builder $PLATFORM --config electron-builder.yml
echo "✅ Electron 打包完成"

echo ""
echo "[4/4] 清理临时文件..."
rm -rf build/python-bundle
echo "✅ 清理完成"
echo ""
echo "📦 成品位置: dist-electron/"
