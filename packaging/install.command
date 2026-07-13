#!/bin/bash
# ===========================================================================
# install.command — ZLink Agent 首次启动解锁脚本
#
# 作用: 去除 macOS Gatekeeper 给应用打的 quarantine 扩展属性
#       绕过 "ZLink Agent 已损坏，无法打开" 提示
#
# 用法:
#   - 双击本脚本（Finder 中双击 .command 即可触发）
#   - 或在终端执行: bash install.command
#
# 说明: 本脚本不需要 sudo 权限
# ===========================================================================

set -euo pipefail

APP_NAME="ZLink Agent.app"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

# 按优先级查找 app 位置
CANDIDATES=(
    "/Applications/${APP_NAME}"
    "${SCRIPT_DIR}/${APP_NAME}"
)

echo "╔══════════════════════════════════════════════╗"
echo "║  ZLink Agent 首次安装解锁                   ║"
echo "╚══════════════════════════════════════════════╝"
echo ""

# 查找 app
APP_PATH=""
for path in "${CANDIDATES[@]}"; do
    if [ -d "$path" ]; then
        APP_PATH="$path"
        break
    fi
done

if [ -z "$APP_PATH" ]; then
    echo "❌ 未找到 ${APP_NAME}"
    echo ""
    echo "请确认:"
    echo "  1. 如果你在 dmg 挂载窗口: 先把 ${APP_NAME}"
    echo "     拖到右侧的「应用程序」文件夹快捷方式"
    echo "  2. 拖完后再次双击本脚本"
    echo ""
    echo "已搜索的位置:"
    for path in "${CANDIDATES[@]}"; do
        echo "  - $path"
    done
    echo ""
    read -r -p "按回车键关闭此窗口..."
    exit 1
fi

echo "📍 找到应用: $APP_PATH"
echo "🔓 正在去除扩展属性和签名隔离..."
# 第一步: 去除所有扩展属性（包括 quarantine 和签名残留）
xattr -cr "$APP_PATH" 2>/dev/null || true
# 第二步: 确保 quarantine 属性也被清除
xattr -dr com.apple.quarantine "$APP_PATH" 2>/dev/null || true

echo ""
echo "✅ 完成！现在可以在 Finder 中双击 ${APP_NAME} 打开。"
echo ""
echo "💡 如果仍遇到问题，请在终端执行:"
echo "   xattr -cr '/Applications/${APP_NAME}'"
echo "   然后到「系统设置 → 隐私与安全性」点「仍要打开」"
echo ""

# 让 Terminal.app 窗口停留，便于新人看到结果
read -r -p "按回车键关闭此窗口..."
