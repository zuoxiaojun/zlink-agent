#!/bin/bash
set -e

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"

# ── 系统环境检测 ──
case "$(uname -s)" in
  Darwin)  OS="macos" ;;
  Linux)   OS="linux" ;;
  MINGW*|MSYS*|CYGWIN*) OS="windows" ;;
  *)       OS="unknown" ;;
esac

VENV_ACTIVATE="$PROJECT_DIR/.venv/bin/activate"
[ "$OS" = "windows" ] && VENV_ACTIVATE="$PROJECT_DIR/.venv/Scripts/activate"

# 从 .env 文件读取端口（有默认值）
if [ -f "$PROJECT_DIR/.env" ]; then
    source <(grep -E '^YS_(AGENT_PORT|FRONTEND_PORT)=' "$PROJECT_DIR/.env")
fi
BACKEND_PORT="${YS_AGENT_PORT:-8089}"
FRONTEND_PORT="${YS_FRONTEND_PORT:-8088}"
HOST="${YS_AGENT_HOST:-0.0.0.0}"

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

kill_port() {
    local port=$1 pid
    if command -v lsof &>/dev/null; then
        pid=$(lsof -ti :"$port" 2>/dev/null || true)
    elif command -v netstat &>/dev/null; then
        pid=$(netstat -ano 2>/dev/null | grep ":$port " | awk '{print $NF}' | head -1 || true)
    fi
    if [ -n "$pid" ]; then
        echo "Port $port in use, killing PID $pid..."
        kill "$pid" 2>/dev/null || true
        sleep 1
    fi
}

# ── Backend ──
kill_port $BACKEND_PORT

cd "$PROJECT_DIR"
PYTHONPATH="" source "$VENV_ACTIVATE"
echo "Starting backend on http://$HOST:$BACKEND_PORT ..."
PYTHONPATH="" uvicorn backend.main:app --host "$HOST" --port $BACKEND_PORT &
BACKEND_PID=$!

# ── Frontend（仅在 web/node_modules 存在时启动 Vite 开发服务器） ──
if [ -d "$PROJECT_DIR/web/dist" ]; then
    echo "  前端已构建，通过后端 Serve: http://$HOST:$BACKEND_PORT"
elif [ -d "$PROJECT_DIR/web/node_modules" ]; then
    kill_port $FRONTEND_PORT
    cd "$PROJECT_DIR/web"
    echo "Starting frontend dev server on http://localhost:$FRONTEND_PORT ..."
    npx vite --host 0.0.0.0 &
    FRONTEND_PID=$!
    cd "$PROJECT_DIR"
else
    echo "  ⚠ 前端未构建（web/dist 不存在），请先运行: bash setup.sh"
fi

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  YS-Agent 启动完成"
echo "  访问: http://$HOST:$BACKEND_PORT"
if [ -n "$FRONTEND_PID" ]; then
echo "  前端开发服务器: http://localhost:$FRONTEND_PORT"
fi
echo "  API 文档: http://$HOST:$BACKEND_PORT/docs"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# 自动打开浏览器
sleep 2
case "$OS" in
  macos) open "http://$HOST:$BACKEND_PORT" 2>/dev/null || true ;;
  linux) xdg-open "http://$HOST:$BACKEND_PORT" 2>/dev/null || true ;;
  windows) start "http://$HOST:$BACKEND_PORT" ;;
esac

wait $BACKEND_PID $FRONTEND_PID
