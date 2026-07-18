#!/bin/bash
# ===========================================================================
# build-electron.sh — ZLink Agent Electron 打包脚本（macOS + Windows）
#
# 用法：
#   bash scripts/build-electron.sh              默认 macOS
#   bash scripts/build-electron.sh --win        Windows .exe
#   bash scripts/build-electron.sh --mac --win  同时打包两个平台
#
# 前置条件：
#   - Python 3.11+、Node.js 18+、npm
#   - Windows 打包需要 wine（brew install wine）
# ===========================================================================

set -euo pipefail

# Electron 运行时默认从 GitHub 下载，国内容易停滞；npmmirror 镜像 121MB 约 10 秒。
# 已在国外网络环境可用 ELECTRON_MIRROR="" 显式覆盖回官方源。
export ELECTRON_MIRROR="${ELECTRON_MIRROR:-https://npmmirror.com/mirrors/electron/}"

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$(dirname "$0")/.."

PLATFORM="${1:-}"
case "$PLATFORM" in
  --win)   PLATFORM="--win" ;;
  --mac)   PLATFORM="--mac" ;;
  "")      PLATFORM="--mac" ;;
  *) echo "用法: $0 [--mac|--win]"; exit 1 ;;
esac

IS_MAC_HOST=false
[[ "$(uname -s)" == "Darwin" ]] && IS_MAC_HOST=true
IS_WIN_HOST=false
[[ "$(uname -s)" =~ MINGW*|MSYS* ]] && IS_WIN_HOST=true

echo "╔══════════════════════════════════════════════╗"
echo "║     ZLink Agent 全自包含打包                  ║"
echo "║     目标平台: $PLATFORM"
echo "║     构建主机: $(uname -s)"
echo "╚══════════════════════════════════════════════╝"

echo ""
echo "[1/4] 构建前端..."
cd web && npm install --prefer-offline && npm run build && cd ..
echo "✅ 前端构建完成"

echo ""
echo "[1.5/4] 安装 Chart MCP 运行时依赖（随包分发，新用户无需 node/npm）..."
CHART_DIR="node_modules/@antv/mcp-server-chart"
if [ -d "$CHART_DIR" ]; then
    # 装进包目录内的 node_modules，electron-builder extraResources 会一并拷贝
    # --ignore-scripts: 跳过 husky 等 dev 脚本（会失败并中断构建），build/ 已是预编译产物
    (cd "$CHART_DIR" && npm install --omit=dev --no-save --no-package-lock --ignore-scripts --silent)
    echo "✅ Chart MCP 依赖安装完成"
else
    echo "⏭️  未找到 $CHART_DIR，跳过（Chart 功能将不可用）"
fi

echo ""
echo "[2/4] 打包 Python 后端 (PyInstaller)..."
if $IS_WIN_HOST || [[ "$PLATFORM" == "--mac" && "$IS_MAC_HOST" == "true" ]]; then
    bash scripts/build-pyinstaller.sh
    echo "✅ PyInstaller 打包完成"
elif [[ "$PLATFORM" == "--win" && "$IS_MAC_HOST" == "true" ]]; then
    echo "  ⚠️  macOS 上无法交叉编译 Windows PyInstaller 二进制。"
    echo "  ℹ️  请准备预编译的 dist/zlink-backend.exe 后再运行此脚本。"
    echo "  ℹ️  或者在 Windows 主机上原生构建。"
fi

echo ""
ARCH_FLAG=""
[[ "$PLATFORM" == "--mac" ]] && ARCH_FLAG="--arm64"
echo "[3/4] 打包 Electron 应用..."
npx electron-builder $PLATFORM $ARCH_FLAG --config electron-builder.yml
echo "✅ Electron 打包完成"

if [[ "$PLATFORM" == *"--mac"* ]]; then
    echo ""
    echo "[3.5/4] 把安装资源嵌入 dmg..."
    EMBED_FILES=()
    [ -f "packaging/install.command" ] && EMBED_FILES+=("packaging/install.command")
    DMG_FOUND=false

    if [ ${#EMBED_FILES[@]} -gt 0 ]; then
        for dmg in dist-electron/*.dmg; do
            [ -f "$dmg" ] || continue
            DMG_FOUND=true
            echo "  → $dmg"
            (
                WORK_DIR=$(mktemp -d)
                RW="$WORK_DIR/source-rw.dmg"
                MNT="$WORK_DIR/mount"
                OUTPUT="$WORK_DIR/output.dmg"
                ATTACHED=false
                mkdir -p "$MNT"

                cleanup_dmg() {
                    if $ATTACHED; then
                        hdiutil detach "$MNT" -quiet 2>/dev/null \
                            || hdiutil detach "$MNT" -force -quiet 2>/dev/null \
                            || true
                    fi
                    rm -rf "$WORK_DIR"
                }
                trap cleanup_dmg EXIT

                hdiutil convert "$dmg" -format UDRW -o "$RW" > /dev/null
                hdiutil attach "$RW" -mountpoint "$MNT" -nobrowse -quiet
                ATTACHED=true
                for f in "${EMBED_FILES[@]}"; do
                    cp "$f" "$MNT/"
                    [[ "$f" == *.sh || "$f" == *.command ]] \
                        && chmod +x "$MNT/$(basename "$f")"
                done
                hdiutil detach "$MNT" -quiet
                ATTACHED=false
                hdiutil convert "$RW" -format UDZO -o "$OUTPUT" > /dev/null
                mv "$OUTPUT" "$dmg"
            )
        done
    fi

    if $DMG_FOUND; then
        EMBED_NAMES=""
        for f in "${EMBED_FILES[@]}"; do EMBED_NAMES+="$(basename "$f") "; done
        echo "✅ 已嵌入: $EMBED_NAMES"
    else
        echo "⏭️  未找到 DMG 或嵌入文件，跳过"
    fi
fi


echo ""
echo "[4/4] 清理临时文件..."
python3 -c "
import sys; sys.path.insert(0, '$SCRIPT_DIR')
from build_utils import remove_paths
import glob
for f in glob.glob('dist-electron/*.blockmap'):
    remove_paths(f)
remove_paths(
    'dist-electron/mac',
    'dist-electron/mac-arm64',
    'dist-electron/win',
    'dist-electron/builder-debug.yml',
)
"
echo "✅ 清理完成"
echo ""
echo "📦 成品位置: dist-electron/"
ls -lh dist-electron/*.dmg dist-electron/*.exe 2>/dev/null || true
