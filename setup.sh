#!/bin/bash
set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
CYAN='\033[0;36m'
NC='\033[0m'

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

echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${CYAN}  YS-Agent 一键构建脚本${NC}"
echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""

# ── 镜像配置 ──
USE_MIRROR="${YS_USE_MIRROR:-true}"
if [ "$USE_MIRROR" = "true" ]; then
    PIP_MIRROR="${YS_PIP_MIRROR:-https://mirrors.tuna.tsinghua.edu.cn/pypi/web/simple}"
    NPM_MIRROR="${YS_NPM_MIRROR:-https://mirrors.npmmirror.com}"
    echo -e "${GREEN}使用国内镜像：${NC}"
    echo "  PIP: $PIP_MIRROR"
    echo "  NPM: $NPM_MIRROR"
    echo "  设置 YS_USE_MIRROR=false 可关闭镜像"
else
    PIP_MIRROR=""
    NPM_MIRROR=""
fi

# ── Python 环境 ──
if [ ! -d ".venv" ]; then
    echo -e "${GREEN}[1/5] 创建 Python 虚拟环境...${NC}"
    python3 -m venv .venv
fi

echo -e "${GREEN}[2/5] 安装 Python 依赖...${NC}"
if [ "$OS" = "windows" ]; then
    source "$VENV_ACTIVATE"
else
    source "$VENV_ACTIVATE"
fi
if [ -n "$PIP_MIRROR" ]; then
    pip install -r requirements.txt -q -i "$PIP_MIRROR"
else
    pip install -r requirements.txt -q
fi

# ── 配置文件 ──
if [ ! -f ".env" ]; then
    echo -e "${GREEN}[3/5] 创建 .env 配置文件...${NC}"
    cp .env.example .env
else
    echo -e "${GREEN}[3/5] .env 已存在，跳过${NC}"
fi

# ── 创建数据目录 ──
mkdir -p data/logs data/sessions data/memory

# ── 前端构建 ──
echo -e "${GREEN}[4/5] 安装前端依赖...${NC}"
cd "$PROJECT_DIR/web"
if [ -n "$NPM_MIRROR" ]; then
    npm config set registry "$NPM_MIRROR"
fi
npm ci --silent 2>/dev/null || npm install --silent

echo -e "${GREEN}[5/5] 构建前端...${NC}"
npm run build

# ── 完成 ──
cd "$PROJECT_DIR"
echo ""
echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${GREEN}  构建完成！${NC}"
echo ""
echo "  启动方式："
echo "    ./start.sh          # 前后端一起启动"
echo "    ./run_backend.sh    # 仅后端 (端口从 .env 读取)"
echo "    ./run_frontend.sh   # 仅前端 (端口从 .env 读取)"
echo ""
echo "  前端访问地址在 .env 中配置"
echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
