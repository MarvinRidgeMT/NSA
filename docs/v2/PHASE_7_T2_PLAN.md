# POLARIS X v2 round 3 · T2 — web integration of the v2 results (plan, written before coding)

Session T2, 16–17 Nov 2026. Branch `claude/v2-t2-web-fdb776` (already contains 13551d0 = `feature/v2-whole-moon` round-3 split).
Prompt sections: V2 §2.2 item 5 (coverage layer in the UI), §2.5 (global analytics + "query any point"), §5.1 (web 3D
content exported from Blender). Owns `web/src/**` new components + the globe/layer wiring, their tests, git-ignored
`web/public/{globe,layers,anysite,draco}/**`. Does not edit `science/**` or `tools/**` (reads their outputs only).

## 0. Rules kept

- The browser computes no science. The query panel shows precomputed any-site rows (nearest site by great-circle
  distance, a table lookup, never interpolated to the clicked point) or the result of the local solver API.
- Every on-screen value keeps a `data-source` and a `data-label` ancestor so the traceability scan can classify it.
  Labels: geometry/visibility `SOURCE-BASED · UNVALIDATED`; synthetic display colour `VISUAL`; "k % of hourly samples"
  is never called a probability.
- No NASA-derived raster or mesh is committed. The globe GLB, the layer PNGs and the copied precompute summary live in
  git-ignored web paths and are rebuilt/copied by a script that records SHA-256 for each file.

## 1. Inputs (as found)

| Input | Where | Built by |
|---|---|---|
| Whole-Moon globe GLB, Draco, 2.0 MB, axes glTF +Y north / +Z lon 0 / +X 90 E, km, `scenes[0].extras.polaris.builder = blender/v2/globe.py` | `web/public/globe/polaris_moon_globe.glb` (git-ignored) | `POLARIS_PYTHON=… blender -b --python-exit-code 1 -P blender/v2/globe.py -- --no-render` |
| SVS 14959 globe (third-party, whitelisted in `glb_proof.py`) | `web/public/globe/NASA_SVS_moon_small.glb` | NASA SVS; fallback only |
| Coverage (native-resolution class, dominant source), eqc 4096 + 1440, polar 1024² 2560 m cells | `web/public/globe/coverage/` | `python -m tools.globe.coverage` (reads the whole pyramid; also rewrites committed `COVERAGE_SUMMARY.*`) |
| Slope, roughness (eqc 0.125°) | `web/public/globe/analytics/{slope,roughness}_eqc.png`, `legend.json` | `python -m tools.globe.analytics` (whole pyramid; also updates `PYRAMID_QA.json`) |
| Earth visibility (global 0.125° + polar 1 km), Sun visibility (polar 1 km, ≥ 85°) | `$POLARIS_DATA/v2/analytics/*.npz` → PNG | `python -m tools.globe.visibility …` (PNG writer reused on the cached npz) |
| 1,251 precomputed any-site rows | `data/anysite/precompute_summary.json` (committed) | `python -m science.anysite.precompute` |
| Solver API | `science/anysite/api.py --serve 8766` (stub, POST `/anysite`, GET `/` spec, no CORS); T1 is building `science/api/` | T1 |

Decision: the coverage and slope/roughness builds read the full 71 GB pyramid and rewrite committed QA documents that
are not T2's, so the sync script does **not** rerun them. It copies the already-built PNGs from a directory given with
`--from` (here the R2/S3 worktrees' git-ignored outputs, the same code as on this branch), re-renders the visibility
PNGs from the cached npz with `tools.globe.visibility`'s own writer, and records every file's SHA-256, pixel size,
projection, legend and rebuild command in `web/public/layers/manifest.json` (git-ignored).

## 2. Method

1. **Globe asset** (`web/src/three/globeAsset.ts`, `GlobalMoon.tsx`)
   - `web/public/globe/globe_manifest.json` (written by the sync script from the GLB's own glTF JSON: generator,
     `extras.polaris`, SHA-256, bytes). The viewer loads the Blender globe when the manifest names it and the file
     loads; otherwise the SVS globe, and the card says which one is shown and why.
   - Blender globe: DRACOLoader (decoder copied from `three/examples/jsm/libs/draco/gltf/` to `web/public/draco/`),
     scale 1/1737.4 (km → reference radius 1), **no re-centring** (a bounding-box centre would shift lat/lon).
   - `GlobalMoon` becomes a lazy chunk (smaller `Scene3D` chunk; backlog B15).
2. **Layers** (`web/src/globe/layers.ts`, `GlobeLayers.tsx`, shader in `web/src/three/globeLayerShader.ts`)
   - Layers: coverage · resolution, coverage · source, slope, roughness, Earth visibility, Sun visibility (polar).
   - Drape: the globe material's fragment shader computes lat/lon from the Moon-fixed world position and samples an
     equirectangular texture and/or a polar-stereographic texture (sphere R = 1,737,400 m, ρ = 2R tan(45° − |φ|/2),
     x = ρ sin λ, y = ±ρ cos λ; the same projection as `science.terrain.stack.PROJ4`, checked against pyproj values in
     a unit test). Polar texture wins where its alpha is non-zero. Opacity slider. Display only.
   - Legend: class swatches (coverage, from the tool's `legend.json`) or a sampled ramp with end values (slope 0–40°,
     roughness 0–30°, visibility 0–1), the label chip, the source line and the rebuild command. A layer whose files are
     absent says "not built here" with the command, never a blank globe pretending to be data.
3. **Query any point** (`web/src/globe/anysite.ts`, `QueryPanel.tsx`)
   - Click (not drag) on the globe → ray ∩ reference sphere → lat/lon (display geometry; reported to 0.01°). Keyboard
     path: lat/lon inputs + "Query", and "Use site marker".
   - Lookup: nearest `status == done` row of `anysite/precompute_summary.json` (copied by the sync script, SHA-256 shown)
     by great-circle distance on the 1,737.4 km sphere; shows the distance and says the values belong to that site.
     Fields: Sun / Earth / Sun+Earth % of hourly samples, longest Sun gap, ground height, slope, near/far product,
     near cut, PGDA 78 clone or assumed-error ranges where present, window, site hash, Horizons response hashes, and the
     reproduce command `python -m science.anysite.solve --lat … --lon … --mast 1 --start '2026-11-14 00:00' --days 14`.
   - Compute now: POST `solver-api/anysite` (Vite dev/preview proxy → `http://127.0.0.1:8766`, override with
     `POLARIS_SOLVER_API`). Probe `GET solver-api/` first; if it is not answering, the panel says "solver API not
     running" with the start command and disables the button. Result shown with its label and bundle path.
4. **Deep link + state** (backlog B4, partial): `globe=1` and `gl=<layer>` in the URL; the globe layer and the picked
   point live in a small store (`web/src/store/globe.ts`).
5. **Layout**: desktop — globe card left, tools panel (layers + query) right; ≤ 1023 px — one bottom sheet with tabs
   (Site / Layers / Query) so nothing overlaps at 390 px. All controls are buttons, radios, inputs (keyboard reachable,
   visible focus).

## 3. Tests

- vitest: polar-stereographic forward vs pyproj values (sp/np), eqc uv, nearest-site lookup (exact hit, antimeridian,
  pole, skips `needs coordinates`), haversine distance, layer manifest validation (missing files → "not built"),
  reproduce-command text, solver-API client states (down / spec / error / result) with a mocked fetch, QueryPanel
  rendering labels and sources.
- Playwright (`web/tests/e2e/globe-v2.spec.ts`): Blender globe loads and the card names `blender/v2/globe.py` (skips to
  the SVS assertion when the Blender GLB is absent); each layer selectable, legend + label + source visible, instrument
  text unchanged; click on the globe → query result with provenance and reproduce command; keyboard query; compute now
  with the API down → "not running" message; compute now with a mocked API route → result; deep link `globe=1&gl=slope`
  restores; 390×844 no horizontal scroll and no overlap between the sheet and the globe card; traceability scan of the
  open globe panels: 0 untraced.
- Existing: all Playwright specs (port 4222) except the known `cold-launch.spec.ts`; traceability 0 untraced;
  `blender/tests/run_all.py` (glTF proof covers the new GLB under `web/public/`).

## 4. Acceptance

`cd web && npm run build && npx vitest run` green; Playwright green on 4222 except `cold-launch.spec.ts`; traceability
0 untraced; Blender `run_all.py` green; STATUS row "T2 · …"; BUILD_STATUS appended; nothing NASA-derived committed.

## 5. As built (17 Nov 2026)

- Built as planned, with one layout change: the tools are not a right-hand column (the stage's instrument panel and the top bar sit
  there and took the clicks) but tabs Site / Layers / Query in the card's place, height-capped above the view row; a pick opens Query.
- Found and fixed: the old SVS normalisation scaled by the bounding sphere of the bounding box (√3 too large), so that globe was drawn at
  0.58 of the marker radius; both globes now sit on the reference radius 1 and the flight ends 3.6 R out.
- Checks: polar drape formula = pyproj (< 1 mm, unit test); drape vs eqc product 3,993 / 4,000 random points agree (7 on class edges);
  visibility PNGs re-rendered here are byte-identical to R2's; the real stub API through the proxy returns the precomputed row's own
  numbers (site hash 581243a87926c7b4, Sun 51.929 %, gap 162 h).
- Not done: Cesium quantized-mesh terrain (`web/public/globe/terrain/`) is not wired; T1's `science/api` is not on this branch (the panel
  uses the stub contract, documented in the shared notes); coverage and slope/roughness were copied from the R2/S3 builds, not rebuilt.
