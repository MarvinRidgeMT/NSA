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
| 10 Everything at once (opens here) | every section on one board: globe (south pole up), both site terrains, the Mars dome and the three galleries, each a scaled collection instance with its scale in the label; Solid view, no lamps | `showcase_v2.py` | as the sections |
| 01 Whole Moon | cube-sphere globe from the pyramid level 0, Hapke shading with the WAC albedo, Sun from the bundle at 2026-11-21T02:00Z | `blender/v2/globe.py` | heights SOURCE-BASED · UNVALIDATED; photometry MODEL |
| 02, 03 Site01 RoI6 / Site04 RoI3 — 1.7 m eye | PGDA 78 5 m near terrain + PGDA 90 80 m far terrain; Sun lamp, Sun disc and Earth from the bundle; sight lines and the bundle skyline | `blender/v2/build_scene.py --all-around` | terrain SOURCE-BASED · UNVALIDATED; assets ILLUSTRATIVE; stars VISUAL |
| 04, 05 LROC NAC / WAC views | the same builder with the orbital camera presets | `build_scene.py` | as above |
| 06 Render vs real — LROC NAC held-out (A5) | the 26 local gallery thumbnails (real, render, log difference, edges) with each row's shadow IoU and edge error | `report_heldout.py --gallery` | scores SOURCE-BASED · UNVALIDATED; thumbnails are NASA crops, never committed |
| 07 Render vs real — LROC WAC dev (A6) | WAC thumbnails (real, render, real with predicted shadow) with scores | `wac_report.py --gallery` | as above, dev only |
| 09 Render vs real — LROC WAC held-out (A7) | held-out WAC thumbnails with scores; the claim is not met (the Otsu threshold sits at the log floor) | `POLARIS_WAC_SPLIT=heldout wac_report.py --gallery` | as above, held-out |
| 11–14 Mars, Mercury, Moon, Earth — HD full globes | true radius (1 unit = 1 km), body-fixed axes; viewport mesh n = 384 with heights; at render, adaptive subdivision displaced by the full height map: Moon SLDEM2015 (±60°) + LOLA LDEM_64 0.47 km/px, Mercury USGS DEM 0.67 km/px, Mars MOLA 128 ppd 0.93 km/px, Earth ETOPO 2022 1.85 km/px (5–22× the earlier globes); Sun direction from SPICE at 2026-11-21T02:00Z; cameras: disc from Earth (or from the Moon for Earth), sunlit side, close-up near the terminator | `globe_hd_pack.py`, `globe_hd.py` | heights SOURCE-BASED · UNVALIDATED; Moon Hapke MODEL; Earth Blue Marble Nov 2004 and Mercury MDIS colour VISUAL; Mars uniform tint VISUAL; no atmospheres |
| 15 Sun | sphere at the IAU nominal radius 695 700 km, emission with linear limb darkening u = 0.6 | `globe_hd.py` | MODEL |
| 16 Earth–Moon–Sun system | Earth, Moon and Sun at true size and de421 positions (J2000, Earth-centred), each body rotated by its SPICE body-fixed → J2000 matrix; cameras: Earth's day side, both bodies at true distance from the sunward side, Earth's night side from near the Moon (the Moon is near full) | `globe_hd.py` | positions SOURCE-BASED; Sun sphere MODEL (casts no shadow, so it does not block its own lamp) |
| 17, 18 Site04 RoI3, Site01 RoI6 — terrain to ±100 km | three levels instead of two: 5 m near, a new 20 m middle level to ±100 km (10× the earlier ±8–11 km of detailed terrain), 80 m to ±290 km; all-around tiles, ~10.7 M vertices | `build_scene.py --terrain stack --mid-half 100000 --mid-res 20` | terrain SOURCE-BASED · UNVALIDATED |
| 19 Venus | USGS Magellan topography (4.6 km/px, gaps filled from the nearest pixel) under a cloud deck at ~70 km — the visible Venus; hide the deck object to see the surface | `globe_hd.py` | terrain SOURCE-BASED; deck and surface tone VISUAL |
| 20–23 Jupiter, Saturn, Uranus, Neptune | true equatorial / polar radii (1 bar), IAU orientation and SPICE Sun; Hubble OPAL 2024–25 global colour maps (STScI MAST, DOI 10.17909/T9G593), unobserved pixels filled from their latitude row (6 %, 7 %, 38 %, 13 %); Saturn's rings from fact-sheet radii and representative optical depths, transparency 1 − exp(−τ/μ) | `giants_pack.py`, `globe_hd.py` | maps VISUAL (cloud features of the OPAL epoch); rings MODEL |
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

## Upgrades on 17 Nov (evening)
- **Earth:**
  - Day side: NASA GIBS VIIRS true colour (NOAA-21, then NOAA-20) of 2026-11-16, gaps filled from 11-15 and 11-14, so
    84 % of the globe shows real clouds of those days. Blue Marble November 2004 fills only the polar night (16 %).
  - Night side: Black Marble 2016 city lights, masked by the SPICE Sun direction.
  - Rayleigh atmosphere shell (MODEL): sea-level scattering (5.8, 13.5, 33.1) × 10⁻⁶ m⁻¹, scale height 8.5 km.
- **Mars:** USGS Viking MDIM colour mosaic at 925 m, plus a dust-haze shell (MODEL: τ ≈ 0.2, scale height 11 km).
- **UV maps:** every globe has a seam-corrected equirectangular UV map, so its colour shows in Solid view. Mercury is the
  exception: its 23,040 px mosaic exceeds the GPU texture limit and reads grey there.

## What is still not exact (stated, not hidden)
- **Clouds and weather:** they are those of 14–16 Nov 2026, not of the scene time 2026-11-21 02:00 UTC, which is in the
  future of every image.
- **The giant planets:** their cloud features are from the Hubble OPAL epochs (2024–25). Their longitudes are read as
  System III east from the map's left edge (the OPAL convention), so where storms like the Great Red Spot sit on 21 Nov
  2026 is not reproduced.
- **Neptune:** pale greenish-blue, as in the OPAL composite and the 2024 recalibration (Irwin et al.), not the
  saturated blue of older processed images.
- **Mars:** the dark regions look bluish because the Viking colourised mosaic does. The dust loading on the scene date
  is not known; τ ≈ 0.2 is a clear-season value.
- **Venus:** the surface tone under the clouds is a uniform basalt colour. Radar images have no visible-light colour.
- **Atmospheres:** single-component shells. There is no Mie aerosol on Earth, no clouds with height, and no limb
  refraction.
- **Faint rings and moons:** the faint rings of Jupiter, Uranus and Neptune, and moons other than our Moon, are not
  modelled.

## Not in the showcase
- **Atmospheres** (Earth, Mars) and the Earth's clouds and night lights are not modelled.
- **A Mars colour map**: none is downloaded, so Mars has a uniform tint rather than an invented one.
- **Solid view:** image-textured globes (Earth, Mercury) look grey in Solid view because their textures are looked up from position in the shader. Use Rendered view in their scenes.
- **ShadowCam and Kaguya TC render-vs-real:** not scored.
