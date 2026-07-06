#!/bin/bash
# ===========================================================================
# start.sh — YS-Agent 启动入口
#
# 薄代理，所有逻辑都在 scripts/ys-agent.sh。
# 保留此文件是为了：
#   - 不强制安装即可直接 ./start.sh 使用
#   - 对旧用户兼容
#
# 用法：
#   ./start.sh          启动（默认生产模式）
#   ./start.sh --dev    启动（开发模式，Vite 热更新）
#   ./start.sh stop     停止
#   ./start.sh --help   帮助
# ===========================================================================

set -euo pipefail
cd "$(dirname "$0")"
exec bash scripts/ys-agent.sh "$@"
