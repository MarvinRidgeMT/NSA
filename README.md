# POLARIS X — Lunar Landing Site Navigator (NASA Space Apps 2026)
**Live demo:** [https://polarisx.earth](https://polarisx.earth/)  ·  **Demo video:** [Youtube](https://youtu.be/EZtttWtJaFc)

# POLARIS X — 5D lunar digital twin research build

POLARIS X is a local Mac research prototype for lunar south-pole terrain, time-dependent Sun/Earth geometry and deterministic uncertainty scenarios. It contains a source-backed browser dashboard, a reproducible NASA PGDA/JPL Horizons ingest pipeline, and editable Blender/GLB outputs.

**Scientific status: `SOURCE_BASED_UNVALIDATED`.** Official source records and internal consistency gates are present. Independent illumination validation is not complete. This is not flight software, a communications guarantee, or a NASA endorsement.

## Launch

From this folder:

```bash
bash run_polaris.command
```

The app opens on localhost and automatically loads a compact, source-backed two-site case for Connecting Ridge (Site01) and Shackleton Rim (Site04). You can also double-click `app/index.html`; a bundled direct-file runtime now avoids Chrome's local module/fetch restrictions and displays the same source-backed WebGL model. Peak Near Shackleton and de Gerlache remain explicitly labelled demonstration cases. Import `app/data/polaris-source-site01-2026-11-14-v2.json` in the mission drawer to expose the Site01 5 m nominal layer, RMS evidence and four deterministic terrain clones.

The redesigned experience uses a full-bleed lunar viewport, cinematic camera drift, floating mission HUD, progressive mission controls, compact playback and a synchronized scientific analysis deck. The local source terrain now renders as a dense observer-centered mesh (up to 301² vertices), with smooth regolith lighting, disclosed 2.4× visual relief, live Sun/Earth rays and a schematic surface node for scale. Numerical calculations still use unexaggerated source metres. Runtime use requires no npm install. Optional Cesium Moon visualization requires the user's own Cesium ion token and remains separate from the numerical terrain solver.

## Blender

Build the synthetic control scene:

```bash
bash run_blender.command --demo
```

Build the source-backed Site01 scene:

```bash
bash run_blender.command \
  --bundle app/data/polaris-source-site01-2026-11-14-v2.json \
  --site connecting
```

Outputs are in `blender/output/`: editable `.blend`, GLB v2, source/visibility metadata, a hash manifest, and start/middle/end PNG renders. Blender 5.3.0 on Apple Silicon was used for the verified build.

## Verify

Fast tests:

```bash
bash test_all.command
```

Full test plus both Blender rebuilds:

```bash
bash test_all.command --full
```

The suite covers pure-Python terrain geometry, raster/projection/JPL parser gates, the browser science engine, JSON Schema, raw-response hashes and generated GLB/manifest integrity. A Chrome smoke test is also available:

```bash
python3 app/tests/browser_smoke.py --screenshot
```

## Regenerate source data

The project `.venv` contains the current dependencies. For a clean environment:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements-science.txt
.venv/bin/python app/scripts/prepare_science.py --help
```

The pipeline never silently substitutes synthetic terrain or analytic ephemerides after a source failure. Full reproduction commands, source hashes and limitations are in the documentation.

## Documentation

- `docs/BUILD_STATUS.md` — implemented work and remaining gaps
- `docs/ARCHITECTURE.md` — data and component boundaries
- `docs/SCIENTIFIC_CONTRACT.md` — frames, units, time, visibility and 5D semantics
- `docs/DATA_PROVENANCE.md` — source artifacts and checksums
- `docs/SCIENCE_VALIDATION_REPORT.md` — passed and uncompleted gates
- `docs/FINAL_AUDIT.md` — release classification and evidence

The browser interface is currently modular standards-based JavaScript rather than the requested React/TypeScript migration. That migration, an independent illumination truth-set comparison, and wider horizon coverage remain open work; none is represented as complete.


---

# POLARIS X — 5D lunar digital twin research build

POLARIS X is a local Mac research prototype for lunar south-pole terrain, time-dependent Sun/Earth geometry and deterministic uncertainty scenarios. It contains a source-backed browser dashboard, a reproducible NASA PGDA/JPL Horizons ingest pipeline, and editable Blender/GLB outputs.

**Scientific status: `SOURCE_BASED_UNVALIDATED`.** Official source records and internal consistency gates are present. Independent illumination validation is not complete. This is not flight software, a communications guarantee, or a NASA endorsement.

## Launch

**Web viewer (`web/`, the current front end) on any computer:** unzip the release, then double-click `open_web_viewer.command`
(Mac) or `open_web_viewer.bat` (Windows). It serves `web/dist` on http://127.0.0.1:8765 with Python 3 and opens the browser; no Node or
Blender needed. Opening `web/dist/index.html` directly does not work (browsers block its data reads from disk).

**Legacy viewer (`app/`)**, from this folder:

```bash
bash run_polaris.command
```

The app opens on localhost and automatically loads the full source-backed runtime: Site01's 5 m nominal terrain, RMS layer and four deterministic clones, plus 80 m regional terrain and JPL records for Site01 and Site04. You can also double-click `app/index.html`; the bundled direct-file runtime avoids Chrome's local module/fetch restrictions and displays the same model. Peak Near Shackleton and de Gerlache remain explicitly labelled demonstration cases.

The redesigned experience uses a full-bleed lunar viewport, cinematic camera drift, floating mission HUD, progressive mission controls, compact playback and a synchronized scientific analysis deck. The local scene combines the full 401² Site01 5 m surface with a 241² rendering of its 80 m regional context (about 435,000 triangles). A presentation-only edge fade joins the two visual LODs while preserving a coverage boundary; disclosed 2.38× relief, live Sun/Earth rays and the surface node are also visual aids. Numerical calculations use source metres and a separate source DEM. Global mode embeds NASA SVS's official 8K LRO color-plus-height Moon (about 2.02M vertices / 1.02M triangles) and works offline. Optional Cesium Moon visualization requires the user's own ion token and remains separate from the numerical solver.

## Blender

Build the synthetic control scene:

```bash
bash run_blender.command --demo
```

Build the source-backed Site01 scene:

```bash
bash run_blender.command \
  --bundle app/data/polaris-source-site01-2026-11-14-v2.json \
  --site connecting
```

Outputs are in `blender/output/`: editable `.blend`, GLB v2, source/visibility metadata, a hash manifest, and start/middle/end PNG renders. Blender 5.3.0 on Apple Silicon was used for the verified build.

Build a real ROI hero scene with the Sun/Earth sky model (true-angle sky shell, ×5 sky chart with the 5th-axis skylines, and mast-eye renders looking at the Sun and Earth):

```bash
bash rebuild_blender_hero.command site04_roi3
```

Rebuild the 5th-axis scenario bundles (PGDA 78 clones and ±100 m offsets; queries JPL Horizons) and the viewer export:

```bash
.venv/bin/python -m science.scenario_bundles --site site04_roi3
.venv/bin/python -m science.viewer --out data/viewer/polaris-x5d-roi-2026-11-14-v2.json --dataset site01_roi6:1,10 --dataset site04_roi3:1,10 --dataset site04_roi4:1,10
```

## Verify

Fast tests:

```bash
bash test_all.command
```

Full test plus both Blender rebuilds:

```bash
bash test_all.command --full
```

The suite covers pure-Python terrain geometry, raster/projection/JPL parser gates, local-to-grid direction handling, the browser science engine, JSON Schema, raw-response hashes and NASA/Blender GLB integrity. A Chrome smoke test is also available:

```bash
.venv/bin/python app/tests/browser_smoke.py --screenshot
```

## Regenerate source data

The project `.venv` contains the current dependencies. For a clean environment:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements-science.txt
.venv/bin/python app/scripts/prepare_science.py --help
```

The pipeline never silently substitutes synthetic terrain or analytic ephemerides after a source failure. Full reproduction commands, source hashes and limitations are in the documentation.

## Solver API

The standalone solver under `tools/polaris_solver/` accepts one JSON request and returns source-labelled geometric-visibility results. From `tools/`:

```bash
python -m polaris_solver request.json
python -m polaris_solver --serve 8765
python -m polaris_solver --tool-spec
```

Set `POLARIS_DATA=../data/external` to keep downloaded NASA rasters and cached raw JPL Horizons responses outside version control. k of N counts NASA terrain clones tested; it is not a probability.

## Documentation

- `docs/BUILD_STATUS.md` — implemented work and remaining gaps
- `docs/5D_SCENARIO_AXIS.md` — 5th-axis scenarios, Sun/Earth sky model, terrain-size diagnosis
- `docs/ARCHITECTURE.md` — data and component boundaries
- `docs/SCIENTIFIC_CONTRACT.md` — frames, units, time, visibility and 5D semantics
- `docs/DATA_PROVENANCE.md` — source artifacts and checksums
- `docs/SCIENCE_VALIDATION_REPORT.md` — passed and uncompleted gates
- `docs/FINAL_AUDIT.md` — release classification and evidence
- `docs/SCREENSHOT_AUDIT.md` — verified local/global/direct-file visual evidence


## Data and AI credits

- NASA GSFC shape-from-shading DEM: Bertone et al. (2026), [Zenodo doi:10.5281/zenodo.17954508](https://doi.org/10.5281/zenodo.17954508), CC-BY-4.0. It is used only in `research/long_features/` and the Decision Lab evidence; attribution is required.
- LROC `WAC_POLE_ILL_TWI_SOUTH_100M` polar illumination map, distributed through the Planetary Data System (PDS).
- NASA PGDA products 69, 78 and 90; NASA/JPL Horizons; and NAIF SPICE.
- AI use: Anthropic Claude (analysis, research scripts, Decision Lab page) and OpenAI Codex (integration).
The production-style direct/offline application in `app/` is modular JavaScript/Three.js. A separate typed React/TypeScript bundle viewer is implemented in `web/` and deliberately reads derived bundle outputs rather than recomputing them. It also displays NASA PGDA 69's 18.6-year average Sun/Earth visibility reference maps with all 17 PGDA 78 landing-region outlines; these reference layers are clearly separated from POLARIS mission-window outputs. Independent matched truth-set comparison and wider numerical horizon coverage remain open; neither is represented as complete.
