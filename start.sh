#!/bin/bash
# ===========================================================================
# start.sh — YS-Agent 统一启动脚本
#
# 用法:
#   ./start.sh          启动（后端 Serve 前端静态文件，生产模式）
#   ./start.sh --dev    启动开发模式（后端 + Vite 热更新）
#   ./start.sh stop     停止后端服务
#   ./start.sh --help   显示帮助
# ===========================================================================

set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"

# ── 颜色 ──
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'
info()  { echo -e "${CYAN}[start]${NC} $*"; }
ok()    { echo -e "${GREEN}[start]${NC} $*"; }
err()   { echo -e "${RED}[start]${NC} $*"; }

# ── 系统检测 ──
case "$(uname -s)" in
  Darwin)  OS="macos" ;;
  Linux)   OS="linux" ;;
  MINGW*|MSYS*|CYGWIN*) OS="windows" ;;
  *)       OS="unknown" ;;
esac

VENV_ACTIVATE="$PROJECT_DIR/.venv/bin/activate"
[ "$OS" = "windows" ] && VENV_ACTIVATE="$PROJECT_DIR/.venv/Scripts/activate"

# ── 端口配置 ──
if [ -f "$PROJECT_DIR/.env" ]; then
    source <(grep -E '^YS_(AGENT_PORT|FRONTEND_PORT)=' "$PROJECT_DIR/.env" 2>/dev/null || true)
fi
BACKEND_PORT="${YS_AGENT_PORT:-8089}"
FRONTEND_PORT="${YS_FRONTEND_PORT:-8088}"
HOST="${YS_AGENT_HOST:-0.0.0.0}"

# 浏览器访问地址（用 127.0.0.1 而非 0.0.0.0，部分浏览器不认 0.0.0.0）
BROWSER_URL="http://127.0.0.1:$BACKEND_PORT"

# ── 端口清理 ──
kill_port() {
    local port=$1 pid
    if command -v lsof &>/dev/null; then
        pid=$(lsof -ti :"$port" 2>/dev/null || true)
    elif command -v netstat &>/dev/null; then
        pid=$(netstat -ano 2>/dev/null | grep ":$port " | awk '{print $NF}' | head -1 || true)
    fi
    if [ -n "$pid" ]; then
        info "端口 $port 已被占用，停止进程 PID $pid..."
        kill "$pid" 2>/dev/null || true
        sleep 1
        kill -9 "$pid" 2>/dev/null || true
    fi
}

# ── 帮助 ──
if [[ "${1:-}" == "--help" || "${1:-}" == "-h" ]]; then
    echo "YS-Agent — AI Agent for YonSuite ERP"
    echo ""
    echo "用法:"
    echo "  ./start.sh           启动（后端 Serve 前端，生产模式）"
    echo "  ./start.sh --dev     启动开发模式（后端 + Vite 热更新）"
    echo "  ./start.sh stop      停止后端服务"
    echo ""
    echo "快捷命令（安装后可用）："
    echo "  ys-agent             同 ./start.sh"
    echo "  ys-agent stop        同 ./start.sh stop"
    echo "  ys-agent update      拉取最新代码并升级"
    echo "  ys-agent migrate     手动执行数据迁移"
    exit 0
fi

# ── stop ──
if [[ "${1:-}" == "stop" ]]; then
    kill_port "$BACKEND_PORT"
    kill_port "$FRONTEND_PORT"
    ok "服务已停止"
    exit 0
fi

# ── 前置检查 ──
cd "$PROJECT_DIR"
if [ ! -f "$VENV_ACTIVATE" ]; then
    err "虚拟环境不存在，请先运行: bash setup.sh"
    exit 1
fi

# ── 启动 ──
IS_DEV=false
[[ "${1:-}" == "--dev" ]] && IS_DEV=true

cleanup() {
    echo ""
    info "正在停止 YS-Agent..."
    kill $BACKEND_PID 2>/dev/null || true
    kill $FRONTEND_PID 2>/dev/null || true
    wait $BACKEND_PID 2>/dev/null || true
    wait $FRONTEND_PID 2>/dev/null || true
    ok "已停止"
    exit 0
}
trap cleanup SIGINT SIGTERM

kill_port "$BACKEND_PORT"

PYTHONPATH="" source "$VENV_ACTIVATE"

# 确保 PID 变量始终有值（避免 set -u 报错）
BACKEND_PID=""
FRONTEND_PID=""

# ── 启动后端 ──
info "启动后端: $BROWSER_URL"
PYTHONPATH="" uvicorn backend.main:app --host "$HOST" --port "$BACKEND_PORT" &
BACKEND_PID=$!

# ── 前端 ──
if $IS_DEV; then
    # 开发模式：Vite 热更新
    kill_port "$FRONTEND_PORT"
    cd "$PROJECT_DIR/web"
    info "启动 Vite 开发服务器: http://localhost:$FRONTEND_PORT"
    npx vite --host "$HOST" --port "$FRONTEND_PORT" &
    FRONTEND_PID=$!
    cd "$PROJECT_DIR"
elif [ -d "$PROJECT_DIR/web/dist" ]; then
    info "前端已构建，通过后端统一 Serve: http://$HOST:$BACKEND_PORT"
else
    warn "前端未构建（web/dist 不存在），请先运行: bash setup.sh"
fi

echo ""
echo "╔══════════════════════════════════════════════╗"
echo "║     YS-Agent 启动完成                         ║"
if $IS_DEV; then
echo "║  模式: 开发模式 (Vite 热更新)                 ║"
fi
echo "║  访问: $BROWSER_URL              ║"
echo "║  API 文档: $BROWSER_URL/docs    ║"
echo "║  按 Ctrl+C 停止                               ║"
echo "╚══════════════════════════════════════════════╝"
echo ""

# 等后端就绪后打开浏览器（MCP 在后台异步连接）
echo ""
echo "  正在启动后端，自动打开浏览器..."
for i in $(seq 1 30); do
    if curl -sf "http://127.0.0.1:$BACKEND_PORT/api/config" > /dev/null 2>&1; then
        break
    fi
    sleep 0.2
done

case "$OS" in
  macos) open "$BROWSER_URL" 2>/dev/null || echo "  浏览器打开失败，请手动访问 $BROWSER_URL" ;;
  linux) xdg-open "http://$HOST:$BACKEND_PORT" 2>/dev/null || true ;;
  windows) start "http://$HOST:$BACKEND_PORT" ;;
esac

wait $BACKEND_PID $FRONTEND_PID
