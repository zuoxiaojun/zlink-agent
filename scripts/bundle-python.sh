#!/bin/bash
# ===========================================================================
# bundle-python.sh — 打包自包含 Python 运行环境
#
# 策略：创建空 venv + pip install（利用 pip 缓存，无需重新下载）。
# 只安装 requirements.txt 中的运行时依赖，不含 dev 包。
#
# 用法:
#   bash scripts/bundle-python.sh               构建 Python bundle
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
VENV_DIR="$PROJECT_DIR/.venv"

echo "╔══════════════════════════════════════════════╗"
echo "║     ZLink Agent Python Bundle                 ║"
echo "╚══════════════════════════════════════════════╝"

# ── 找 Python ────────────────────────────────────────────────────────
# 优先用 .venv 的 Python（版本确定一致，避免 Python 3.14/3.13 不一致）
if [ -f "$VENV_DIR/bin/python" ]; then
  PYTHON_BIN="$VENV_DIR/bin/python"
else
  for cmd in python3.14 python3.13 python3.12 python3.11 python3; do
    if command -v "$cmd" &>/dev/null; then
      PYTHON_BIN=$(command -v "$cmd")
      break
    fi
  done
fi

if [ -z "${PYTHON_BIN:-}" ]; then
  echo "[ERROR] 未找到 Python 3.11+"
  exit 1
fi

PY_VER=$("$PYTHON_BIN" --version 2>&1)
echo "[1/3] 使用: $PY_VER ($PYTHON_BIN)"

# ── 创建空 venv ──────────────────────────────────────────────────────
echo "[2/3] 创建虚拟环境..."
rm -rf "$BUNDLE_DIR"
"$PYTHON_BIN" -m venv "$BUNDLE_DIR"

# ── 安装运行时依赖（走 pip 缓存，不从零下载） ──────────────────────
echo "[3/3] 安装运行时依赖（复用 pip 缓存）..."
"$BUNDLE_DIR/bin/python" -m pip install --quiet --upgrade pip 2>/dev/null || true

# 只安装 requirements.txt 中的包，不含 dev 依赖
"$BUNDLE_DIR/bin/python" -m pip install \
  --no-input --quiet \
  -r requirements.txt 2>&1 | tail -3

# ── 清理 ─────────────────────────────────────────────────────────────
find "$BUNDLE_DIR" -name '__pycache__' -type d -exec rm -rf {} + 2>/dev/null || true
find "$BUNDLE_DIR" -name '*.pyc' -delete 2>/dev/null || true
rm -rf "$BUNDLE_DIR/lib/python3."*/test 2>/dev/null || true

# ── 验证关键包 ───────────────────────────────────────────────────────
echo ""
echo "  验证安装:"
"$BUNDLE_DIR/bin/python" -c "
import fastapi, uvicorn, openai, anthropic, pydantic, httpx, oracledb, sqlparse, mcp
print('  ✅ 所有核心依赖已安装')
print(f'  Python: {__import__(\"sys\").version}')
" 2>&1 || echo "  ⚠️ 部分依赖缺失"

# ── 统计大小 ─────────────────────────────────────────────────────────
SIZE=$(du -sh "$BUNDLE_DIR" 2>/dev/null | cut -f1)
echo ""
echo "✅ Python bundle 完成: $BUNDLE_DIR ($SIZE)"
echo "   路径: $BUNDLE_DIR/bin/python"