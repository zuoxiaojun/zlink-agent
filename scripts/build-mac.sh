#!/bin/bash
# ──────────────────────────────────────────────────────────
# YS-Agent macOS 客户端完整打包脚本
# 用法: ./scripts/build-mac.sh [--no-pyinstaller]
#
# 前置条件:
#   - Python 3.11+ 虚拟环境已激活 (source .venv/bin/activate)
#   - pyinstaller 已安装 (pip install pyinstaller)
#   - Node.js 18+
# ──────────────────────────────────────────────────────────
set -euo pipefail
PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$PROJECT_DIR"

echo "================================================"
echo "  YS-Agent macOS 客户端构建"
echo "================================================"

# ── Step 1: Build frontend ──
echo ""
echo "[1/4] 构建前端 (React + Vite)..."
cd "$PROJECT_DIR/web"
npm ci
npm run build
echo "  ✅ 前端构建完成: web/dist/"

# ── Step 2: Install root npm deps (Electron) ──
echo ""
echo "[2/4] 安装 Electron 构建依赖..."
cd "$PROJECT_DIR"
npm ci
echo "  ✅ Electron 依赖安装完成"

# ── Step 3: PyInstaller (optional, can skip for testing) ──
SKIP_PYI="${2:-}"
if [ "${1:-}" = "--no-pyinstaller" ] || [ "$SKIP_PYI" = "--no-pyinstaller" ]; then
    echo ""
    echo "[3/4] ⏭️  跳过 PyInstaller 打包 (--no-pyinstaller)"
else
    echo ""
    echo "[3/4] PyInstaller 打包 Python 后端..."
    source .venv/bin/activate
    pip install -r requirements.txt
    pyinstaller backend/ys-agent.spec --clean --noconfirm
    echo "  ✅ PyInstaller 完成: dist/ys-agent-backend/"
fi

# ── Step 4: electron-builder ──
echo ""
echo "[4/4] electron-builder 打包 .dmg..."
npx electron-builder --mac --config electron-builder.yml
echo "  ✅ 构建完成！"

# ── 输出结果 ──
echo ""
echo "================================================"
echo "  构建产物"
if [ -d "dist/mac" ]; then
    echo "  📦 dist/mac/YS-Agent.app"
fi
echo "================================================"
