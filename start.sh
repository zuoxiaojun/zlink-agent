#!/bin/bash
set -e

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"

# 从 .env 文件读取端口（有默认值）
if [ -f "$PROJECT_DIR/.env" ]; then
    source <(grep -E '^YS_(FRONTEND_PORT|AGENT_PORT)=' "$PROJECT_DIR/.env")
fi
BACKEND_PORT="${YS_AGENT_PORT:-8089}"
FRONTEND_PORT="${YS_FRONTEND_PORT:-8088}"

cleanup() {
    echo ""
    echo "Shutting down YS-Agent..."
    kill $BACKEND_PID 2>/dev/null || true
    kill $FRONTEND_PID 2>/dev/null || true
    wait $BACKEND_PID 2>/dev/null || true
    wait $FRONTEND_PID 2>/dev/null || true
    echo "Done."
    exit 0
}

trap cleanup SIGINT SIGTERM

# ── Backend ──
PID=$(lsof -ti :$BACKEND_PORT 2>/dev/null || true)
if [ -n "$PID" ]; then
    echo "Port $BACKEND_PORT in use, killing PID $PID..."
    kill "$PID" 2>/dev/null || true
    sleep 1
fi

cd "$PROJECT_DIR"
source .venv/bin/activate
echo "Starting backend on http://localhost:$BACKEND_PORT ..."
uvicorn backend.main:app --host 0.0.0.0 --port $BACKEND_PORT &
BACKEND_PID=$!

# ── Frontend ──
PID=$(lsof -ti :$FRONTEND_PORT 2>/dev/null || true)
if [ -n "$PID" ]; then
    echo "Port $FRONTEND_PORT in use, killing PID $PID..."
    kill "$PID" 2>/dev/null || true
    sleep 1
fi

cd "$PROJECT_DIR/web"
echo "Starting frontend on http://localhost:$FRONTEND_PORT ..."
npx vite --host 0.0.0.0 &
FRONTEND_PID=$!

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  YS-Agent 启动完成"
echo "  前端: http://localhost:$FRONTEND_PORT"
echo "  后端: http://localhost:$BACKEND_PORT"
echo "  API 文档: http://localhost:$BACKEND_PORT/docs"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

wait $BACKEND_PID $FRONTEND_PID
