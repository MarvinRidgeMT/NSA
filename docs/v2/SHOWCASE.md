# POLARIS X v2 — Blender showcase (17 Nov 2026)

One `.blend` that gathers the v2 work, one Blender **scene** per section. Switch with the Scene selector at the top right of
Blender. **Presentation only:** nothing in it computes science; every number comes from the builders and the committed
results.

**File:** `blender/output/v2/showcase/POLARIS_X_v2_showcase.blend` (git-ignored, about 320 MB). It is rebuilt by:
```bash
POLARIS_PYTHON=.venv/bin/python Blender -b --python-exit-code 1 -P blender/v2/globe.py -- --out blender/output/v2/showcase --tag moon_globe --glb-path blender/output/v2/showcase/polaris_moon_globe.glb
bash blender/v2/build.command --lat -89.47409 --lon -137.3813 --utc 2026-11-21T02:00Z --camera eva_eye --all-around --all-around-deg 0.1 --budget 4000000 --out blender/output/v2/showcase --tag site01_roi6_eva_eye
bash blender/v2/build.command --lat -89.78012 --lon -156.32023 --utc 2026-11-21T02:00Z --camera eva_eye --all-around --all-around-deg 0.1 --budget 4000000 --out blender/output/v2/showcase --tag site04_roi3_eva_eye
bash blender/v2/build.command --lat -89.47409 --lon -137.3813 --utc 2026-11-21T02:00Z --camera lroc_nac --out blender/output/v2/showcase --tag site01_roi6_lroc_nac
bash blender/v2/build.command --lat -89.78012 --lon -156.32023 --utc 2026-11-21T02:00Z --camera lroc_wac --out blender/output/v2/showcase --tag site04_roi3_lroc_wac
.venv/bin/python blender/v2/showcase_prep.py
Blender -b --python-exit-code 1 -P blender/v2/showcase_v2.py -- --qa
```

## Scenes
| scene | what it shows | source | labels |
|---|---|---|---|
| 00 Index | the list below | — | — |
| 01 Whole Moon | cube-sphere globe from the pyramid level 0, Hapke shading with the WAC albedo, Sun from the bundle at 2026-11-21T02:00Z | `blender/v2/globe.py` | heights SOURCE-BASED · UNVALIDATED; photometry MODEL |
| 02, 03 Site01 RoI6 / Site04 RoI3 — 1.7 m eye | PGDA 78 5 m near terrain + PGDA 90 80 m far terrain; Sun lamp, Sun disc and Earth from the bundle; sight lines and the bundle skyline | `blender/v2/build_scene.py --all-around` | terrain SOURCE-BASED · UNVALIDATED; assets ILLUSTRATIVE; stars VISUAL |
| 04, 05 LROC NAC / WAC views | the same builder with the orbital camera presets | `build_scene.py` | as above |
| 06 Render vs real — LROC NAC held-out (A5) | the 26 local gallery thumbnails (real, render, log difference, edges) with each row's shadow IoU and edge error | `report_heldout.py --gallery` | scores SOURCE-BASED · UNVALIDATED; thumbnails are NASA crops, never committed |
| 07 Render vs real — LROC WAC dev (A6) | WAC thumbnails (real, render, real with predicted shadow) with scores | `wac_report.py --gallery` | as above, dev only |
| 09 Render vs real — LROC WAC held-out (A7) | held-out WAC thumbnails with scores; the claim is not met (the Otsu threshold sits at the log floor) | `POLARIS_WAC_SPLIT=heldout wac_report.py --gallery` | as above, held-out |
| 08 Mars — Jezero rim relay sky dome | the bundle's terrain skyline (orange) and MRO, TGO and Mars Express per-minute tracks over the first 24 h; bright = above the skyline, dim = hidden | `showcase_prep.py` (cached Horizons) | relay geometry SOURCE-BASED · UNVALIDATED (geometry only); dome layout VISUAL |

- **Cameras:** each site scene keeps the builder's camera. `CAM_Overview_Oblique_<nn>` is added as a navigation view, 45°
  above the near terrain.
- **Lights:** only the builders' Sun and earthshine (from the bundle) are present. No art-directed lights were added.
- **QA images:** `blender/output/v2/showcase/qa/` (index, galleries, Mars dome, site overviews).

## The blender-skills pack (arjun988/blender-skills, commit 904f095)
- **Used:** `scene-assembly` (COL_* collections), `camera-cinematography` (CAM_* naming, 35 mm overview lens), `rendering`
  (engine choice: Eevee for the diagram scenes, Cycles where the builders set it), `qa-review` (screenshot set and
  defect list).
- **Not used:**
  - its lighting recipes (key, fill and rim lamps), because the Sun must come from the ephemeris (AGENTS.md invariant 2);
  - its `blender-mcp` server, a third-party package plus a Blender add-on that opens a socket. Blender is driven directly
    from its own Python here.
- **QA defects found and fixed:**
  - The Mars track colours saturated: emission lowered, distinct hues used.
  - Overview cameras on the eye-level scenes showed missing tiles, because the builder plans tiles for the scene camera
    only. Fixed by rebuilding with `--all-around`.

## Not in the showcase
- **Mercury:** no Blender builder exists for it yet.
- **Mars terrain mesh:** no Mars `build_scene` mode exists; the Mars scene is the sky dome only.
- **ShadowCam and Kaguya TC render-vs-real:** not scored.
