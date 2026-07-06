#!/bin/bash
# ──────────────────────────────────────────────────────────
# YS-Agent macOS 开发版启动器 (Electron + Python backend)
# 适用于开发调试，不需要 PyInstaller 打包
# ──────────────────────────────────────────────────────────
set -euo pipefail
PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$PROJECT_DIR"

# 启动后端
source .venv/bin/activate
echo "Starting backend on http://localhost:8089 ..."
uvicorn backend.main:app --host 127.0.0.1 --port 8089 &
BACKEND_PID=$!

# 等后端就绪
sleep 2

# 启动前端 dev server + Electron
echo "Starting Electron (loading from Vite dev server) ..."
cd "$PROJECT_DIR/web"
npx vite --host 127.0.0.1 &
VITE_PID=$!

cd "$PROJECT_DIR"
sleep 2
npx electron .

# 清理
kill $BACKEND_PID 2>/dev/null || true
kill $VITE_PID 2>/dev/null || true
wait 2>/dev/null || true
