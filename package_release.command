#!/bin/bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
OUTPUT="${1:-$ROOT/dist/POLARIS-X5D-SourceBuild-Mac.zip}"
TEMP_DIR="$(mktemp -d /tmp/polaris-x-package.XXXXXX)"
TEMP_ZIP="$TEMP_DIR/POLARIS-X5D-SourceBuild-Mac.zip"
trap 'rmdir "$TEMP_DIR" 2>/dev/null || true' EXIT

cd "$ROOT"
mkdir -p "$(dirname "$OUTPUT")"
zip -q -r "$TEMP_ZIP" \
  AGENTS.md README.md requirements-science.txt \
  run_polaris.command run_blender.command run_blender_bundle_v2.command rebuild_blender_hero.command \
  test_all.command package_release.command open_web_viewer.command open_web_viewer.bat \
  app blender docs schemas tools web \
  data/bundles data/viewer data/visual data/batch data/source_registry.json \
  -x '*.DS_Store' '*/__pycache__/*' '*.pyc' \
     'app/node_modules/*' 'web/node_modules/*' \
     'app/data/source/*' \
     'web/test-results/*' 'web/playwright-report/*' \
     'data/visual/*_f32.tif' 'data/visual/*/*_f32.tif' 'data/visual/*/*.partial' 'data/visual/*/*.rows' 'data/visual/*/*.log'
mv "$TEMP_ZIP" "$OUTPUT"

echo "Wrote $OUTPUT"
du -h "$OUTPUT"
if command -v shasum >/dev/null 2>&1; then shasum -a 256 "$OUTPUT"; else sha256sum "$OUTPUT"; fi
