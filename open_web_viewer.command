#!/bin/bash
# Open the POLARIS X web viewer on any Mac: double-click this file (or run `bash open_web_viewer.command`).
# Serves web/dist on http://127.0.0.1:8765 with Python 3 (no Node, no Blender needed) and opens the default browser.
# Close this Terminal window (or press Ctrl-C) to stop it.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
DIST="$ROOT/web/dist"
PORT="${PORT:-8765}"
if [[ ! -f "$DIST/index.html" ]]; then echo "web/dist is missing. Build it with: cd web && npm install && npm run build" >&2; exit 1; fi
PY="$(command -v python3 || true)"
if [[ -z "$PY" ]]; then echo "Python 3 is needed (macOS asks to install the command-line tools the first time you run python3)." >&2; exit 1; fi
echo "POLARIS X web viewer: http://127.0.0.1:$PORT  (Ctrl-C to stop)"
( sleep 1; open "http://127.0.0.1:$PORT/" ) &
cd "$DIST" && exec "$PY" -m http.server "$PORT" --bind 127.0.0.1
