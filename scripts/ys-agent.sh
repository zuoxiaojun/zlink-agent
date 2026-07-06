#!/usr/bin/env bash
# ===========================================================================
# ys-agent — YS-Agent 启动命令
#
# 由 setup.sh 安装到 ~/.local/bin/ys-agent，替换 __PROJECT_DIR__ 为实际路径。
#
# 用法：
#   ys-agent             启动后端（后台进程，后端 Serve 前端）
#   ys-agent --dev       启动开发模式（后端 + Vite 热更新）
#   ys-agent stop        停止正在运行的服务
#   ys-agent update      拉取最新代码并升级
#   ys-agent migrate     手动执行数据迁移
#   ys-agent version     显示版本信息
#   ys-agent --help      显示帮助
# ===========================================================================

set -euo pipefail

# ── 项目路径（setup.sh 安装时自动替换） ──────────────────────────────────────
YS_PROJECT_DIR="__PROJECT_DIR__"

# ── 颜色 ────────────────────────────────────────────────────────────────────
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

info()  { echo -e "${CYAN}[ys-agent]${NC} $*"; }
ok()    { echo -e "${GREEN}[ys-agent]${NC} $*"; }
err()   { echo -e "${RED}[ys-agent]${NC} $*"; }

# ── 系统环境检测 ────────────────────────────────────────────────────────────
case "$(uname -s)" in
  Darwin)  OS="macos" ;;
  Linux)   OS="linux" ;;
  MINGW*|MSYS*|CYGWIN*) OS="windows" ;;
  *)       OS="unknown" ;;
esac

VENV_ACTIVATE="$YS_PROJECT_DIR/.venv/bin/activate"
[ "$OS" = "windows" ] && VENV_ACTIVATE="$YS_PROJECT_DIR/.venv/Scripts/activate"

# ── 帮助 ────────────────────────────────────────────────────────────────────
if [[ "${1:-}" == "--help" || "${1:-}" == "-h" ]]; then
    echo "YS-Agent — AI Agent for YonSuite ERP"
    echo ""
    echo "用法:"
    echo "  ys-agent                    启动后端，浏览器访问 http://localhost:8089"
    echo "  ys-agent stop               停止正在运行的服务"
    echo "  ys-agent update             拉取最新代码并升级"
    echo "  ys-agent migrate            手动执行数据迁移"
    echo "  ys-agent version / --version 显示版本信息"
    echo "  ys-agent --help             显示此帮助"
    exit 0
fi

# ── 前置检查 ────────────────────────────────────────────────────────────────
if [[ ! -d "$YS_PROJECT_DIR" ]]; then
    err "项目目录不存在: $YS_PROJECT_DIR"
    err "请重新运行安装脚本: bash setup.sh"
    exit 1
fi

cd "$YS_PROJECT_DIR"

if [[ ! -f "$VENV_ACTIVATE" ]]; then
    err "虚拟环境未安装，请先运行: bash setup.sh"
    exit 1
fi

# ── 端口清理函数 ────────────────────────────────────────────────────────────
kill_port() {
    local port=$1 pid
    if command -v lsof &>/dev/null; then
        pid=$(lsof -ti :"$port" 2>/dev/null || true)
    elif command -v netstat &>/dev/null; then
        pid=$(netstat -ano 2>/dev/null | grep ":$port " | awk '{print $NF}' | head -1 || true)
    fi
    if [[ -n "$pid" ]]; then
        info "端口 $port 已被占用，停止进程 PID $pid..."
        kill "$pid" 2>/dev/null || true
        sleep 1
        kill -9 "$pid" 2>/dev/null || true
    fi
}

# ── 读取端口（兼容 .env） ──────────────────────────────────────────────────
if [[ -f "$YS_PROJECT_DIR/.env" ]]; then
    source <(grep -E '^YS_(AGENT_PORT|FRONTEND_PORT)=' "$YS_PROJECT_DIR/.env" 2>/dev/null || true)
fi
BACKEND_PORT="${YS_AGENT_PORT:-8089}"
FRONTEND_PORT="${YS_FRONTEND_PORT:-8088}"

# ── 子命令处理 ──────────────────────────────────────────────────────────────
case "${1:-}" in

    # ── version / --version ──
    version*|--version*)
        PYTHONPATH="" source "$VENV_ACTIVATE"
        python -c "
from backend.api.system_api import _get_version, _get_git_info
v = _get_version()
g = _get_git_info()
print(f'YS-Agent v{v} ({g[\"tag\"]})')
print(f'  Commit: {g[\"commit\"]}   Branch: {g[\"branch\"]}')
"
        exit 0
        ;;

    # ── update ──
    update)
        bash "$YS_PROJECT_DIR/scripts/update.sh"
        exit $?
        ;;

    # ── migrate ──
    migrate)
        PYTHONPATH="" source "$VENV_ACTIVATE"
        python -m scripts.migrate
        exit $?
        ;;

    # ── stop ──
    stop)
        kill_port "$BACKEND_PORT"
        ok "服务已停止"
        exit 0
        ;;

    # ── --dev 开发模式 ──
    --dev)
        IS_DEV=true
        ;;

    # ── 空参数 → 默认启动 ──
    "")
        # 默认走下方启动流程
        ;;

    # ── 未知命令 ──
    *)
        err "未知命令: ${1:-}"
        err "使用 ys-agent --help 查看可用命令"
        exit 1
        ;;

esac

# ── 启动 ──
IS_DEV="${IS_DEV:-false}"
PYTHONPATH="" source "$VENV_ACTIVATE"
kill_port "$BACKEND_PORT"

HOST="${YS_AGENT_HOST:-0.0.0.0}"

# 前端策略
if $IS_DEV; then
    # 开发模式：强制启动 Vite 热更新
    kill_port "$FRONTEND_PORT"
    cd "$YS_PROJECT_DIR/web"
    npx vite --host "$HOST" --port "$FRONTEND_PORT" &
    FRONTEND_PID=$!
    cd "$YS_PROJECT_DIR"
elif [[ -d "$YS_PROJECT_DIR/web/dist" ]]; then
    info "前端已构建，通过后端统一 Serve: http://$HOST:$BACKEND_PORT"
elif [[ -d "$YS_PROJECT_DIR/web/node_modules" ]]; then
    warn "前端未构建（web/dist 不存在），用 Vite 临时启动..."
    cd "$YS_PROJECT_DIR/web"
    npx vite --host "$HOST" --port "$FRONTEND_PORT" &
    FRONTEND_PID=$!
    cd "$YS_PROJECT_DIR"
else
    warn "前端未构建，请先运行: bash setup.sh"
fi

info "启动后端: http://$HOST:$BACKEND_PORT"

echo ""
echo "╔══════════════════════════════════════════════╗"
echo "║     YS-Agent 启动完成                         ║"
echo "║  访问: http://127.0.0.1:$BACKEND_PORT              ║"
echo "║  API 文档: http://127.0.0.1:$BACKEND_PORT/docs    ║"
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
  macos) open "http://127.0.0.1:$BACKEND_PORT" 2>/dev/null || echo "  浏览器打开失败，请手动访问 http://127.0.0.1:$BACKEND_PORT" ;;
  linux) xdg-open "http://127.0.0.1:$BACKEND_PORT" 2>/dev/null || true ;;
  windows) start "http://127.0.0.1:$BACKEND_PORT" ;;
esac

PYTHONPATH="" exec uvicorn backend.main:app --host "$HOST" --port "$BACKEND_PORT"
