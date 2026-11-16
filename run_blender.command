#!/bin/bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"
if [[ -x /Applications/Blender.app/Contents/MacOS/Blender ]]; then
  BLENDER=/Applications/Blender.app/Contents/MacOS/Blender
elif command -v blender >/dev/null 2>&1; then
  BLENDER="$(command -v blender)"
else
  echo 'Blender was not found. Install Blender, then rerun this script.' >&2
  exit 1
fi
if [[ $# -eq 0 ]]; then
  echo 'No arguments supplied: running synthetic demonstration only (NOT NASA data).'
  set -- --demo
fi
"$BLENDER" --background --python-exit-code 1 \
  --python "$ROOT/blender/build_lunar_science_scene.py" -- \
  "$@" --outdir "$ROOT/blender/output"

shopt -s nullglob
outputs=("$ROOT"/blender/output/POLARIS_X_*.blend "$ROOT"/blender/output/POLARIS_X_*.glb)
if [[ ${#outputs[@]} -lt 2 ]]; then
  echo 'Blender finished without producing the required .blend and .glb outputs.' >&2
  exit 1
fi
for output in "${outputs[@]}"; do
  if [[ ! -s "$output" ]]; then
    echo "Blender produced an empty output: $output" >&2
    exit 1
  fi
done
echo 'Created nonempty Blender source and GLB in blender/output/'
