#!/bin/bash
# ===========================================================================
# setup.sh — ZLink Agent 一键安装部署脚本
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
#   7. 安装 zlink 快捷命令
#   8. 执行数据迁移
#
# 环境变量（镜像加速）：
#   ZLINK_USE_MIRROR=true          是否使用国内镜像（默认 true）
#   ZLINK_PIP_MIRROR=...           PyPI 镜像地址
#   ZLINK_NPM_MIRROR=...           npm 镜像地址
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
echo -e "${CYAN}║     ZLink Agent 安装部署                        ║${NC}"
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
    warn "未找到 git，无法使用升级功能（zlink update）"
fi

# ── Mac 专属前置检查 (其他平台跳过) ─────────────────────────────────────
if [ "$OS" = "macos" ]; then
    # Homebrew 检测 (可选, 仅作提示)
    if ! command -v brew &>/dev/null; then
        info "Homebrew 未装 (可选, 装 Python/Node 不是必需的)"
        info "  方案 A — 手动装 (无需 Homebrew):"
        info "    Python 3.11+: https://www.python.org/downloads/macos/"
        info "    Node.js 18+:  https://nodejs.org/en/download"
        info "  方案 B — 装 Homebrew 后用 brew:"
        info "    /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)""
    else
        ok "Homebrew: $(brew --version | head -1) (可选)"
    fi

    # Xcode Command Line Tools 检测 (强失败, pip 装包会卡)
    if ! command -v xcode-select &>/dev/null || ! xcode-select -p &>/dev/null 2>&1; then
        err "Xcode Command Line Tools 未装"
        err "  cryptography / pydantic-core 等需要它编译本地扩展"
        err "  修复: xcode-select --install"
        err "  跳过此检查: XCODE_CLT_SKIP=1 bash setup.sh"
        if [ "${XCODE_CLT_SKIP:-}" != "1" ]; then
            exit 1
        else
            warn "XCODE_CLT_SKIP=1 已设置, 跳过 (后续装包可能失败)"
        fi
    else
        ok "Xcode CLT: $(xcode-select -p)"
    fi
fi

echo ""

# ── 2. 镜像配置 ─────────────────────────────────────────────────────────────
echo -e "${GREEN}[2/8] 配置镜像源...${NC}"
USE_MIRROR="${ZLINK_USE_MIRROR:-true}"
NPM_MIRROR="${ZLINK_NPM_MIRROR:-https://mirrors.npmmirror.com}"
# PyPI 镜像回退链：按优先级逐个尝试，首个成功即用，全部失败才报错
PIP_MIRRORS=(
    "https://mirrors.tuna.tsinghua.edu.cn/pypi/web/simple"
    "https://mirrors.aliyun.com/pypi/simple"
    "https://mirrors.cloud.tencent.com/pypi/simple"
    "https://pypi.org/simple"
)
if [ "$USE_MIRROR" = "true" ]; then
    if [ -n "${ZLINK_PIP_MIRROR:-}" ]; then
        # 用户指定了单一镜像，禁用回退
        PIP_MIRRORS=("$ZLINK_PIP_MIRROR")
        echo "  PIP: $ZLINK_PIP_MIRROR (用户指定, 无回退)"
    else
        echo "  PIP 镜像回退链 (按优先级):"
        for m in "${PIP_MIRRORS[@]}"; do echo "    - $m"; done
    fi
    echo "  NPM: $NPM_MIRROR"
else
    PIP_MIRRORS=()
    echo "  不使用镜像源 (走 PyPI 官方)"
fi
echo ""

# ── 2b. pip 安装辅助函数 (镜像回退 + 错误可见) ───────────────────────────
# 用法: pip_install_robust -r requirements.txt
#      pip_install_robust -e ".[all]"
#      pip_install_robust --upgrade pip
# 返回: 0=成功, 1=全部失败
pip_install_robust() {
    set +e
    if [ ${#PIP_MIRRORS[@]} -eq 0 ]; then
        info "  尝试 PyPI 官方源"
        if pip install --retries 1 --timeout 15 "$@"; then
            set -e
            return 0
        fi
        warn "  PyPI 官方源失败"
        set -e
        return 1
    fi
    for mirror in "${PIP_MIRRORS[@]}"; do
        info "  尝试镜像: $mirror"
        if pip install --retries 1 --timeout 15 -i "$mirror" "$@"; then
            ok "  镜像 $mirror 安装成功"
            set -e
            return 0
        fi
        warn "  镜像 $mirror 失败, 尝试下一个..."
    done
    set -e
    err "  所有 PyPI 镜像均不可用，请检查网络"
    err "  提示: ZLINK_USE_MIRROR=false 走官方, 或 ZLINK_PIP_MIRROR=<URL> 指定单一镜像"
    return 1
}

# ── 3. Python 虚拟环境 ──────────────────────────────────────────────────────
echo -e "${GREEN}[3/8] 创建 Python 虚拟环境...${NC}"
if [ ! -d ".venv" ]; then
    if ! $PY_CMD -m venv .venv 2>&1; then
        err "虚拟环境创建失败"
        case "$OS" in
            linux)
                err "Debian/Ubuntu 通常需要: sudo apt install python3-venv python3-pip"
                err "Fedora: sudo dnf install python3-virtualenv"
                ;;
            macos)
                err "macOS: brew install python (或 python@3.12)"
                ;;
            windows)
                err "Windows 安装 Python 时勾选 'tcl/tk and IDLE' 和 'Add to PATH'"
                ;;
        esac
        exit 1
    fi
    ok "虚拟环境已创建"
else
    info "虚拟环境已存在，跳过"
fi
# 验证 venv 里的 pip 可用 (Debian 上 python3-venv 未装时 venv 会建成功但 pip 缺失)
if [ "$OS" = "windows" ]; then
    if ! .venv/Scripts/python.exe -m pip --version >/dev/null 2>&1; then
        err "虚拟环境创建成功但 pip 不可用"
        err "重装 Python 时勾选 pip, 或: python -m ensurepip --upgrade"
        exit 1
    fi
else
    if ! .venv/bin/python -m pip --version >/dev/null 2>&1; then
        err "虚拟环境创建成功但 pip 不可用"
        err "Debian/Ubuntu: sudo apt install python3-venv"
        err "或手动引导: .venv/bin/python -m ensurepip --upgrade"
        exit 1
    fi
fi
ok "venv pip 就绪"
echo ""

# ── 4. 安装 Python 依赖 ────────────────────────────────────────────────────
echo -e "${GREEN}[4/8] 安装 Python 依赖...${NC}"
PYTHONPATH="" source "$VENV_ACTIVATE"

# 升级 pip 自身 (失败可容忍, 旧 pip 也能装包)
info "升级 pip..."
pip_install_robust --upgrade pip || warn "pip 升级失败, 继续用现有版本"

# 安装项目依赖 (requirements.txt -> pyproject.toml 单一源)
info "安装项目依赖..."
if ! pip_install_robust -r requirements.txt; then
    err "Python 依赖安装失败"
    err "请检查上方 pip 错误信息, 修复后重新运行本脚本"
    exit 1
fi

# 验证依赖图一致性
info "验证依赖图 (pip check)..."
if pip check 2>&1; then
    ok "依赖图一致"
else
    warn "依赖图存在冲突, 但通常不影响运行。可手动查看: .venv/bin/pip check"
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

LAUNCHER_SRC="$PROJECT_DIR/scripts/zlink.sh"
LAUNCHER_DST="$INSTALL_DIR/zlink"
# (ys-agent 兼容 shim 已在 v1.5.3 移除 — 全新项目不保留任何命名兼容)

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
    echo -e "${CYAN}║     ✅ ZLink Agent 升级完成                      ║${NC}"
    echo -e "${CYAN}╠══════════════════════════════════════════════╣${NC}"
    echo -e "${CYAN}║  安装路径: $PROJECT_DIR${NC}"
    echo -e "${CYAN}║  用户数据: 已保留                             ║${NC}"
    echo -e "${CYAN}╚══════════════════════════════════════════════╝${NC}"
    echo ""
    echo "  升级完成，请重启后端：zlink stop && zlink"
else
    echo -e "${CYAN}╔══════════════════════════════════════════════╗${NC}"
    echo -e "${CYAN}║     ✅ ZLink Agent 安装完成                      ║${NC}"
    echo -e "${CYAN}╠══════════════════════════════════════════════╣${NC}"
    echo -e "${CYAN}║  安装路径: $PROJECT_DIR${NC}"
    echo -e "${CYAN}║  快捷命令: zlink                           ║${NC}"
    echo -e "${CYAN}║  数据目录: $PROJECT_DIR/data/${NC}"
    echo -e "${CYAN}╚══════════════════════════════════════════════╝${NC}"
fi
echo ""
echo "  启动方式："
echo ""
echo "    zlink                    启动后端（浏览器访问 http://localhost:8089）"
    echo "    zlink update          升级到最新版本"
    echo "    zlink stop               停止服务"
echo "    zlink --help             查看全部命令"
echo ""
echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
