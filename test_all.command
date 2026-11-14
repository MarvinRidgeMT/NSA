#!/bin/bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"

PYTHON="$ROOT/.venv/bin/python"
if [[ ! -x "$PYTHON" ]]; then
  PYTHON="$(command -v python3)"
fi

echo "[1/6] Pure-Python terrain geometry"
"$PYTHON" -m unittest discover -s blender -p 'test_*.py' -v

echo "[2/6] NASA/JPL preparation pipeline"
"$PYTHON" -m unittest discover -s app/scripts -p 'test_*.py' -v

echo "[3/6] Direct-file browser distributable"
if [[ -x "$ROOT/app/node_modules/.bin/esbuild" ]]; then
  (cd app && npm run build:file)
elif [[ ! -s "$ROOT/app/dist/polaris-file.js" ]]; then
  echo "Missing app/dist/polaris-file.js; run npm install && npm run build:file in app/." >&2
  exit 1
else
  echo "Using checked distributable app/dist/polaris-file.js"
fi

echo "[4/6] Browser science engine"
(cd app && npm test)

echo "[5/6] Python syntax"
"$PYTHON" -m compileall -q blender app/scripts

echo "[6/6] JSON Schema and source-bundle integrity"
"$PYTHON" app/scripts/verify_artifacts.py

if [[ "${1:-}" == "--full" ]]; then
  echo "[full] Rebuilding Blender demonstration scene"
  bash "$ROOT/run_blender.command" --demo
  echo "[full] Rebuilding source-backed Blender scene"
  bash "$ROOT/run_blender.command" \
    --bundle "$ROOT/app/data/polaris-source-site01-2026-11-14-v2.json" \
    --site connecting
  "$PYTHON" app/scripts/verify_artifacts.py --require-blender
fi

echo "POLARIS X checks passed."
