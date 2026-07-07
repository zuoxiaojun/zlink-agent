#!/usr/bin/env bash
# ===========================================================================
# build-app.sh — YS-Agent 桌面应用打包脚本
#
# 用法：
#   bash scripts/build-app.sh                 默认打包（macOS / Linux）
#   bash scripts/build-app.sh --os windows    打包 Windows 版本
#   bash scripts/build-app.sh --no-frontend   跳过前端构建（已 build 过）
#   bash scripts/build-app.sh --debug         PyInstaller debug 模式
#
# 输出：dist/YS-Agent/
#   ├── ys-agent              ← 双击启动的服务端可执行文件
#   ├── _internal/            ← 所有依赖
#   └── web/dist/             ← 前端静态文件（由 spec 复制）
#
# 前置条件：
#   - Python >= 3.11 + 虚拟环境已激活
#   - Node.js >= 18 + npm
#   - pip install pyinstaller
# ===========================================================================

set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

info()  { echo -e "${CYAN}[INFO]${NC}  $*"; }
ok()    { echo -e "${GREEN}[OK]${NC}    $*"; }
warn()  { echo -e "${YELLOW}[WARN]${NC}  $*"; }
err()   { echo -e "${RED}[ERROR]${NC} $*"; }

# ── 项目根目录 ──────────────────────────────────────────────────────────
PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$PROJECT_DIR"

# ── 参数解析 ──────────────────────────────────────────────────────────────
BUILD_FRONTEND=true
BUILD_DMG=false
DEBUG_MODE=""
TARGET_OS=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    --no-frontend) BUILD_FRONTEND=false; shift ;;
    --dmg)         BUILD_DMG=true; shift ;;
    --debug)       DEBUG_MODE="--debug"; shift ;;
    --os)          TARGET_OS="$2"; shift 2 ;;
    --help|-h)
      echo "用法: bash scripts/build-app.sh [选项]"
      echo ""
      echo "选项:"
      echo "  --no-frontend     跳过前端构建（如果 web/dist/ 已经存在）"
      echo "  --dmg             额外生成 macOS DMG 安装包（仅 macOS）"
      echo "  --debug           PyInstaller debug 模式（生成更多日志）"
      echo "  --os <系统>       目标系统: macos / linux / windows（默认: 当前系统）"
      echo "  --help           显示此帮助"
      exit 0
      ;;
    *) err "未知参数: $1"; exit 1 ;;
  esac
done

# ── 系统检测 ────────────────────────────────────────────────────────────
if [ -z "$TARGET_OS" ]; then
  case "$(uname -s)" in
    Darwin)  TARGET_OS="macos" ;;
    Linux)   TARGET_OS="linux" ;;
    MINGW*|MSYS*|CYGWIN*) TARGET_OS="windows" ;;
    *)       err "未知系统: $(uname -s)"; exit 1 ;;
  esac
fi

info "目标系统: $TARGET_OS"
echo ""

# ── 1. 检查依赖 ──────────────────────────────────────────────────────────
info "[1/4] 检查依赖..."

if ! command -v python3 &>/dev/null && ! command -v python &>/dev/null; then
  err "需要 Python >= 3.11"
  exit 1
fi

PY_CMD="python3"
if ! command -v python3 &>/dev/null; then
  PY_CMD="python"
fi

PY_VER=$($PY_CMD --version 2>&1 | awk '{print $2}')
info "  Python: $PY_VER"

if ! $PY_CMD -c "import PyInstaller" 2>/dev/null; then
  err "需要 PyInstaller，请安装: pip install pyinstaller"
  exit 1
fi

PYI_VER=$($PY_CMD -c "import PyInstaller; print(PyInstaller.__version__)" 2>/dev/null || echo "?")
info "  PyInstaller: $PYI_VER"

if command -v node &>/dev/null; then
  info "  Node.js: $(node --version)"
else
  warn "  Node.js 未安装 — 如有前端构建需求请先安装"
fi

echo ""

# ── 2. 构建前端 ──────────────────────────────────────────────────────────
if $BUILD_FRONTEND; then
  info "[2/4] 构建前端..."

  if [ ! -d "web/node_modules" ]; then
    info "  安装前端依赖..."
    cd web && npm ci --silent 2>/dev/null || npm install --silent
    cd "$PROJECT_DIR"
  fi

  cd web && npm run build
  cd "$PROJECT_DIR"
  ok "前端构建完成: web/dist/"
else
  info "[2/4] 跳过前端构建（--no-frontend）"
fi

# 确认前端构建产物存在
if [ ! -d "web/dist" ]; then
  err "web/dist/ 不存在！请先构建前端或去掉 --no-frontend"
  exit 1
fi
echo ""

# ── 3. 激活虚拟环境（如果有） ──────────────────────────────────────────
info "[3/5] 准备 Python 环境..."
if [ -f ".venv/bin/activate" ]; then
  PYTHONPATH="" source ".venv/bin/activate"
  ok "虚拟环境已激活: .venv"
else
  warn "未找到 .venv，使用系统 Python 环境"
fi
echo ""

# ── 4. 预缓存 MCP 依赖 ──────────────────────────────────────────────────
info "[4/5] 预缓存 MCP 依赖..."

# 预缓存 chart MCP 的 npx 包，避免用户首次启动等待下载
if command -v npx &>/dev/null; then
  info "  缓存 mcp-server-chart (npx)..."
  npx --prefer-offline -y @antv/mcp-server-chart --version &>/dev/null || \
  npx -y @antv/mcp-server-chart --version &>/dev/null && \
  ok "  mcp-server-chart 已缓存"
else
  warn "  npx 未安装，跳过缓存（chart MCP 启动时可能稍慢）"
fi
echo ""

# ── 5. 运行 PyInstaller（隔离环境，排除 Hermes 等外部 PYTHONPATH 污染） ──
info "[5/5] 运行 PyInstaller 打包..."

# 清理之前的构建
rm -rf dist/YS-Agent build/

# 用隔离环境运行（unset PYTHONPATH 避免混入其他 venv 的二进制）
PYTHONPATH="" $PY_CMD -m PyInstaller \
  packaging/ys-agent.spec \
  --clean \
  --noconfirm \
  $DEBUG_MODE

echo ""

# ── 完成 ────────────────────────────────────────────────────────────────
if [ -f "dist/YS-Agent/ys-agent" ] || [ -f "dist/YS-Agent/ys-agent.exe" ]; then
  EXE_PATH="dist/YS-Agent/ys-agent"
  [ "$TARGET_OS" = "windows" ] && EXE_PATH="dist/YS-Agent/ys-agent.exe"

  APP_SIZE=$(du -sh "dist/YS-Agent" 2>/dev/null | awk '{print $1}')

  # ── macOS: 自动生成 .app 包装 ────────────────────────────────────────
  if [ "$TARGET_OS" = "macos" ]; then
    APP_BUNDLE="dist/YS-Agent.app"
    info "[+] 生成 macOS .app 应用包..."

    rm -rf "$APP_BUNDLE"
    mkdir -p "$APP_BUNDLE/Contents/MacOS"
    mkdir -p "$APP_BUNDLE/Contents/Resources"

    # 把 onedir 输出整体放进 Resources/（二进制 + _internal/ 一起）
    cp -r dist/YS-Agent/* "$APP_BUNDLE/Contents/Resources/"

    # 创建启动脚本 — 用 osascript 弹一个终端窗口显示服务日志
    cat > "$APP_BUNDLE/Contents/MacOS/YS-Agent" << 'LAUNCHER'
#!/bin/bash
# YS-Agent macOS launcher — opens a Terminal window with server logs
DIR="$(cd "$(dirname "$0")/../Resources" && pwd)"
cd "$DIR" || exit 1

# 检查是否已有实例在运行
if curl -sf http://127.0.0.1:8089/api/config >/dev/null 2>&1; then
  osascript -e "tell application \"Terminal\" to do script \"echo '━━━ YS-Agent 已在运行 ━━━' && echo '访问地址: http://127.0.0.1:8089' && read -p '按回车关闭'\""
  open http://127.0.0.1:8089
  exit 0
fi

# 在独立终端窗口里启动服务
osascript -e "tell application \"Terminal\" to do script \"cd '$DIR' && clear && \\
echo '━━━ YS-Agent 启动中 ━━━' && \\
echo '数据目录: ~/.ys-agent/data/' && \\
echo '访问地址: http://127.0.0.1:8089' && \\
echo '按 Ctrl+C 停止服务' && \\
echo '' && \\
./ys-agent; \\
echo ''; \\
echo '服务已停止，此窗口将自动关闭...'; \\
sleep 3\"" &

# 等服务就绪后自动打开浏览器
for i in $(seq 1 20); do
  if curl -sf http://127.0.0.1:8089/api/config >/dev/null 2>&1; then
    break
  fi
  sleep 0.3
done
open http://127.0.0.1:8089
LAUNCHER
    chmod +x "$APP_BUNDLE/Contents/MacOS/YS-Agent"

    # 创建 Info.plist
    cat > "$APP_BUNDLE/Contents/Info.plist" << 'PLIST'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>CFBundleDevelopmentRegion</key>
  <string>zh_CN</string>
  <key>CFBundleDisplayName</key>
  <string>YS-Agent</string>
  <key>CFBundleExecutable</key>
  <string>YS-Agent</string>
  <key>CFBundleIdentifier</key>
  <string>com.yousuite.ys-agent</string>
  <key>CFBundleInfoDictionaryVersion</key>
  <string>6.0</string>
  <key>CFBundleName</key>
  <string>YS-Agent</string>
  <key>CFBundlePackageType</key>
  <string>APPL</string>
  <key>CFBundleShortVersionString</key>
  <string>1.3.0</string>
  <key>CFBundleVersion</key>
  <string>1.3.0</string>
  <key>LSMinimumSystemVersion</key>
  <string>10.15</string>
  <key>NSHighResolutionCapable</key>
  <true/>
  <key>NSHumanReadableCopyright</key>
  <string>Copyright © 2026 YS-Agent.</string>
</dict>
</plist>
PLIST

    # 复制图标
    if [ -f "packaging/app.icns" ]; then
      cp packaging/app.icns "$APP_BUNDLE/Contents/Resources/app.icns"
    fi

    # ── DMG 安装包（--dmg 时） ──────────────────────────────────────────
    DMG_PATH=""
    if $BUILD_DMG; then
      VERSION=$(cat VERSION 2>/dev/null || echo "1.3.0")
      DMG_NAME="YS-Agent ${VERSION}.dmg"
      DMG_PATH="dist/${DMG_NAME}"

      info "[+] 生成 DMG 安装包..."

      if create-dmg --overwrite --no-code-sign "$APP_BUNDLE" "dist/" 2>/dev/null; then
        # find the generated DMG (create-dmg auto-names it)
        DMG_PATH=$(ls -t dist/*.dmg 2>/dev/null | head -1)
        if [ -n "$DMG_PATH" ] && [ -f "$DMG_PATH" ]; then
          DMG_SIZE=$(du -sh "$DMG_PATH" 2>/dev/null | awk '{print $1}')
          ok "DMG 安装包已生成: $(basename "$DMG_PATH") (${DMG_SIZE})"
        else
          warn "DMG 文件未找到，可能命名不同，请检查 dist/ 目录"
          BUILD_DMG=false
        fi
      else
        warn "DMG 生成失败，跳过"
        BUILD_DMG=false
      fi
    fi

    APP_BUNDLE_SIZE=$(du -sh "$APP_BUNDLE" 2>/dev/null | awk '{print $1}')

    echo ""
    echo -e "${CYAN}╔══════════════════════════════════════════════╗${NC}"
    echo -e "${CYAN}║     ✅ YS-Agent macOS 应用打包完成              ║${NC}"
    echo -e "${CYAN}╠══════════════════════════════════════════════╣${NC}"
    echo -e "${CYAN}║  应用包: dist/YS-Agent.app                    ║${NC}"
    if [ -n "$DMG_PATH" ] && [ -f "$DMG_PATH" ]; then
      echo -e "${CYAN}║  DMG:    ${DMG_PATH}  ║${NC}"
    fi
    echo -e "${CYAN}║  大小: ${APP_BUNDLE_SIZE}                              ║${NC}"
    echo -e "${CYAN}║  命令行版本: dist/YS-Agent/                    ║${NC}"
    echo -e "${CYAN}╚══════════════════════════════════════════════╝${NC}"
    echo ""
    info "双击 dist/YS-Agent.app 启动"
    if [ -n "$DMG_PATH" ] && [ -f "$DMG_PATH" ]; then
      info "DMG 安装包: open ${DMG_PATH}"
    fi
    info "或命令行: open dist/YS-Agent.app"
    info "首次启动会自动创建数据目录: ~/.ys-agent/data/"
    echo ""
  else
    # 非 macOS 平台
    echo ""
    echo -e "${CYAN}╔══════════════════════════════════════════════╗${NC}"
    echo -e "${CYAN}║     ✅ YS-Agent 打包完成                       ║${NC}"
    echo -e "${CYAN}╠══════════════════════════════════════════════╣${NC}"
    echo -e "${CYAN}║  输出: dist/YS-Agent/                         ║${NC}"
    echo -e "${CYAN}║  入口: ${EXE_PATH}${NC}"
    echo -e "${CYAN}║  大小: ${APP_SIZE}                              ║${NC}"
    echo -e "${CYAN}╚══════════════════════════════════════════════╝${NC}"
    echo ""
    info "启动方式:"
    echo "    ${EXE_PATH}"
    echo ""
  fi
else
  err "打包失败 — dist/YS-Agent/ys-agent 未生成"
  exit 1
fi
