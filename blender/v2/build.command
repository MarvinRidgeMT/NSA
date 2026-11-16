#!/bin/bash
# POLARIS X v2 — build one Blender scene for a lunar point, time and camera (headless).
#   bash blender/v2/build.command --lat -89.47409 --lon -137.3813 --utc 2026-11-21T02:00Z --camera eva_eye
#   bash blender/v2/build.command --lat -89.78012 --lon -156.32023 --utc 2026-11-27T08:00Z --camera shadowcam
#   bash blender/v2/build.command --lat 26.13239 --lon 3.6333 --utc 2026-11-18T00:00Z --camera eva_eye --terrain stack \
#        --bundle data/cache/anysite/bundles/314932c2112ae1bd.json --no-overlays      # S3 pyramid anywhere (needs the project venv)
# Whole Moon: Blender -b --python-exit-code 1 -P blender/v2/globe.py  (cube-sphere .blend + web/public/globe/polaris_moon_globe.glb)
# Cameras: eva_eye, lander_cam, lroc_nac, lroc_wac, shadowcam, kaguya_tc. Outputs go to blender/output/v2/ (git-ignored).
# Acceptance tests: Blender -b --python-exit-code 1 -P blender/tests/run_all.py
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"
if [[ -x /Applications/Blender.app/Contents/MacOS/Blender ]]; then
  BLENDER=/Applications/Blender.app/Contents/MacOS/Blender
elif command -v blender >/dev/null 2>&1; then
  BLENDER="$(command -v blender)"
else
  echo 'Blender was not found. Install Blender 4.5+ (tested with 5.3.0) and rerun.' >&2
  exit 1
fi
exec "$BLENDER" -b --python-exit-code 1 -P "$ROOT/blender/v2/build_scene.py" -- --world moon "$@"
