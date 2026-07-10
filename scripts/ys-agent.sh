#!/usr/bin/env bash
# 兼容 shim: v1.5.0 起 zlink 是主命令，ys-agent 自动转发。
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
if [ -x "$SCRIPT_DIR/zlink" ]; then
  exec "$SCRIPT_DIR/zlink" "$@"
fi
exec bash "$SCRIPT_DIR/zlink.sh" "$@"
