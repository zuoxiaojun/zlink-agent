#!/bin/bash
set -e

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
if [ -f "$PROJECT_DIR/.env" ]; then
    source <(grep -E '^YS_FRONTEND_PORT=' "$PROJECT_DIR/.env")
fi
PORT="${YS_FRONTEND_PORT:-8088}"

cd "$PROJECT_DIR/web"
echo "Starting YS-Agent Frontend on http://localhost:$PORT ..."
npx vite --host 0.0.0.0 --port $PORT
