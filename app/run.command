#!/bin/zsh
set -e
APP="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$APP/.." && pwd)"
PYTHON="$ROOT/.venv/bin/python"
[[ -x "$PYTHON" ]] || PYTHON="$(command -v python3)"
cd "$ROOT"
"$PYTHON" app/scripts/make_runtime_cache.py
cd "$APP"
npm run build:file
PORT=${POLARIS_PORT:-5173}
if command -v lsof >/dev/null 2>&1; then
  while lsof -nP -iTCP:"$PORT" -sTCP:LISTEN >/dev/null 2>&1; do
    echo "Port $PORT already in use — trying next available port."
    PORT=$((PORT + 1))
  done
fi
URL="http://localhost:$PORT"
echo "============================================="
echo "  POLARIS X | 5D MISSION RESILIENCE STUDIO"
echo "  Open: $URL"
echo "============================================="
python3 -m http.server "$PORT" --bind 127.0.0.1 &
SERVER=$!
trap 'kill "$SERVER" >/dev/null 2>&1 || true' EXIT INT TERM
sleep .7
open "$URL" || true
wait "$SERVER"
