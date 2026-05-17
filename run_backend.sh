#!/bin/bash
set -e

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
if [ -f "$PROJECT_DIR/.env" ]; then
    source <(grep -E '^YS_(AGENT_PORT|AGENT_CORS)=' "$PROJECT_DIR/.env")
fi
PORT="${YS_AGENT_PORT:-8089}"

PID=$(lsof -ti :$PORT 2>/dev/null || true)
if [ -n "$PID" ]; then
    echo "Killing existing process on port $PORT (PID: $PID)..."
    kill "$PID" 2>/dev/null || true
    sleep 1
    kill -9 "$PID" 2>/dev/null || true
fi

cd "$PROJECT_DIR"
source .venv/bin/activate
echo "Starting YS-Agent Backend on http://localhost:$PORT ..."
exec uvicorn backend.main:app --host 0.0.0.0 --port $PORT --reload
