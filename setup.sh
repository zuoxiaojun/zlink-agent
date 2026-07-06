#!/bin/bash
# ===========================================================================
# setup.sh — YS-Agent 一键安装部署脚本
#
# 功能：
#   1. 检查依赖（Python 3.11+、Node.js、npm、git）
#   2. 创建 Python 虚拟环境（如不存在）
#   3. 安装 Python 依赖（支持国内镜像加速）
#   4. 创建 .env 配置文件（如不存在）
#   5. 创建数据目录 data/
#   6. 安装前端依赖并构建前端
#   7. 将 `ys-agent` 快捷命令安装到 ~/.local/bin/
#   8. 执行数据迁移
#
# 安装后：
#   终端输入 `ys-agent` 即可启动服务
#   也可继续使用 ./start.sh / ./run_backend.sh / ./run_frontend.sh
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
VENV_PYTHON="$PROJECT_DIR/.venv/bin/python"
[ "$OS" = "windows" ] && VENV_ACTIVATE="$PROJECT_DIR/.venv/Scripts/activate" && VENV_PYTHON="$PROJECT_DIR/.venv/Scripts/python"

echo ""
echo -e "${CYAN}╔══════════════════════════════════════════════╗${NC}"
echo -e "${CYAN}║        YS-Agent 一键安装部署                  ║${NC}"
echo -e "${CYAN}║        $PROJECT_DIR${NC}"
echo -e "${CYAN}╚══════════════════════════════════════════════╝${NC}"
echo ""


# ── 1. 前置依赖检查 ─────────────────────────────────────────────────────────
echo -e "${GREEN}[1/8] 检查依赖...${NC}"

# Python
PY_CMD=""
for cmd in python3.14 python3.13 python3.12 python3.11 python3; do
    if command -v "$cmd" &>/dev/null; then
        PY_VER=$("$cmd" --version 2>&1 | grep -oP '\d+\.\d+')
        if awk "BEGIN {exit !($PY_VER >= 3.11)}" 2>/dev/null; then
            PY_CMD="$cmd"
            break
        fi
    fi
done

if [ -z "$PY_CMD" ]; then
    err "需要 Python >= 3.11，请安装：https://www.python.org/downloads/"
    exit 1
fi
ok "Python: $($PY_CMD --version)"

# Node.js — 如果系统没有，自动下载便携版（仅构建用）
NODE_BIN=""
if command -v node &>/dev/null; then
    NODE_BIN="$(command -v node)"
    ok "Node.js: $(node --version)"
else
    warn "未找到 Node.js，正在下载便携版..."
    _NODE_DIR="$PROJECT_DIR/.node"
    mkdir -p "$_NODE_DIR"
    _NODE_VER="22.14.0"
    case "$(uname -s)-$(uname -m)" in
        Darwin-arm64)  _NODE_URL="https://nodejs.org/dist/v$_NODE_VER/node-v$_NODE_VER-darwin-arm64.tar.gz" ;;
        Darwin-x86_64) _NODE_URL="https://nodejs.org/dist/v$_NODE_VER/node-v$_NODE_VER-darwin-x64.tar.gz" ;;
        Linux-arm64)   _NODE_URL="https://nodejs.org/dist/v$_NODE_VER/node-v$_NODE_VER-linux-arm64.tar.gz" ;;
        Linux-x86_64)  _NODE_URL="https://nodejs.org/dist/v$_NODE_VER/node-v$_NODE_VER-linux-x64.tar.gz" ;;
        *)
            err "不支持的系统架构: $(uname -s)-$(uname -m)，请手动安装 Node.js >= 18"
            exit 1
            ;;
    esac
    echo "  下载 $_NODE_URL ..."
    curl -fsSL "$_NODE_URL" | tar xz -C "$_NODE_DIR" --strip-components=1
    NODE_BIN="$_NODE_DIR/bin/node"
    ok "Node.js 便携版已安装: $($NODE_BIN --version)"
fi

# npm
if command -v npm &>/dev/null; then
    ok "npm: $(npm --version)"
elif [ -f "$(dirname "$NODE_BIN")/npm" ]; then
    ok "npm: $($(dirname "$NODE_BIN")/npm --version)"
else
    err "未找到 npm。"
    exit 1
fi

if command -v git &>/dev/null; then
    ok "git: $(git --version)"
else
    warn "未找到 git，将无法使用升级功能（ys-agent update）"
fi

echo ""

# ── 2. 镜像配置 ──
echo -e "${GREEN}[2/8] 配置镜像源...${NC}"
USE_MIRROR="${YS_USE_MIRROR:-true}"
if [ "$USE_MIRROR" = "true" ]; then
    PIP_MIRROR="${YS_PIP_MIRROR:-https://mirrors.tuna.tsinghua.edu.cn/pypi/web/simple}"
    NPM_MIRROR="${YS_NPM_MIRROR:-https://mirrors.npmmirror.com}"
    echo "  PIP: $PIP_MIRROR"
    echo "  NPM: $NPM_MIRROR"
    echo "  设置 YS_USE_MIRROR=false 可关闭镜像"
else
    PIP_MIRROR=""
    NPM_MIRROR=""
    echo "  不使用镜像源"
fi
echo ""

# ── 3. Python 虚拟环境 ──
echo -e "${GREEN}[3/8] 创建 Python 虚拟环境...${NC}"
if [ ! -d ".venv" ]; then
    $PY_CMD -m venv .venv
    ok "虚拟环境已创建"
else
    info "虚拟环境已存在，跳过"
fi
echo ""

# ── 4. 安装 Python 依赖 ──
echo -e "${GREEN}[4/8] 安装 Python 依赖...${NC}"
# Clear PYTHONPATH to avoid venv conflicts (e.g. from Hermes, asdf, pyenv)
PYTHONPATH="" source "$VENV_ACTIVATE"

pip install --upgrade pip -q 2>/dev/null || true

if [ -n "$PIP_MIRROR" ]; then
    pip install -r requirements.txt -q -i "$PIP_MIRROR"
else
    pip install -r requirements.txt -q
fi

# 安装项目自身（可选依赖）
if [ -f "pyproject.toml" ]; then
    if [ -n "$PIP_MIRROR" ]; then
        pip install -e ".[all]" -q -i "$PIP_MIRROR" 2>/dev/null || true
    else
        pip install -e ".[all]" -q 2>/dev/null || true
    fi
fi
ok "Python 依赖安装完成"
echo ""

# ── 5. 配置文件 ──
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

# ── 6. 数据目录 ──
echo -e "${GREEN}[6/8] 创建数据目录...${NC}"
mkdir -p data/logs data/sessions data/memory data/backups
ok "数据目录就绪"
echo ""

# ── 7. 前端构建 ──
echo -e "${GREEN}[7/8] 安装前端依赖并构建...${NC}"
cd "$PROJECT_DIR/web"

# 如果用便携版 Node.js，用它的 npm
_NPM_CMD="npm"
if [ -n "$NODE_BIN" ] && [ -f "$(dirname "$NODE_BIN")/npm" ]; then
    _NPM_CMD="$(dirname "$NODE_BIN")/npm"
    PATH="$(dirname "$NODE_BIN"):$PATH"
fi

if [ -n "$NPM_MIRROR" ]; then
    $_NPM_CMD config set registry "$NPM_MIRROR"
    info "npm 镜像已设置: $NPM_MIRROR"
fi

$_NPM_CMD ci --silent 2>/dev/null || $_NPM_CMD install --silent
ok "前端依赖安装完成"

$_NPM_CMD run build
ok "前端构建完成"

cd "$PROJECT_DIR"
echo ""

# ── 8. 安装 ys-agent 快捷命令 + 数据迁移 ──
echo -e "${GREEN}[8/8] 安装快捷命令并执行初始化...${NC}"

# 安装 ys-agent 到 ~/.local/bin/
INSTALL_DIR="${HOME}/.local/bin"
mkdir -p "$INSTALL_DIR"

LAUNCHER_SRC="$PROJECT_DIR/scripts/ys-agent.sh"
LAUNCHER_DST="$INSTALL_DIR/ys-agent"

if [ -f "$LAUNCHER_SRC" ]; then
    # 替换 __PROJECT_DIR__ 为实际路径
    sed "s|__PROJECT_DIR__|$PROJECT_DIR|g" "$LAUNCHER_SRC" > "$LAUNCHER_DST"
    chmod +x "$LAUNCHER_DST"
    ok "快捷命令已安装: $LAUNCHER_DST"
else
    warn "未找到启动器模板: $LAUNCHER_SRC，跳过快捷命令安装"
fi

# 检查 PATH
if ! echo ":$PATH:" | grep -q ":${HOME}/.local/bin:"; then
    warn "~/.local/bin 不在 PATH 中，请将以下内容添加到 ~/.zshrc（或 ~/.bashrc）："
    echo '    export PATH="$HOME/.local/bin:$PATH"'
    echo "  添加后执行: source ~/.zshrc"
fi

# 数据迁移
PYTHONPATH="" source "$VENV_ACTIVATE"
python -m scripts.migrate && ok "数据迁移检查完成" || warn "数据迁移执行异常（可后续手动执行）"

echo ""

# ── 完成 ──
echo -e "${CYAN}╔══════════════════════════════════════════════╗${NC}"
echo -e "${CYAN}║     ✅ YS-Agent 安装完成                      ║${NC}"
echo -e "${CYAN}╠══════════════════════════════════════════════╣${NC}"
echo -e "${CYAN}║  安装路径: $PROJECT_DIR${NC}"
echo -e "${CYAN}║  快捷命令: ys-agent                           ║${NC}"
echo -e "${CYAN}║  数据目录: $PROJECT_DIR/data/${NC}"
echo -e "${CYAN}╚══════════════════════════════════════════════╝${NC}"
echo ""
echo "  启动方式："
echo ""
echo "    ys-agent                 # 仅后端（推荐，终端全局可用）"
echo "    ys-agent --dev           # 后端 + 前端开发服务器"
echo "    ys-agent update          # 升级到最新版本"
echo "    ys-agent --help          # 查看全部命令"
echo ""
echo "    或使用原有方式："
echo "    ./start.sh               # 前后端一起启动"
echo "    ./run_backend.sh         # 仅后端"
echo "    ./run_frontend.sh        # 仅前端"
echo ""
echo "  前端访问地址在 .env 中配置"
echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
