#!/bin/bash
# Build the Blender scene from a science-bundle-v2 file (read-only w.r.t. science).
#   bash run_blender_bundle_v2.command                                  # Site01 source bundle
#   bash run_blender_bundle_v2.command web/public/bundles/demo-fixture.json   # DEMO fixture
#   extra args after the bundle go to the builder, e.g. --samples 64 --resolution 1920x1080
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"
if [[ -x /Applications/Blender.app/Contents/MacOS/Blender ]]; then
  BLENDER=/Applications/Blender.app/Contents/MacOS/Blender
elif command -v blender >/dev/null 2>&1; then
  BLENDER="$(command -v blender)"
else
  echo 'Blender was not found. Install Blender 4.5+ and rerun.' >&2
  exit 1
fi
BUNDLE="${1:-app/data/polaris-source-site01-2026-11-14-v2.json}"
shift || true
"$BLENDER" --background --python-exit-code 1 \
  --python "$ROOT/blender/build_from_nasa_bundle.py" -- \
  --bundle "$BUNDLE" --output "$ROOT/blender/output" "$@"
