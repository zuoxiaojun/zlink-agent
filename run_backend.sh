#!/bin/bash
set -e

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"

case "$(uname -s)" in
  Darwin)  OS="macos" ;;
  Linux)   OS="linux" ;;
  MINGW*|MSYS*|CYGWIN*) OS="windows" ;;
  *)       OS="unknown" ;;
esac

VENV_ACTIVATE="$PROJECT_DIR/.venv/bin/activate"
[ "$OS" = "windows" ] && VENV_ACTIVATE="$PROJECT_DIR/.venv/Scripts/activate"

if [ -f "$PROJECT_DIR/.env" ]; then
    source <(grep -E '^YS_(AGENT_PORT|AGENT_CORS)=' "$PROJECT_DIR/.env")
fi
PORT="${YS_AGENT_PORT:-8089}"

kill_port() {
    local port=$1 pid
    if command -v lsof &>/dev/null; then
        pid=$(lsof -ti :"$port" 2>/dev/null || true)
    elif command -v netstat &>/dev/null; then
        pid=$(netstat -ano 2>/dev/null | grep ":$port " | awk '{print $NF}' | head -1 || true)
    fi
    if [ -n "$pid" ]; then
        echo "Killing existing process on port $port (PID: $pid)..."
        kill "$pid" 2>/dev/null || true
        sleep 1
        kill -9 "$pid" 2>/dev/null || true
    fi
}

kill_port $PORT
cd "$PROJECT_DIR"
source "$VENV_ACTIVATE"
echo "Starting YS-Agent Backend on http://localhost:$PORT ..."
exec uvicorn backend.main:app --host 0.0.0.0 --port $PORT --reload
