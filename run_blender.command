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
"$BLENDER" --background --python "$ROOT/blender/build_lunar_science_scene.py" -- "$@" --outdir "$ROOT/blender/output"
echo 'Created Blender source and GLB in blender/output/'
