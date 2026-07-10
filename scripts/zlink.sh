#!/usr/bin/env bash
# ===========================================================================
# zlink — ZLink Agent 统一启动命令（唯一入口）
#
# 两种使用方式：
#   1. setup.sh 安装 → 替换 __PROJECT_DIR__ 后安装到 ~/.local/bin/zlink
#   2. 通过 start.sh 调用 → 自动检测项目目录
#
# 用法：
#   zlink                     启动后端（生产模式，后端 Serve 前端）
#   zlink --dev               开发模式（后端 + Vite 热更新）
#   zlink stop                停止服务
#   zlink update              升级
#   zlink migrate             数据 schema 迁移 (旧用户使用)
#   zlink version             显示版本
#   zlink --help              帮助
# ===========================================================================

set -euo pipefail

# ── 项目目录自动检测 ──────────────────────────────────────────────────────
# setup.sh 安装时用 sed 替换首个 __PROJECT_DIR__ 为实际路径。
# 用拼接字符串构造 sentinel，避免 sed 连后面的检测逻辑也一起替换掉。
_ZLINK_SENTINEL="__PROJECT"
_ZLINK_SENTINEL="${_ZLINK_SENTINEL}_DIR__"

_ZLINK_REPLACED="__PROJECT_DIR__"
if echo "$_ZLINK_REPLACED" | grep -qF "$_ZLINK_SENTINEL" >/dev/null 2>&1; then
    # __PROJECT_DIR__ 未被替换 → 直接从源码目录运行
    ZLINK_PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
else
    ZLINK_PROJECT_DIR="$_ZLINK_REPLACED"
fi

# ── 颜色 ────────────────────────────────────────────────────────────────────
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'
info()  { echo -e "${CYAN}[zlink]${NC} $*"; }
ok()    { echo -e "${GREEN}[zlink]${NC} $*"; }
warn()  { echo -e "${YELLOW}[zlink]${NC} $*"; }
err()   { echo -e "${RED}[zlink]${NC} $*"; }

# ── 系统检测 ────────────────────────────────────────────────────────────────
case "$(uname -s)" in
  Darwin)  OS="macos" ;;
  Linux)   OS="linux" ;;
  MINGW*|MSYS*|CYGWIN*) OS="windows" ;;
  *)       OS="unknown" ;;
esac

VENV_ACTIVATE="$ZLINK_PROJECT_DIR/.venv/bin/activate"
[ "$OS" = "windows" ] && VENV_ACTIVATE="$ZLINK_PROJECT_DIR/.venv/Scripts/activate"

# ── 读取端口配置（兼容 .env） ──────────────────────────────────────────────
if [ -f "$ZLINK_PROJECT_DIR/.env" ]; then
    source <(grep -E '^(ZLINK|YS)_(AGENT_HOST|AGENT_PORT|FRONTEND_PORT)=' "$ZLINK_PROJECT_DIR/.env" 2>/dev/null || true)
fi
BACKEND_PORT="${ZLINK_AGENT_PORT:-${YS_AGENT_PORT:-8089}}"
FRONTEND_PORT="${ZLINK_FRONTEND_PORT:-${YS_FRONTEND_PORT:-8088}}"
HOST="${ZLINK_AGENT_HOST:-${YS_AGENT_HOST:-0.0.0.0}}"

# 浏览器打开地址（127.0.0.1 而非 0.0.0.0，部分浏览器不认）
BROWSER_URL="http://127.0.0.1:$BACKEND_PORT"

# ── 端口清理 ────────────────────────────────────────────────────────────────
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
        sleep 0.5
        kill -9 "$pid" 2>/dev/null || true
    fi
}

# ── 前置检查 ────────────────────────────────────────────────────────────────
if [ ! -d "$ZLINK_PROJECT_DIR" ]; then
    err "项目目录不存在: $ZLINK_PROJECT_DIR"
    err "请重新运行: bash setup.sh"
    exit 1
fi
cd "$ZLINK_PROJECT_DIR"

if [ ! -f "$VENV_ACTIVATE" ]; then
    err "虚拟环境未安装，请先运行: bash setup.sh"
    exit 1
fi

# ── 子命令处理 ──────────────────────────────────────────────────────────────
case "${1:-}" in

    # ── version / versionb / --version ──
    version*|--version*)
        PYTHONPATH="" source "$VENV_ACTIVATE"
        python -c "
from backend.api.system_api import _get_version, _get_git_info
v = _get_version()
g = _get_git_info()
print(f'ZLink Agent v{v} ({g[\"tag\"]})')
print(f'  Commit: {g[\"commit\"]}   Branch: {g[\"branch\"]}')
"
        exit 0
        ;;

    # ── update ──
    update)
        bash "$ZLINK_PROJECT_DIR/scripts/update.sh"
        exit $?
        ;;

    # ── migrate (data schema migration) ──
    migrate)
        PYTHONPATH="" source "$VENV_ACTIVATE"
        python -m scripts.migrate
        exit $?
        ;;

    # ── stop ──
    stop)
        kill_port "$BACKEND_PORT"
        kill_port "$FRONTEND_PORT"
        ok "服务已停止"
        exit 0
        ;;

    # ── --help -h ──
    --help|-h)
        echo "ZLink Agent — Smart Link to Your Business Systems"
        echo ""
        echo "用法:"
        echo "  zlink                       启动后端（生产模式，后端 Serve 前端静态文件）"
        echo "  zlink --dev                 启动开发模式（后端 + Vite 热更新）"
        echo "  zlink stop                  停止服务"
        echo "  zlink update                拉取最新代码并升级"
        echo "  zlink migrate               数据 schema 迁移 (旧用户使用,新项目无需)"
        echo "  zlink version / --version   显示版本信息"
        echo "  zlink --help                显示此帮助"
        echo "  ys-agent                    兼容 shim，等同于 zlink"
        exit 0
        ;;

    # ── --dev 开发模式 ──
    --dev)
        IS_DEV=true
        ;;

    # ── 空参数 → 默认启动（走下方逻辑） ──
    "")
        ;;

    # ── 未知命令 ──
    *)
        err "未知命令: ${1:-}"
        err "使用 zlink --help 查看可用命令"
        exit 1
        ;;
esac

# ── 启动 ────────────────────────────────────────────────────────────────────
IS_DEV="${IS_DEV:-false}"
PYTHONPATH="" source "$VENV_ACTIVATE"
kill_port "$BACKEND_PORT"

# 后台进程 PID，用于 trap 清理
BACKEND_PID=""
FRONTEND_PID=""

cleanup() {
    echo ""
    info "正在停止 ZLink Agent..."
    kill "$BACKEND_PID" 2>/dev/null || true
    kill "$FRONTEND_PID" 2>/dev/null || true
    wait "$BACKEND_PID" 2>/dev/null || true
    wait "$FRONTEND_PID" 2>/dev/null || true
    ok "已停止"
    exit 0
}
trap cleanup SIGINT SIGTERM

# ── 前端策略 ──
if $IS_DEV; then
    # 开发模式：Vite 热更新
    kill_port "$FRONTEND_PORT"
    cd "$ZLINK_PROJECT_DIR/web"
    info "启动 Vite 开发服务器: http://localhost:$FRONTEND_PORT"
    npx vite --host "$HOST" --port "$FRONTEND_PORT" &
    FRONTEND_PID=$!
    cd "$ZLINK_PROJECT_DIR"
elif [ -d "$ZLINK_PROJECT_DIR/web/dist" ]; then
    info "前端已构建，通过后端统一 Serve"
else
    warn "前端未构建（web/dist 不存在），仅后端可用"
    warn "请先运行: bash setup.sh"
fi

# ── 启动后端 ──
info "启动后端: $BROWSER_URL"
PYTHONPATH="" uvicorn backend.main:app --host "$HOST" --port "$BACKEND_PORT" &
BACKEND_PID=$!

# ── 打印启动信息 ──
echo ""
echo "╔══════════════════════════════════════════════╗"
echo "║     ZLink Agent 启动完成                         ║"
if $IS_DEV; then
echo "║  模式: 开发模式 (Vite 热更新)                 ║"
fi
echo "║  访问: $BROWSER_URL              ║"
echo "║  API 文档: $BROWSER_URL/docs    ║"
echo "║  按 Ctrl+C 停止                               ║"
echo "╚══════════════════════════════════════════════╝"
echo ""

# ── 等后端就绪后打开浏览器 ──
for i in $(seq 1 20); do
    if curl -sf "http://127.0.0.1:$BACKEND_PORT/api/config" > /dev/null 2>&1; then
        break
    fi
    sleep 0.2
done

case "$OS" in
  macos) open "$BROWSER_URL" 2>/dev/null || true ;;
  linux) xdg-open "$BROWSER_URL" 2>/dev/null || true ;;
  windows) start "$BROWSER_URL" ;;
esac

# ── 保持前台运行，等待任一进程退出 ──
wait "$BACKEND_PID" "$FRONTEND_PID" 2>/dev/null || true
