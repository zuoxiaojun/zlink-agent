#!/bin/bash
set -e

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"

if [ -f "$PROJECT_DIR/.env" ]; then
    source <(grep -E '^YS_FRONTEND_PORT=' "$PROJECT_DIR/.env" 2>/dev/null || true)
fi
PORT="${YS_FRONTEND_PORT:-8088}"

cd "$PROJECT_DIR/web"

if [ -d "dist" ]; then
    echo "Starting YS-Agent Frontend on http://localhost:$PORT ..."
    npx serve dist --host 0.0.0.0 --port $PORT 2>/dev/null || npx vite preview --host 0.0.0.0 --port $PORT
else
    echo "Starting YS-Agent Frontend dev server on http://localhost:$PORT ..."
    npx vite --host 0.0.0.0 --port $PORT
fi
