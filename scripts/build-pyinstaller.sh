#!/bin/bash
# build-pyinstaller.sh — PyInstaller 打包 ZLink Agent Python 后端
#
# 用法:
#   bash scripts/build-pyinstaller.sh            # 打包为单文件
#   bash scripts/build-pyinstaller.sh --onedir   # 打包为单目录（调试用）
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$(dirname "$0")/.."

MODE="${1:---onefile}"
PLATFORM_TAG=""
case "$(uname -s)" in
  Darwin) PLATFORM_TAG="macos-$(uname -m)" ;;
  Linux)  PLATFORM_TAG="linux-$(uname -m)" ;;
  MINGW*|MSYS*) PLATFORM_TAG="win" ;;
esac

echo "╔══════════════════════════════════════════════╗"
echo "║     PyInstaller 打包 ZLink 后端              ║"
echo "║     模式: $MODE"
echo "║     平台: $PLATFORM_TAG"
echo "╚══════════════════════════════════════════════╝"

# 使用项目自带的虚拟环境（干净 venv，不含 torch/pandas 等无关大包）
# Windows venv 结构是 .venv/Scripts/python.exe，macOS/Linux 是 .venv/bin/python3
if [ -f "$(pwd)/.venv/Scripts/python.exe" ]; then
    VENV_PYTHON="$(pwd)/.venv/Scripts/python.exe"
elif [ -f "$(pwd)/.venv/bin/python3" ]; then
    VENV_PYTHON="$(pwd)/.venv/bin/python3"
else
    echo "❌ 未找到项目虚拟环境"
    echo "   Windows: $(pwd)/.venv/Scripts/python.exe"
    echo "   macOS/Linux: $(pwd)/.venv/bin/python3"
    echo "   请先运行: python3 -m venv .venv && source .venv/bin/activate && pip install -e ."
    exit 1
fi

PYTHON="$VENV_PYTHON"

# 确保 venv 里有 pyinstaller
if ! "$PYTHON" -c "import PyInstaller" 2>/dev/null; then
    echo "安装 PyInstaller 到项目 venv..."
    "$PYTHON" -m pip install pyinstaller --quiet
fi

# ── 动态导入扫描提醒 ─────────────────────────────────────────────
echo ""
echo "▶ 扫描代码中的动态导入..."
if ! "$PYTHON" scripts/check_dynamic_imports.py > /dev/null 2>&1; then
    echo "⚠️  发现未覆盖的动态导入，请运行以下命令查看："
    echo "   $PYTHON scripts/check_dynamic_imports.py --verbose"
    echo ""
fi

echo ""
echo "▶ 打包中..."

# --add-data separator: macOS/Linux use ":", Windows uses ";"
if [[ "$(uname -s)" =~ MINGW*|MSYS* ]]; then
    ADD_DATA_SEP=";"
else
    ADD_DATA_SEP=":"
fi

# 从集中清单生成 --hidden-import 参数（去除 Windows 换行符 \r）
HIDDEN_IMPORT_ARGS=()
while IFS= read -r module; do
    module="${module%$'\r'}"
    [ -n "$module" ] && HIDDEN_IMPORT_ARGS+=("--hidden-import" "$module")
done < <("$PYTHON" scripts/pyinstaller_hidden_imports.py)

"$PYTHON" -m PyInstaller \
    --clean \
    --noconfirm \
    --paths . \
    $MODE \
    --name zlink-backend \
    --add-data "agent/skills${ADD_DATA_SEP}agent/skills" \
    --add-data "pyproject.toml${ADD_DATA_SEP}." \
    --hidden-import backend.main \
    "${HIDDEN_IMPORT_ARGS[@]}" \
    backend/pyinstaller_entry.py

echo ""
echo "✅ PyInstaller 打包完成"
ls -lh dist/zlink-backend*

# ── 冒烟测试 ─────────────────────────────────────────────────────
echo ""
echo "▶ 冒烟测试..."

# 启动新打包的后端
if [[ "$(uname -s)" =~ MINGW*|MSYS* ]]; then
    EXE_PATH="dist/zlink-backend.exe"
else
    EXE_PATH="dist/zlink-backend"
fi

if [ ! -f "$EXE_PATH" ]; then
    echo "❌ 未找到打包产物: $EXE_PATH"
    exit 1
fi

# 选择测试端口，避免与运行中的服务冲突
TEST_PORT=18089
export ZLINK_AGENT_PORT="$TEST_PORT"

# 后台启动
"$EXE_PATH" &
TEST_PID=$!
echo "   测试后端 PID: $TEST_PID (端口: $TEST_PORT)"

# 等待启动（onefile 自解压冷启动可达 20 秒，留足余量）
for i in {1..45}; do
    if curl -s "http://127.0.0.1:${TEST_PORT}/api/system/version" > /dev/null 2>&1; then
        break
    fi
    sleep 1
done

# 检查是否启动成功
if ! curl -s "http://127.0.0.1:${TEST_PORT}/api/system/version" > /dev/null 2>&1; then
    echo "❌ 冒烟测试失败：后端未在 45 秒内启动"
    kill "$TEST_PID" 2>/dev/null || true
    exit 1
fi

# 验证关键接口
echo "   ✓ /api/system/version 响应正常"

# 检查工具注册（确认 agent 模块加载成功）
TOOLS_COUNT=$(curl -s "http://127.0.0.1:${TEST_PORT}/api/tools" | "$PYTHON" -c "import json,sys; print(len(json.load(sys.stdin)))")
if [ "$TOOLS_COUNT" -lt 50 ]; then
    echo "❌ 冒烟测试失败：工具注册数量异常 ($TOOLS_COUNT)"
    kill "$TEST_PID" 2>/dev/null || true
    exit 1
fi
echo "   ✓ 工具注册正常 ($TOOLS_COUNT 个)"

# 验证 NC 工具（确认 oracledb + cryptography 打包成功）
if ! curl -s "http://127.0.0.1:${TEST_PORT}/api/tools" | grep -q "nc_query"; then
    echo "❌ 冒烟测试失败：NC 工具未注册"
    kill "$TEST_PID" 2>/dev/null || true
    exit 1
fi
echo "   ✓ NC 工具注册正常"

# 清理
kill "$TEST_PID" 2>/dev/null || true
sleep 1

echo ""
echo "✅ 冒烟测试通过"
