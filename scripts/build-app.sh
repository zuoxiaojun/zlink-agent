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

# ── 4. 预缓存 MCP 依赖 (可选, 仅当 Node.js 可用时执行) ───────────────
# v1.3.1+ chart MCP 不再内置, 用户通过 MCP 管理页自装 @antv/mcp-server-chart
# 构建时若本机有 npx, 顺便预缓存, 加速用户首次启动
if command -v npx &>/dev/null; then
  info "[4/5] 预缓存 chart MCP (npx, 可选)..."
  npx --prefer-offline -y @antv/mcp-server-chart --version &>/dev/null || \
  npx -y @antv/mcp-server-chart --version &>/dev/null && \
  ok "  mcp-server-chart 已缓存" || \
  warn "  mcp-server-chart 缓存失败 (不影响构建)"
else
  info "[4/5] 跳过 chart MCP 预缓存 (本机无 npx, 用户自装时再下)"
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


# v1.4.0: 数据目录统一为 ~/.ys-agent/data,源码与 .app 行为一致。
# 这里仅显示一行提示,真实路径由 backend/main.py 启动时打印。
DATA_DIR_DISPLAY="~/.ys-agent/data (源码与 .app 共享)"

# 在独立终端窗口里启动服务
osascript -e "tell application \"Terminal\" to do script \"cd '$DIR' && clear && \\
echo '━━━ YS-Agent 启动中 ━━━' && \\
echo '数据目录: $DATA_DIR_DISPLAY' && \\
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

    # 创建 Info.plist (版本号从 VERSION 文件动态读, 避免硬编码过期)
    PLIST_VERSION=$(cat VERSION 2>/dev/null || echo "0.0.0")
    cat > "$APP_BUNDLE/Contents/Info.plist" << PLIST
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
  <key>CFBundleIconFile</key>
  <string>app.icns</string>
  <key>CFBundleInfoDictionaryVersion</key>
  <string>6.0</string>
  <key>CFBundleName</key>
  <string>YS-Agent</string>
  <key>CFBundlePackageType</key>
  <string>APPL</string>
  <key>CFBundleShortVersionString</key>
  <string>${PLIST_VERSION}</string>
  <key>CFBundleVersion</key>
  <string>${PLIST_VERSION}</string>
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

    # ad-hoc 签名 — 让自定义图标在 Finder 中显示，无开发者账号也能用
    info "[+] 签名 .app（ad-hoc）..."
    codesign --force --deep --sign - "$APP_BUNDLE" 2>/dev/null && ok "  签名完成" || warn "  签名失败（不影响运行）"

    # ── DMG 安装包（--dmg 时） ──────────────────────────────────────────
    # 用 hdiutil 而非 create-dmg, 因为我们想在 DMG 里同时放 .app + 说明文档
    # create-dmg 只接受单个 .app, 不支持 add-file 类选项
    DMG_PATH=""
    if $BUILD_DMG; then
      VERSION=$(cat VERSION 2>/dev/null || echo "1.3.1")
      DMG_PATH="dist/YS-Agent ${VERSION}.dmg"

      info "[+] 生成 DMG 安装包..."

      # staging 目录: 装 .app + 首次安装说明.txt + Applications 软链
      DMG_STAGE=$(mktemp -d)
      cp -R "$APP_BUNDLE" "$DMG_STAGE/"
      ln -s /Applications "$DMG_STAGE/Applications"
      cat > "$DMG_STAGE/首次安装说明.txt" << 'FIRST_RUN'
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  YS-Agent 首次安装说明 (macOS)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

1. 把 YS-Agent.app 拖到右边的 Applications 文件夹
2. 在 Applications 里找到 YS-Agent.app
3. 首次启动: 右键点击 → 选择"打开" (不是双击!)
   → 弹出确认框, 再点一次"打开"
4. 之后双击即可正常使用

为什么要右键打开?
  本 .app 用了 ad-hoc 签名 (无 Apple 开发者账号, 免费)
  macOS Gatekeeper 默认会拦截"未识别开发者"的 .app
  右键打开是 macOS 给非商店 App 的官方放行方式

不想右键? 也可以在终端跑:
  xattr -dr com.apple.quarantine /Applications/YS-Agent.app

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  访问地址: http://127.0.0.1:8089
  停止服务: 关闭启动时弹出的 Terminal 窗口即可
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
FIRST_RUN

      rm -f "$DMG_PATH"
      if hdiutil create -volname "YS-Agent ${VERSION}" \
              -srcfolder "$DMG_STAGE" \
              -ov -format UDZO \
              "$DMG_PATH" > /dev/null 2>&1; then
        rm -rf "$DMG_STAGE"
        DMG_SIZE=$(du -sh "$DMG_PATH" 2>/dev/null | awk '{print $1}')
        ok "DMG 安装包已生成: $(basename "$DMG_PATH") (${DMG_SIZE})"
      else
        warn "DMG 生成失败 (hdiutil 错误)"
        rm -rf "$DMG_STAGE"
        BUILD_DMG=false
        DMG_PATH=""
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
