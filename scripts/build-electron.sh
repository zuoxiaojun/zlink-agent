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

cd "$(dirname "$0")/.."

PLATFORM="${1:-}"
case "$PLATFORM" in
  --win)   PLATFORM="--win" ;;
  --mac)   PLATFORM="--mac" ;;
  "")      PLATFORM="--mac" ;;
  *) echo "用法: $0 [--mac|--win]"; exit 1 ;;
esac

echo "╔══════════════════════════════════════════════╗"
echo "║     ZLink Agent 全自包含打包                  ║"
echo "║     平台: $PLATFORM"
echo "╚══════════════════════════════════════════════╝"

echo ""
echo "[1/4] 构建前端..."
cd web && npm ci && npm run build && cd ..
echo "✅ 前端构建完成"

echo ""
echo "[2/4] 打包 Python 运行环境..."
bash scripts/bundle-python.sh
echo "✅ Python 环境打包完成"

echo ""
echo "[3/4] 打包 Electron 应用..."
npx electron-builder $PLATFORM --arm64 --config electron-builder.yml
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
rm -rf build/python-bundle
# 清理 .blockmap 增量文件（本应用不使用 auto-updater）
rm -f dist-electron/*.blockmap
# 清理 electron-builder 中间产物
rm -rf dist-electron/mac dist-electron/mac-arm64 dist-electron/win dist-electron/builder-debug.yml
echo "✅ 清理完成"
echo ""
echo "📦 成品位置: dist-electron/"
ls -lh dist-electron/*.dmg dist-electron/*.exe 2>/dev/null
