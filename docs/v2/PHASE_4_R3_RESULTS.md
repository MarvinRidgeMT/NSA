# Phase 4 round 2, R3 — Blender whole Moon (prompt §5.1–5.2): results

Session R3, 16 Nov 2026 ~11:45–12:45 EST, branch `v2-r3-blender-moon` (from `feature/v2-whole-moon` 72e3430). Plan:
`docs/v2/PHASE_4_R3_PLAN.md`. Blender 5.3.0, Cycles CPU. Labels: heights SOURCE-BASED · UNVALIDATED; Hapke photometry and
w MODEL; web base colour and micro-relief VISUAL; assets ILLUSTRATIVE. Pictures show solver/pyramid numbers; their realism
against real images is R4's job and is not claimed here.

## 1. What exists now

| Piece | File | Status |
|---|---|---|
| Pyramid / WAC packs (project venv: Blender's Python has no rasterio) | `blender/v2/pack.py` | done; `site` + `globe` |
| Level projections `sp` / `np` / `local-stere` (pyramid eq windows), lat/lon placement | `blender/v2/terrain.py` | done; south-polar path bit-identical |
| Close-ups on the pyramid: `build_scene.py --terrain stack` (runs `pack.py` itself when the pack is missing) | `blender/v2/build_scene.py` | done, end to end, tested |
| WAC albedo: Hapke w per vertex; Hapke graph with w as a variable | `blender/v2/albedo.py`, `hapke.py`, `hapke_nodes.py` | done (WAC map 70N–70S); NAC not used (§4) |
| VISUAL micro-relief (Cycles displacement + bump from noise), opt-in `--micro-relief <m>` | `build_scene.py` | done, off by default, labelled |
| Whole-Moon cube-sphere base mesh from pyramid L0, `.blend` + manifest, render | `blender/v2/cubesphere.py`, `globe.py` | done |
| Web globe GLB (Draco, Khronos exporter, `extras.polaris.builder = blender/v2/globe.py`) | `web/public/globe/polaris_moon_globe.glb` (git-ignored) | built; **not wired into the web app** (web files are not R3's) |
| Checks | `blender/tests/run_all.py` (14 checks), `test_albedo.py`, `test_cubesphere.py`, `test_pack.py`, `skyline_check.py`, `photometry_check.py`, `glb_proof.py` | green |

Commands:
```
bash blender/v2/build.command --lat 26.13239 --lon 3.6333 --utc 2026-11-18T00:00Z --camera eva_eye --terrain stack \
     --bundle data/cache/anysite/bundles/314932c2112ae1bd.json --no-overlays
/Applications/Blender.app/Contents/MacOS/Blender -b --python-exit-code 1 -P blender/v2/globe.py
/Applications/Blender.app/Contents/MacOS/Blender -b --python-exit-code 1 -P blender/tests/run_all.py
.venv/bin/python blender/v2/pack.py site --lat 26.13239 --lon 3.6333 --skyline      # what --terrain stack runs for you
```
Packs live in `$POLARIS_DATA/v2/blender/packs/` (git-ignored), named by a hash of the request and the pyramid `index.json`.

## 2. Close-ups on the pyramid (§5.1b, §5.2 terrain)

**Windows.** Near: `TerrainStack.window(lat, lon, min(25 km, 1600 px), res=None → native, fill_coarser=True)`; far:
`window(lat, lon, 290 km, 80 m, fill_coarser=True)`. For the eq zone (local oblique stereographic grid, 7 250² nodes) the same
arithmetic is done in row chunks (`pack.eq_window_chunked`; equality with `window()` is a unit test, bit-exact). Filled pixels
(no data at that level → bilinear from a coarser level, as the contract allows) are counted in the pack: Site01 RoI 6 near
window 143 556 of 10.24 M (outside the PGDA 78 tile), Apollo 15 none.

**Drawing.** Unchanged view-dependent planner (frustum at the needed spacing, coarser ring to 290 km, shadow casters toward the
Sun); vertices go grid → (lat, lon) by the level's own closed-form inverse (equal to `science/terrain/stack.py` to 1e-9°,
tested) → Moon-fixed → local ENU. Assets and the eye stand on the drawn ground in lat/lon for non-south-polar grids.

**Skyline consistency (Blender ray casts from the mast top, 720 bins, 0.05° angular pixel):**

| Site | Terrain drawn | Reference | median \|Δ\| | p95 | far-bin p95 | max |
|---|---|---|---|---|---|---|
| Site01 RoI 6 | solver DEM cache (unchanged) | committed bundle | 0.0014° | 0.021° | 0.010° | 0.063° |
| Site01 RoI 6 | **pyramid** (sp L8 5 m + L4 80 m) | committed bundle | 0.0014° | 0.025° | 0.017° | 0.063° |
| Apollo 15 LM (26.132° N, 3.633° E; eq, SLDEM2015 59 m) | **pyramid** (eq L4 59 m + 80 m) | `compute_skyline` on the same windows | 0.0004° | 0.020° | 0.019° | 0.050° |

Why Apollo 15 is checked against `compute_skyline` and not a solver bundle: the any-site solver on this branch cannot yet read eq
pyramid windows (`get_stack(prefer_pyramid=True)` fails in `SPView` on the `local-stere` CRS; R1 owns that). So the reference is
the solver's own function fed the windows Blender draws (wrapped by `pack.SouthGridView`, the role of `SPView`), with the solver's
any-site settings (ray step native/5, 280 km). It isolates the drawing error, which is what this check is for. Sun/Earth for the
Apollo 15 scenes come from the existing any-site bundle `314932c2112ae1bd` (legacy LOLA 128 ppd terrain; topocentric directions do
not depend on the DEM; its skyline overlay is therefore **not** drawn on pyramid scenes, `--no-overlays`). Ground height at the LM:
pyramid −1927.95 m vs that bundle's LOLA −1925.43 m.

## 3. WAC albedo (§5.2 "albedo from WAC")

The cached 100 m WAC product is the **morphologic** mosaic (`WAC_morphology_globe_June2013_100m`): moderately high-incidence images,
topographic shading baked in. Used as albedo under a physically lit shader it would shade every crater twice, so it is **not** used
for photometry. Albedo comes from the WAC Hapke parameter map itself (`WAC_HAPKEPARAMMAP_643NM`, Sato et al. 2014; the product the
Hapke constants already came from): **w per vertex**, bilinear on the 1° cells, registered from the PDS3 label (cell (1,1) centred
at 69.5° N, 0.5° E; the PDS4 xml's corner is half a cell off and is not used). Poleward of 69.5° it blends to the regional median
over 1°; beyond 70.5° it is that median, so south-polar scenes are numerically unchanged (both stored references still match at
mean |Δ| 0.000/255). b, c, B_S0, h_S, θ̄ are unchanged (`--hapke-region`, default SOUTH_60_70 for close-ups, GLOBAL for the globe).

- Values: maria 0.20–0.27 (Tranquillitatis 0.203, Imbrium 0.266), highlands 0.39–0.46; Hadley scene 0.27–0.35; globe median 0.395
  (= the GLOBAL median of the map).
- Cycles check: flat plane with the attribute at w = 0.21 / 0.27 / 0.46 equals the Python Hapke to ≤ 1.2 × 10⁻⁶ relative.
- The graph with w as a variable equals the straight-line `reference_r` to < 10⁻⁷ at 300 random geometries/w (unit test).

## 4. Whole-Moon base mesh (§5.1a)

Equal-angle cube-sphere (cell size ratio ≤ 1.41), welded (6n² + 2 vertices, every edge shared by two quads, outward winding:
tested). Heights: pyramid **level 0** (eq 947 m, polar 1280 m) with the contract's eq↔polar blend, box-filtered as the mean of 3×3
sub-samples per node footprint; 0 NaN sub-samples. n = 384 (.blend): 884 738 vertices, node spacing 5.0–7.1 km, heights −8 502 …
+10 447 m. n = 192 (web): 221 186 vertices. Hapke material with per-vertex w; Sun lamp from a solver bundle sample
(`site01_roi6` bundle, 2026-11-21T02Z, topocentric az/el → Moon-fixed); orthographic camera along the bundle's Earth direction.

**Web GLB:** `web/public/globe/polaris_moon_globe.glb`, 2.04 MB, Draco (≈ 15–19× on positions), 6 face primitives each with a
1024² JPEG face texture sampled from the WAC morphologic mosaic (area-averaged to 8192 × 4096 first): **VISUAL base colour, shading
baked in**, stated in `extras.polaris.labels`. Axes baked for `web/src/three/GlobalMoon.tsx`: glTF +Y north, +Z lon 0, +X lon 90° E;
units km. It passes `glb_proof` as a POLARIS asset (generator "Khronos glTF Blender I/O v5.3.43", builder `blender/v2/globe.py`).
The NASA SVS globe stays whitelisted and in use: swapping `GLOBE_ASSET` is a web change for its owner (one line), not made here.

**Bug found by the first globe render:** `cubesphere.latlon_deg` treated km-scaled vertices as unit vectors, so every vertex read as a
pole (w = polar fallback) except a 1 km band on the equator — a dark line and no maria. Fixed (normalise) + regression test.
The first render also had a degenerate camera roll (`to_track_quat('-Z','Z')`); fixed to up = Y.

## 5. Renders (small; copies in `docs/v2/phase4/r3_*.png`)

| Render | Resolution, samples | Verts | Build + render (s) |
|---|---|---|---|
| Globe from the Earth direction, 2026-11-21T02Z (phase 47.5°) | 512², 16 | 0.88 M | 2.4 + 0.5 |
| Apollo 15 EVA eye, look az 160°, Sun az 98.5° el 13.4°, pyramid | 640×360, 32, denoised | 2.19 M | 6.5 + 2.7 |
| same + `--micro-relief 0.4` (VISUAL) and +1 EV | 640×360, 32, denoised | 2.19 M | 6.6 + 2.3 |
| Apollo 15 LROC WAC preset, 50 km, pyramid | 256², 16 | 0.50 M | 5.6 + 0.4 |

Packs: Apollo 15 25 s (far window 7 250², peak RSS 4.9 GB), Site01 RoI 6 13 s, globe 19 s (texture 11 s). `run_all.py`: 14/14 in 48 s.
The stored references were **not** regenerated (nothing in them changed).

## 6. Not done / limits (stated, not hidden)
- **Solver bundle on the pyramid for eq sites:** waits for R1; Apollo 15 is checked against `compute_skyline` on the same windows.
- **NAC albedo:** not used — cached NAC products are illumination-averaged polar mosaics with shadows/PSRs baked in.
- **WAC albedo resolution:** 1° (≈ 30 km) w map; no sub-degree albedo for photometry. A normalised WAC albedo mosaic (e.g. the
  Hapke-normalised 643 nm mosaic) is not cached; poleward of 70° w is a regional constant.
- **3D Tiles:** not done; close-ups are per-scene meshes, the globe is one GLB.
- **Web integration:** GLB built, not referenced by the web app (web owners; one constant in `GlobalMoon.tsx`).
- **Micro-relief:** a noise displacement with a user amplitude; no amplitude rule from data (S3's VISUAL tree is polar-only and
  measured 1.2–1.9× too strong); never used by a check.
- Globe heights are the ~1 km level box-filtered onto 5–14 km nodes: a navigation/overview mesh, not for any measurement.
- Globe: no earthshine, no Earth in the scene; the camera ignores the Earth's parallax (orthographic).
- Planner cost: the eq far window (52 M nodes) makes `plan_tiles` the slowest step (~5 s); fine for single scenes.
