#!/bin/bash
# ===========================================================================
# bundle-python.sh — 打包自包含 Python 运行环境
#
# 在当前项目创建一个可移植的 Python 环境，包含所有依赖，
# 供 Electron 打包为 extraResources。
#
# 用法:
#   bash scripts/bundle-python.sh               构建 Python bundle
#   bash scripts/bundle-python.sh --python /path/to/python  指定 Python
#
# 输出: build/python-bundle/
#   ├── bin/python          ← 可执行 Python
#   ├── lib/python3.x/      ← 所有依赖
#   └── site-packages/      ← pip install 的包
# ===========================================================================

set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$PROJECT_DIR"

BUNDLE_DIR="build/python-bundle"
PYTHON_BIN=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --python) PYTHON_BIN="$2"; shift 2 ;;
    --help|-h)
      echo "用法: bash scripts/bundle-python.sh [--python /path/to/python]"
      exit 0 ;;
    *) echo "未知参数: $1"; exit 1 ;;
  esac
done

echo "╔══════════════════════════════════════════════╗"
echo "║     ZLink Agent Python Bundle                 ║"
echo "╚══════════════════════════════════════════════╝"

# ── 找 Python ────────────────────────────────────────────────────────
if [ -z "$PYTHON_BIN" ]; then
  for cmd in python3.14 python3.13 python3.12 python3.11 python3; do
    if command -v "$cmd" &>/dev/null; then
      PYTHON_BIN=$(command -v "$cmd")
      break
    fi
  done
fi

if [ -z "$PYTHON_BIN" ]; then
  echo "[ERROR] 未找到 Python 3.11+"
  exit 1
fi

PY_VER=$("$PYTHON_BIN" --version 2>&1)
echo "[1/3] 使用: $PY_VER ($PYTHON_BIN)"

# ── 清理旧的 bundle ──────────────────────────────────────────────────
rm -rf "$BUNDLE_DIR"
mkdir -p "$BUNDLE_DIR"

# ── 创建虚拟环境 ──────────────────────────────────────────────────────
echo "[2/3] 创建虚拟环境..."
"$PYTHON_BIN" -m venv "$BUNDLE_DIR"

# ── 安装依赖 ──────────────────────────────────────────────────────────
echo "[3/3] 安装依赖（复用 pip 缓存）..."
"$BUNDLE_DIR/bin/python" -m pip install --no-input --quiet --upgrade pip 2>/dev/null || true

# 安装项目自身（包含所有依赖）
"$BUNDLE_DIR/bin/python" -m pip install \
  --no-input --quiet \
  -r requirements.txt 2>&1 | tail -3

# 检查关键包
echo ""
echo "  验证安装:"
"$BUNDLE_DIR/bin/python" -c "
import fastapi, uvicorn, openai, anthropic, pydantic, httpx, oracledb, sqlparse, mcp
print('  ✅ 所有核心依赖已安装')
print(f'  Python: {__import__(\"sys\").version}')
" 2>&1 || echo "  ⚠️ 部分依赖缺失"

# ── 清理 bundle ──────────────────────────────────────────────────────
find "$BUNDLE_DIR" -name '__pycache__' -type d -exec rm -rf {} + 2>/dev/null || true
find "$BUNDLE_DIR" -name '*.pyc' -delete 2>/dev/null || true
# 移除可删除的文档和测试
rm -rf "$BUNDLE_DIR/lib/python3."*/test 2>/dev/null || true

# ── 统计大小 ──────────────────────────────────────────────────────────
SIZE=$(du -sh "$BUNDLE_DIR" 2>/dev/null | cut -f1)
echo ""
echo "✅ Python bundle 完成: $BUNDLE_DIR ($SIZE)"
echo "   路径: $BUNDLE_DIR/bin/python"
