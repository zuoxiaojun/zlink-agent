#!/bin/bash
set -e

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"

if [ -f "$PROJECT_DIR/.env" ]; then
    source <(grep -E '^YS_FRONTEND_PORT=' "$PROJECT_DIR/.env")
fi
PORT="${YS_FRONTEND_PORT:-8088}"

# 优先用便携版 Node.js
_NODE_BIN="$PROJECT_DIR/.node/bin/node"
_NPM_BIN="$PROJECT_DIR/.node/bin/npm"
if [ -f "$_NODE_BIN" ]; then
    PATH="$(dirname "$_NODE_BIN"):$PATH"
fi

cd "$PROJECT_DIR/web"

if [ -d "dist" ]; then
    echo "Starting YS-Agent Frontend (Vite preview) on http://localhost:$PORT ..."
    npx vite preview --host 0.0.0.0 --port $PORT
else
    echo "Starting YS-Agent Frontend dev server on http://localhost:$PORT ..."
    npx vite --host 0.0.0.0 --port $PORT
fi
