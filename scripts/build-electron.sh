#!/bin/bash
# ===========================================================================
# build-electron.sh — ZLink Agent Electron 打包脚本（macOS + Windows）
#
# 用法（每次只构建一个平台；macOS 可指定芯片架构）：
#   bash scripts/build-electron.sh                默认 macOS arm64（Apple 芯片）
#   bash scripts/build-electron.sh --mac --arm64  macOS .dmg（M 芯片 / Apple Silicon）
#   bash scripts/build-electron.sh --mac --x64    macOS .dmg（Intel 芯片）
#   bash scripts/build-electron.sh --win          Windows .exe
#
# macOS Intel（x64）说明：
#   - PyInstaller 不能跨架构构建：后端必须用 x86_64 解释器建 .venv-x64 再打包。
#     本机（Apple Silicon）用 python.org universal2 框架版的 -intel64 切片，配合
#     Rosetta（arch -x86_64）运行；脚本首次跑 --mac --x64 时会自动创建 .venv-x64。
#     需要：已安装 Rosetta + 框架版 Python（含 /usr/local/bin/python3.x-intel64）。
#   - Electron 外壳由 electron-builder --x64 交叉打包（前端纯 JS，无架构绑定）。
#   - 因此 arm64 与 x64 需各跑一次构建（后端随架构重建），产物名带 -arm64 / -x64。
#
# 前置条件：
#   - Python 3.11+、Node.js 18+、npm
#   - Windows 主机：在 Git Bash (MINGW/MSYS) 中运行本脚本；PyInstaller 只能
#     原生构建，macOS 无法交叉编译 Windows 后端二进制
# ==========================================================================="

set -euo pipefail

# Electron 运行时默认从 GitHub 下载，国内容易停滞；npmmirror 镜像 121MB 约 10 秒。
# 已在国外网络环境可用 ELECTRON_MIRROR="" 显式覆盖回官方源。
export ELECTRON_MIRROR="${ELECTRON_MIRROR:-https://npmmirror.com/mirrors/electron/}"

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$(dirname "$0")/.."

PLATFORM=""
ARCH=""
for arg in "$@"; do
  case "$arg" in
    --mac)   PLATFORM="--mac" ;;
    --win)   PLATFORM="--win" ;;
    --arm64) ARCH="--arm64" ;;
    --x64)   ARCH="--x64" ;;
    *) echo "用法: $0 [--mac|--win] [--arm64|--x64]"; exit 1 ;;
  esac
done
[ -z "$PLATFORM" ] && PLATFORM="--mac"

IS_MAC_HOST=false
[[ "$(uname -s)" == "Darwin" ]] && IS_MAC_HOST=true
IS_WIN_HOST=false
[[ "$(uname -s)" =~ MINGW*|MSYS* ]] && IS_WIN_HOST=true

echo "╔══════════════════════════════════════════════╗"
echo "║     ZLink Agent 全自包含打包                  ║"
echo "║     目标平台: $PLATFORM${ARCH:+ ($ARCH)}"
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
    echo "⏭️  未找到 ${CHART_DIR}，跳过（Chart 功能将不可用）"
fi

echo ""
echo "[2/4] 打包 Python 后端 (PyInstaller)..."
BACKEND_DONE=false
if [[ "$PLATFORM" == "--mac" && "$IS_MAC_HOST" == "true" ]]; then
    if [[ "$ARCH" == "--x64" ]]; then
        echo "  ℹ️  构建 x64 (Intel) 后端：使用 .venv-x64（Rosetta x86_64）"
        X64_PY="/usr/local/bin/python3.14-intel64"
        if [ ! -x ".venv-x64/bin/python" ]; then
            if [ -x "$X64_PY" ]; then
                echo "  🔨 创建 x64 虚拟环境 .venv-x64（Rosetta x86_64）..."
                # 框架版 Python 的 sysconfig 平台为 macosx-10.15-universal2，
                # 会把 macosx_11_0+ 的 x86_64 wheel 判为不兼容而回退到 sdist（需 Rust 源码编译，
                # 且 cryptography 最新版无 cp314 x86_64 wheel）。用 MACOSX_DEPLOYMENT_TARGET
                # 抬版本让 pip 命中预编译 wheel，并 --only-binary=:all: 禁止源码构建
                # （cryptography 自动落到有 x86_64 wheel 的最高版本 48.x）。
                arch -x86_64 "$X64_PY" -m venv .venv-x64
                arch -x86_64 .venv-x64/bin/python -m pip install --upgrade pip --quiet
                MACOSX_DEPLOYMENT_TARGET=14.0 arch -x86_64 .venv-x64/bin/python -m pip install --only-binary=:all: --quiet -r requirements.txt
                arch -x86_64 .venv-x64/bin/python -m pip install --quiet pyinstaller
            else
                echo "  ❌ 未找到 Intel Python ($X64_PY)，无法构建 x64 后端" >&2
                echo "     需要 python.org universal2 框架版 Python（含 x86_64 切片）" >&2
                exit 1
            fi
        fi
        ZLINK_BUILD_VENV="$(pwd)/.venv-x64" arch -x86_64 bash scripts/build-pyinstaller.sh
        BACKEND_DONE=true
    else
        bash scripts/build-pyinstaller.sh
        BACKEND_DONE=true
    fi
elif $IS_WIN_HOST; then
    bash scripts/build-pyinstaller.sh
    BACKEND_DONE=true
elif [[ "$PLATFORM" == "--win" && "$IS_MAC_HOST" == "true" ]]; then
    echo "  ⚠️  macOS 上无法交叉编译 Windows PyInstaller 二进制。"
    echo "  ℹ️  请准备预编译的 dist/zlink-backend/ 目录（onedir 模式）后再运行此脚本。"
    echo "  ℹ️  或者在 Windows 主机上原生构建。"
fi

if $BACKEND_DONE; then
    echo "✅ PyInstaller 打包完成"
fi

echo ""
ARCH_FLAG="$ARCH"
if [[ "$PLATFORM" == "--mac" && -z "$ARCH_FLAG" ]]; then
    ARCH_FLAG="--arm64"
fi

if [[ "$PLATFORM" == *"--mac"* ]]; then
    # macOS 两阶段打包：先 --dir 出 .app → 在普通文件系统里做 ad-hoc 本地签名 →
    # 再 --prepackaged 从已签名的 .app 生成 DMG。
    # 为什么不能在 DMG 挂载卷里原地签：codesign 会报 "internal error in Code Signing
    # subsystem"，并留下“签名指示器存在但资源缺失”的包 —— 那正是别的 Mac 上报
    # “app is damaged”的形态，比不签名更糟。
    echo "[3/4] 打包 Electron 应用（阶段 1/2：--dir 出 .app）..."
    npx electron-builder --mac $ARCH_FLAG --dir --config electron-builder.yml
    APP_DIR="dist-electron/mac-arm64"
    [[ "$ARCH_FLAG" == "--x64" ]] && APP_DIR="dist-electron/mac"
    APP_BUNDLE="$(find "$APP_DIR" -maxdepth 1 -name '*.app' -print -quit)"
    if [ -z "$APP_BUNDLE" ]; then
        echo "❌ 阶段 1 没找到 .app（$APP_DIR）" >&2
        exit 1
    fi
    echo ""
    echo "  ✍ ad-hoc 本地签名: $APP_BUNDLE"
    codesign --force --deep --sign - "$APP_BUNDLE"
    codesign --verify --deep --strict --verbose=1 "$APP_BUNDLE" \
        && echo "     ✓ codesign --verify 通过"
    echo "     $(codesign -dvv "$APP_BUNDLE" 2>&1 | grep -E '^Identifier|^Signature' | tr '\n' ' ')"
    echo ""
    echo "[3/4] 打包 Electron 应用（阶段 2/2：从已签名 .app 生成 DMG）..."
    npx electron-builder --mac $ARCH_FLAG --prepackaged "$APP_DIR" --config electron-builder.yml
    echo "✅ Electron 打包完成"
else
    echo "[3/4] 打包 Electron 应用..."
    npx electron-builder $PLATFORM $ARCH_FLAG --config electron-builder.yml
    echo "✅ Electron 打包完成"
fi

if [[ "$PLATFORM" == *"--mac"* ]]; then
    echo ""
    echo "[3.5/4] 向 dmg 嵌入安装资源..."
    EMBED_FILES=()
    if [ -f "packaging/install.command" ]; then EMBED_FILES+=("packaging/install.command"); fi
    DMG_FOUND=false

    # 只处理本次新构建的 DMG（按 mtime 取最新）—— 之前写 dist-electron/*.dmg 会把
    # 历史版本的产品包一起重写（mtime 与内容都被覆盖），已发布产物不该被动。
    DMG_LATEST="$(ls -t dist-electron/*.dmg 2>/dev/null | head -1 || true)"
    if [ -n "$DMG_LATEST" ]; then
        dmg="$DMG_LATEST"
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

            # 嵌入安装资源（签名已在阶段 1.5 于普通目录里做过，这里不再动 bundle）
            if [ ${#EMBED_FILES[@]} -gt 0 ]; then
                for f in "${EMBED_FILES[@]}"; do
                    cp "$f" "$MNT/"
                    case "$f" in
                        *.sh|*.command) chmod +x "$MNT/$(basename "$f")" ;;
                    esac
                done
            fi

            hdiutil detach "$MNT" -quiet
            ATTACHED=false
            hdiutil convert "$RW" -format UDZO -o "$OUTPUT" > /dev/null
            mv "$OUTPUT" "$dmg"
        )
    fi

    if $DMG_FOUND; then
        EMBED_NAMES=""
        if [ ${#EMBED_FILES[@]} -gt 0 ]; then
            for f in "${EMBED_FILES[@]}"; do EMBED_NAMES+="$(basename "$f") "; done
        fi
        echo "✅ 已嵌入: ${EMBED_NAMES:-（无）}"
    else
        echo "⏭️  未找到 DMG，跳过嵌入与签名"
    fi
fi


echo ""
echo "[4/4] 清理临时文件..."
if [ -f "$(pwd)/.venv/Scripts/python.exe" ]; then
    CLEANUP_PYTHON="$(pwd)/.venv/Scripts/python.exe"
elif [ -f "$(pwd)/.venv/bin/python3" ]; then
    CLEANUP_PYTHON="$(pwd)/.venv/bin/python3"
else
    CLEANUP_PYTHON="python3"
fi
"$CLEANUP_PYTHON" -c "
import sys; sys.path.insert(0, 'scripts')  # cwd 已是项目根；$SCRIPT_DIR 在 Git Bash 下是 POSIX 路径，Windows Python 无法识别
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
