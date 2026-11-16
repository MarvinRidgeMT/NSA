#!/bin/bash
# Showcase renders (Blender Cycles) for the hero scenes: aerial, ground-level, low-Sun, and the 1 m vs 10 m obstruction pair.
#   bash showcase_render.command                     # Site01 ROI6 and Site04 ROI3
#   bash showcase_render.command site04_roi3         # one site
# Needs the hero .blend from rebuild_blender_hero.command. Output: blender/output/POLARIS_X_<site>_bundlev2_showcase_*.png,
# _showcase.blend, _web.glb (Draco), _showcase_manifest.json. Presentation only; see blender/showcase.py.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"
if [[ -x /Applications/Blender.app/Contents/MacOS/Blender ]]; then BLENDER=/Applications/Blender.app/Contents/MacOS/Blender
elif command -v blender >/dev/null 2>&1; then BLENDER="$(command -v blender)"
else echo 'Blender was not found.' >&2; exit 1; fi
SITES=("$@"); [[ ${#SITES[@]} -eq 0 ]] && SITES=(site01_roi6 site04_roi3)
for SITE in "${SITES[@]}"; do
  BLEND="blender/output/POLARIS_X_${SITE}_bundlev2.blend"
  [[ -f "$BLEND" ]] || { echo "Missing $BLEND: run bash rebuild_blender_hero.command $SITE first." >&2; exit 1; }
  "$BLENDER" --background "$BLEND" --python-exit-code 1 --python "$ROOT/blender/showcase.py" -- \
    --bundle data/viewer/polaris-x5d-roi-2026-11-14-v2.json --site "$SITE" --out blender/output ${SHOWCASE_ARGS:-} 2>&1 | tee "blender/output/showcase_${SITE}.log"
done
echo "Showcase renders finished."
