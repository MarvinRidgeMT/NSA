#!/bin/bash
# Rebuild the Blender HERO scene from the ROI export: Site01 ROI6 (default since 15 Nov 18:10; full NASA GSFC SfS relief), full 401 x 401 5 m crop, derived ray states from the
# bundle (no "not evaluated" rays), plus the display-only 80 m regional context pack when present.
#   bash rebuild_blender_hero.command                 # Site01 ROI6 (default)
#   bash rebuild_blender_hero.command site04_roi3     # Shackleton rim (SfS on the west third only)
#   bash rebuild_blender_hero.command site01_roi6     # another ROI dataset (Site01 ROI6: NASA GSFC SfS relief on the whole crop)
#   SURFACE=lola bash rebuild_blender_hero.command    # draw the bundle LOLA crop instead of the SfS display surface
# Output: blender/output/POLARIS_X_<site>_bundlev2.{blend,glb}, _scene_manifest.json, start/mid/end renders, and a log.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"
SITE="${1:-site01_roi6}"
LOG="blender/output/rebuild_hero_${SITE}.log"
mkdir -p blender/output
bash "$ROOT/run_blender_bundle_v2.command" data/viewer/polaris-x5d-roi-2026-11-14-v2.json \
  --site "$SITE" --surface "${SURFACE:-sfs}" --max-vertices-per-axis 401 --samples 128 --resolution 1920x1080 2>&1 | tee "$LOG"
echo "Blender hero rebuild finished. Log: $LOG"
