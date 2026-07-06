#!/bin/bash
# ===========================================================================
# setup.sh — YS-Agent 一键安装部署脚本
#
# 前置条件：
#   - Python >= 3.11（https://www.python.org/downloads/）
#   - Node.js >= 18  + npm（https://nodejs.org/）
#   - git（可选，用于升级功能）
#
# 功能：
#   1. 检查依赖环境
#   2. 创建 Python 虚拟环境
#   3. 安装 Python 依赖（支持国内镜像加速）
#   4. 创建 .env 配置文件
#   5. 创建数据目录
#   6. 构建前端
#   7. 安装 ys-agent 快捷命令
#   8. 执行数据迁移
#
# 环境变量（镜像加速）：
#   YS_USE_MIRROR=true          是否使用国内镜像（默认 true）
#   YS_PIP_MIRROR=...           PyPI 镜像地址
#   YS_NPM_MIRROR=...           npm 镜像地址
# ===========================================================================

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

info()  { echo -e "${CYAN}[INFO]${NC}  $*"; }
ok()    { echo -e "${GREEN}[OK]${NC}    $*"; }
warn()  { echo -e "${YELLOW}[WARN]${NC}  $*"; }
err()   { echo -e "${RED}[ERROR]${NC} $*"; }

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$PROJECT_DIR"

# ── 系统环境检测 ──
case "$(uname -s)" in
  Darwin)  OS="macos" ;;
  Linux)   OS="linux" ;;
  MINGW*|MSYS*|CYGWIN*) OS="windows" ;;
  *)       OS="unknown" ;;
esac

VENV_ACTIVATE="$PROJECT_DIR/.venv/bin/activate"
[ "$OS" = "windows" ] && VENV_ACTIVATE="$PROJECT_DIR/.venv/Scripts/activate"

echo ""
echo -e "${CYAN}╔══════════════════════════════════════════════╗${NC}"
echo -e "${CYAN}║     YS-Agent 安装部署                        ║${NC}"
echo -e "${CYAN}║     $PROJECT_DIR${NC}"
echo -e "${CYAN}╚══════════════════════════════════════════════╝${NC}"
echo ""

# ── 检测是否已有旧版本 ──
_IS_UPGRADE=false
if [ -f ".venv/bin/python" ] || [ -d "data/sessions" ]; then
    _IS_UPGRADE=true
    echo -e "${YELLOW}╔══════════════════════════════════════════════╗${NC}"
    echo -e "${YELLOW}║  检测到已有安装，升级模式                      ║${NC}"
    echo -e "${YELLOW}║  用户数据 data/ 会保留                         ║${NC}"
    echo -e "${YELLOW}╚══════════════════════════════════════════════╝${NC}"
    echo ""
fi

# ── 1. 依赖检查 ─────────────────────────────────────────────────────────────
echo -e "${GREEN}[1/8] 检查依赖环境...${NC}"

PY_CMD=""
for cmd in python3.14 python3.13 python3.12 python3.11 python3; do
    if command -v "$cmd" &>/dev/null; then
        PY_VER=$("$cmd" --version 2>&1 | awk '{match($2, /[0-9]+\.[0-9]+/); print substr($2, RSTART, RLENGTH)}')
        if awk -v ver="$PY_VER" 'BEGIN {split(ver, v, "."); exit !(v[1] > 3 || (v[1] == 3 && v[2] >= 11))}' 2>/dev/null; then
            PY_CMD="$cmd"
            break
        fi
    fi
done

if [ -z "$PY_CMD" ]; then
    err "需要 Python >= 3.11，未在系统中找到。"
    echo ""
    echo "  请安装 Python 后重新运行："
    echo "    macOS:   brew install python@3.12"
    echo "             或 https://www.python.org/downloads/"
    echo "    Linux:   apt install python3 python3-venv python3-pip"
    echo "    Windows: https://www.python.org/downloads/"
    echo ""
    exit 1
fi
ok "Python: $($PY_CMD --version)"

if command -v node &>/dev/null; then
    ok "Node.js: $(node --version)"
else
    err "需要 Node.js >= 18，未在系统中找到。"
    echo ""
    echo "  请安装 Node.js 后重新运行："
    echo "    macOS:   brew install node"
    echo "             或 https://nodejs.org/"
    echo "    Linux:   apt install nodejs npm"
    echo "    Windows: https://nodejs.org/"
    echo ""
    exit 1
fi

if command -v npm &>/dev/null; then
    ok "npm: $(npm --version)"
else
    err "需要 npm。"
    echo "  npm 通常随 Node.js 一起安装，请检查安装是否正确。"
    exit 1
fi

if command -v git &>/dev/null; then
    ok "git: $(git --version)"
else
    warn "未找到 git，无法使用升级功能（ys-agent update）"
fi

echo ""

# ── 2. 镜像配置 ─────────────────────────────────────────────────────────────
echo -e "${GREEN}[2/8] 配置镜像源...${NC}"
USE_MIRROR="${YS_USE_MIRROR:-true}"
if [ "$USE_MIRROR" = "true" ]; then
    PIP_MIRROR="${YS_PIP_MIRROR:-https://mirrors.tuna.tsinghua.edu.cn/pypi/web/simple}"
    NPM_MIRROR="${YS_NPM_MIRROR:-https://mirrors.npmmirror.com}"
    echo "  PIP: $PIP_MIRROR"
    echo "  NPM: $NPM_MIRROR"
else
    PIP_MIRROR=""
    NPM_MIRROR=""
    echo "  不使用镜像源"
fi
echo ""

# ── 3. Python 虚拟环境 ──────────────────────────────────────────────────────
echo -e "${GREEN}[3/8] 创建 Python 虚拟环境...${NC}"
if [ ! -d ".venv" ]; then
    $PY_CMD -m venv .venv
    ok "虚拟环境已创建"
else
    info "虚拟环境已存在，跳过"
fi
echo ""

# ── 4. 安装 Python 依赖 ────────────────────────────────────────────────────
echo -e "${GREEN}[4/8] 安装 Python 依赖...${NC}"
PYTHONPATH="" source "$VENV_ACTIVATE"

pip install --upgrade pip -q 2>/dev/null || true

if [ -n "$PIP_MIRROR" ]; then
    pip install -r requirements.txt -q -i "$PIP_MIRROR"
else
    pip install -r requirements.txt -q
fi

if [ -f "pyproject.toml" ]; then
    if [ -n "$PIP_MIRROR" ]; then
        pip install -e ".[all]" -q -i "$PIP_MIRROR" 2>/dev/null || true
    else
        pip install -e ".[all]" -q 2>/dev/null || true
    fi
fi
ok "Python 依赖安装完成"
echo ""

# ── 5. 配置文件 ────────────────────────────────────────────────────────────
echo -e "${GREEN}[5/8] 配置文件...${NC}"
if [ ! -f ".env" ]; then
    if [ -f ".env.example" ]; then
        cp .env.example .env
        ok ".env 已从 .env.example 创建"
    else
        warn ".env.example 不存在，跳过"
    fi
else
    info ".env 已存在，跳过"
fi
echo ""

# ── 6. 数据目录 ────────────────────────────────────────────────────────────
echo -e "${GREEN}[6/8] 创建数据目录...${NC}"
mkdir -p data/logs data/sessions data/memory data/backups
ok "数据目录就绪"
echo ""

# ── 7. 前端构建 ────────────────────────────────────────────────────────────
echo -e "${GREEN}[7/8] 安装前端依赖并构建...${NC}"
cd "$PROJECT_DIR/web"

if [ -n "$NPM_MIRROR" ]; then
    npm config set registry "$NPM_MIRROR" 2>/dev/null || true
    info "npm 镜像已设置: $NPM_MIRROR"
fi

npm ci --silent 2>/dev/null || npm install --silent
ok "前端依赖安装完成"

npm run build
ok "前端构建完成"

cd "$PROJECT_DIR"
echo ""

# ── 8. 快捷命令 + 数据迁移 ────────────────────────────────────────────────
echo -e "${GREEN}[8/8] 安装快捷命令并执行初始化...${NC}"

INSTALL_DIR="${HOME}/.local/bin"
mkdir -p "$INSTALL_DIR"

LAUNCHER_SRC="$PROJECT_DIR/scripts/ys-agent.sh"
LAUNCHER_DST="$INSTALL_DIR/ys-agent"

if [ -f "$LAUNCHER_SRC" ]; then
    sed "s|__PROJECT_DIR__|$PROJECT_DIR|g" "$LAUNCHER_SRC" > "$LAUNCHER_DST"
    chmod +x "$LAUNCHER_DST"
    ok "快捷命令已安装: $LAUNCHER_DST"
else
    warn "未找到启动器模板: $LAUNCHER_SRC，跳过"
fi

if ! echo ":$PATH:" | grep -q ":${HOME}/.local/bin:"; then
    warn "~/.local/bin 不在 PATH 中，请添加到 Shell 配置："
    echo '    export PATH="$HOME/.local/bin:$PATH"'
    echo "  然后执行: source ~/.zshrc"
fi

PYTHONPATH="" source "$VENV_ACTIVATE"
PYTHONPATH="$PROJECT_DIR" python -m scripts.migrate && ok "数据迁移检查完成" || warn "数据迁移执行异常（可后续手动执行）"

# 升级时修复内置 MCP 标记
if $_IS_UPGRADE; then
    PYTHONPATH="$PROJECT_DIR" python -c "
import json, sys
cfg_path = sys.argv[1] + '/data/config.json'
try:
    with open(cfg_path, encoding='utf-8') as f:
        cfg = json.load(f)
    servers = cfg.get('mcp_servers', {})
    changed = False
    for name in ('yonsuite', 'mcp-server-chart'):
        if name in servers and not servers[name].get('builtin'):
            servers[name]['builtin'] = True
            changed = True
    if changed:
        with open(cfg_path, 'w', encoding='utf-8') as f:
            json.dump(cfg, f, indent=2, ensure_ascii=False)
        print('  内置 MCP 服务器标记已更新')
except FileNotFoundError:
    pass
" "$PROJECT_DIR" && ok "内置 MCP 服务器标记已修复" || warn "内置 MCP 标记修复失败（可忽略）"
fi

echo ""

# ── 完成 ──
if $_IS_UPGRADE; then
    echo -e "${CYAN}╔══════════════════════════════════════════════╗${NC}"
    echo -e "${CYAN}║     ✅ YS-Agent 升级完成                      ║${NC}"
    echo -e "${CYAN}╠══════════════════════════════════════════════╣${NC}"
    echo -e "${CYAN}║  安装路径: $PROJECT_DIR${NC}"
    echo -e "${CYAN}║  用户数据: 已保留                             ║${NC}"
    echo -e "${CYAN}╚══════════════════════════════════════════════╝${NC}"
    echo ""
    echo "  升级完成，请重启后端：ys-agent stop && ys-agent"
else
    echo -e "${CYAN}╔══════════════════════════════════════════════╗${NC}"
    echo -e "${CYAN}║     ✅ YS-Agent 安装完成                      ║${NC}"
    echo -e "${CYAN}╠══════════════════════════════════════════════╣${NC}"
    echo -e "${CYAN}║  安装路径: $PROJECT_DIR${NC}"
    echo -e "${CYAN}║  快捷命令: ys-agent                           ║${NC}"
    echo -e "${CYAN}║  数据目录: $PROJECT_DIR/data/${NC}"
    echo -e "${CYAN}╚══════════════════════════════════════════════╝${NC}"
fi
echo ""
echo "  启动方式："
echo ""
echo "    ys-agent                 启动后端（浏览器访问 http://localhost:8089）"
    echo "    ys-agent update          升级到最新版本"
    echo "    ys-agent stop            停止服务"
echo "    ys-agent --help          查看全部命令"
echo ""
echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
