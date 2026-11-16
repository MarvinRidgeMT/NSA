# Phase 4 round 2, session R3 — Blender whole Moon (prompt §5.1–5.2): plan

Branch `v2-r3-blender-moon` (from `feature/v2-whole-moon` at 72e3430), 16 Nov 2026. Written before coding. Owns
`blender/v2/**`, `blender/tests/**` (`docs/v2/SPLIT_ROUND2.md`). Reads, never edits, `science/**` and `tools/**`.

## 0. Facts found while reading (they shape the plan)
- **Blender's Python (3.13 in Blender 5.3.0) has no rasterio, pyproj, scipy or PIL.** `science.terrain.stack` reads COG
  tiles with rasterio, so Blender cannot open the pyramid itself. → two steps: a **pack** step in the project venv reads
  the pyramid / WAC products and writes plain `.npy` + JSON (hashes, parameters, stack metadata); Blender reads the pack.
  `build_scene.py --terrain stack` runs the pack step itself (subprocess, project venv) when the pack is missing, so one
  command still goes from lat/lon to `.blend`.
- **The solver's pyramid path does not handle equatorial windows yet** (`science/anysite/stack.get_stack` keeps the legacy
  adapter as default; with `prefer_pyramid=True` an eq site fails in `SPView` on the `local-stere` CRS, and Chandrayaan-3
  fails with "no height at the site"). R1 owns that fix. → For a pyramid-backed mid-latitude site the reference skyline is
  computed by the solver's own function, `science.skyline.compute_skyline`, fed the **same pyramid windows that Blender
  draws** (wrapped so it can sample a `local-stere` window at south-polar grid coordinates, the same idea as R1's
  `SPView`). Sun/Earth for that scene come from the existing any-site bundle (legacy terrain; the topocentric directions do
  not depend on the DEM product). This is stated as a display check, not a solver result.
- **The cached 100 m WAC product is the *morphologic* mosaic** (`WAC_morphology_globe_June2013_100m`): mosaicked from
  moderately high incidence images, so topographic shading is baked in. Used as albedo under a physically lit Hapke shader
  it would shade every crater twice. The **WAC Hapke parameter map** (`WAC_HAPKEPARAMMAP_643NM`, already cached, Sato et al.
  2014) carries the single-scattering albedo **w** on a 1° grid between 70° N and 70° S: that is the WAC albedo used for
  photometry. The morphologic mosaic is used only as a **VISUAL** base colour for the web globe (labelled "shading baked in").
- **NAC:** the cached NAC products (`data/visual/lroc_nac_pole_south_cm_avg`, the Site01 2 km crop) are illumination-
  averaged polar mosaics with shadows and PSRs baked in; as albedo they would paint shadows black. Not used (stated).
- Pyramid levels: `eq` L0 = 32 px/deg (947 m), `sp`/`np` L0 = 1280 m; eq L4 = SLDEM2015 512 ppd (59 m).

## 1. Whole-Moon base mesh — `blender/v2/globe.py` (+ `blender/v2/pack.py globe`)
- Cube-sphere: 6 faces × N×N quads (equal-angle mapping, tan-warped, so cells stay within ~1.3× in size), N = 384 for the
  `.blend` (≈ 0.9 M vertices, ~7 km spacing) and N = 192 for the web GLB. Shared edges are welded (no cracks).
- Heights: pyramid **level 0 only** (eq 947 m, polar 1280 m) through `TerrainStack` with the contract's eq↔polar blend,
  box-averaged over 3×3 sub-samples per vertex footprint (no aliasing of 1 km relief onto a 7 km mesh). NaN never filled;
  coverage at L0 is 100 % (S3), any NaN is counted and reported.
- Radius r = 1 737 400 m + h, Moon-fixed ME axes (x → lon 0, z → north). Blender units = km for the globe (stated).
- Material: the Hapke node shader (parameters unchanged, `GLOBAL` set for the globe) with **w per vertex** from the WAC
  Hapke map (1°, bilinear; poleward of 70° the regional median, blended over 1°). Sun direction from a solver bundle sample
  (topocentric az/el → Moon-fixed), never chosen by hand. Optional small render from the Earth direction of the same sample.
- Web GLB: Draco, Khronos exporter, 6 face primitives each with a 1024² face texture sampled from the WAC morphologic
  mosaic (no antimeridian/pole UV seams), `scenes[0].extras.polaris` = builder `blender/v2/globe.py` + hashes.
  Written to `web/public/globe/polaris_moon_globe.glb` (git-ignored by the existing `web/public/globe/*.glb` rule).
  `blender/tests/glb_proof.py` accepts the two POLARIS builders (`build_scene.py`, `globe.py`); the generator rule is unchanged.
- `.blend` + manifest (Blender version, script SHA-256, pack/stack index/WAC/Hapke hashes, vertex counts, timings).

## 2. Close-ups on the pyramid — `build_scene.py --terrain stack`
- Pack: near window at the native resolution of the site (`stack.window(lat, lon, half, res)`), far window at 80 m to the
  solver's range (±290 km). Heights stored exactly as the stack returns them (float64 → float32 is not done: float64 npy).
  Eq far windows (7 250² px) are read in row chunks through `TerrainStack.sample` (identical to `window` at L4 where L4
  has data; NaN elsewhere is kept) to bound memory.
- `terrain.Level` learns its projection (`sp`, `np`, `local-stere` + centre). Mesh vertices go grid → (lat, lon) with the
  level's own closed-form inverse → Moon-fixed → ENU. The south-polar path stays bit-identical (reference test).
- Tile selection is unchanged (frustum + needed spacing + coarser ring + shadow casters). Ground height, asset and camera
  placement work in lat/lon for non-`sp` levels.
- VISUAL micro-relief: optional Cycles displacement on the Hapke material from S3's `pyramid_visual` amplitude rule? No —
  S3's VISUAL tree is polar only and measured 1.2–1.9× too strong, and θ̄ already models sub-pixel roughness. Plan: an
  opt-in `--micro-relief` noise displacement node (amplitude ≤ native pixel × 0.05, labelled VISUAL in object and manifest),
  **off by default**, never used by any check.
- Checks: site01_roi6 skyline from the solver cache stays green; new: Apollo 15 (26.13° N, 3.63° E, Hadley; eq zone,
  SLDEM2015 59 m) drawn from the pyramid vs `compute_skyline` on the same pyramid windows; site01_roi6 drawn from the
  pyramid vs its committed bundle skyline.

## 3. Albedo
Per-vertex attribute `polaris_w` (float) on every terrain mesh; the Hapke graph takes `w` as a variable (one node graph,
same expression → Python test unchanged). Polar sites (all vertices poleward of 70.5°) keep exactly the regional constant,
so the stored references do not move. No NAC (reason in §0).

## 4. Renders (small, few)
Globe: one 512² render from the Earth direction. Apollo 15: one EVA-eye 640×360 and one WAC-preset 256² view. Reference
PNGs change only if a check proves they must (documented here and in the results).

## 5. Done means
`blender -b -P blender/tests/run_all.py` green; `python3 -m unittest discover -s blender -p 'test_*.py'` green;
`pytest science/tests -q`, `cd web && npx vitest run` green; STATUS row "R3 · …"; `docs/BUILD_STATUS.md` appended;
`docs/v2/PHASE_4_R3_RESULTS.md` with numbers, times and what is not done.
