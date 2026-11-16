# POLARIS X · web viewer (b-experience)

React + TypeScript + Vite viewer for **science-bundle-v2** / **polaris-science-results-v1** (a-science) and `POLARIS-X5D-v2`
(Codex source cases + `derived`). It reads bundles and displays them. It does
**not** compute skylines, visibility, margins or metrics; see `docs/VIEWER_BUNDLE_CONTRACT.md`.

The main offline/source application in `../app/` runs independently; this viewer remains the typed, read-only bundle presentation path.

## Run

```bash
cd web
npm install
npm run dev        # http://localhost:5174  (copies bundles into public/bundles first)
```

`npm run sync-bundles` lists, in this order: `../data/bundles/*.json` (science branch; `fixture.json` first),
`../data/viewer/*.json` (science-branch export with `derived`, e.g. the ROI datasets), `../app/data/polaris-source-*-v2.json` (Codex source cases), and `public/bundles/demo-fixture.json` (DEMO).
You can also open any bundle file from disk with **Open file…**. `?bundle=<file>` in the URL picks one.

## What you see

Three workspaces over one store (`#sky`, `#decision`, `#evidence` in the URL; arrow keys move between tabs; the clock,
site and scenario controls stay above the tabs):

- **Sky**: local 3D, horizon chart with the Ridge-of-Record highlight, **margin ribbon**, visibility strips, failures,
  events, optional Cesium Moon.
- **Decision**: metrics and constraints, 5D scenario table, **certainty height**, **coverage gauge**.
- **Evidence**: **ridge of record**, provenance and limitations, the PGDA 69 South Pole reference map.

The four decision-evidence panels read `derived.attribution`, `derived.coverage`, `derived.certainty_curve` and
`derived.margin_range` when a bundle carries them (contract in `docs/VIEWER_BUNDLE_CONTRACT.md`); otherwise they fall back
to the bundle's own critical cells, margins and mast scenarios and say so on screen.

- One store (UTC time, site, scenario) drives every panel.
- Horizon chart: bundle skyline vs Sun/Earth az/el, with the bundle margin drawn as a bar.
- Visibility strips: Sun, Earth, both, one cell per bundle sample. Click to seek.
- Metrics and constraints: current margins, plus each scenario metric with its limit, margin and PASS/FAIL.
- Failures: click one (or its red marker in 3D) to open the cross-section from the bundle's profile and critical cell.
- Local 3D: the bundle DEM at 1:1 vertical scale, the observer mast, and Sun/Earth rays clipped at the bundle's first-hit
  distance.
- Global Moon (optional): Cesium ion asset 2684829 on `Ellipsoid.MOON`. The token is typed at runtime and held in memory
  only. Any failure is shown and nothing else breaks.
- Provenance drawer: sources, SHA-256 of the loaded bytes, DEM crop and file hashes, Horizons records, gates and the status
  badge: **DEMO**, **SOURCE-BASED UNVALIDATED** or **VALIDATED**.
- South Pole reference map: NASA PGDA 69 average Sun/Earth visibility over 18.6 years, with all 17 PGDA 78 ROI outlines, whole-pole and 60 m site views, hover coordinates and source caveats. It is displayed reference data, not a POLARIS computation or a matched validation result.

## Test

```bash
npm test            # 40 Vitest unit tests (sampling, frame, validation, store, PGDA 69, scienceV2 adapter, evidence helpers)
npx playwright install chromium   # only if Google Chrome is not installed on the Mac
npm run e2e         # builds, serves on :4173, runs Playwright, writes docs/screenshots/*.png
```

Rebuild the pinned PGDA 69 layer (downloads and verifies all source SHA-256 values):

```bash
../.venv/bin/python ../tools/pgda69/build_layer.py
```

## DEMO fixture

`public/bundles/demo-fixture.json` is synthetic terrain and an invented sky. Regenerate it with `npm run demo-fixture`.
It is always labelled DEMO: a banner, the badge, and `[DEMO]` in the bundle list.

## Use of AI

This viewer was written by Claude (Anthropic) under the team's direction; commits carry a `Co-Authored-By: Claude` line.

## Terrain context, surface layers and the global Moon (14 Nov 2026)

`npm run sync-bundles` also copies three kinds of **display-only** assets (never science inputs):
`../data/visual/terrain_context/*` → `public/context/`, `../data/visual/visual_layers.json` + images → `public/visual/`,
and the hash-pinned compact NASA SVS Moon GLB → `public/globe/`.

- Explore on a dataset with a DEM and a matching context pack draws the 5 m crop inside the 80 m regional crop, with
  display-model shadows (no shadow map). Without a pack it falls back to the crop-only scene.
- Camera row: **Moon** (global model, visual context) and **South-pole context** (the crop inside its surroundings).
- **Surface** picker: neutral regolith, LROC NAC average image (only where registered imagery covers the crop),
  elevation, slope, normals, source coverage, Sun-shadow model. The chip under the title says what is shown.
- Rebuild packs: `python tools/terrain/build_terrain_context.py` (numpy; about 15 s per dataset), then `npm run sync-bundles`.
- Tests: `tests/unit/terrain-context.test.ts`, `tests/unit/visual-layers.test.ts`, `tests/e2e/terrain-context.spec.ts`.


## Links, three terrain levels and performance (15 Nov 2026)
- Share a view with `?bundle=<id>&site=<id>&t=<ISO UTC>&sc=<scenario>&cam=<view>&layer=<surface layer>`; the viewer keeps the
  address bar current. Times outside the bundle are refused.
- Terrain: 5 m crop → 20 m ring (when the context pack has `mid`) → 80 m regional; all display only.
- `npm run perf:mac` measures frame times in headed Chrome (ANGLE Metal) against `vite preview` and writes `docs/perf/`.
