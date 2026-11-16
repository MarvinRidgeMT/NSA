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

## Documentation

- `docs/BUILD_STATUS.md` — implemented work and remaining gaps
- `docs/ARCHITECTURE.md` — data and component boundaries
- `docs/SCIENTIFIC_CONTRACT.md` — frames, units, time, visibility and 5D semantics
- `docs/DATA_PROVENANCE.md` — source artifacts and checksums
- `docs/SCIENCE_VALIDATION_REPORT.md` — passed and uncompleted gates
- `docs/FINAL_AUDIT.md` — release classification and evidence
- `docs/SCREENSHOT_AUDIT.md` — verified local/global/direct-file visual evidence

The production-style direct/offline application in `app/` is modular JavaScript/Three.js. A separate typed React/TypeScript bundle viewer is implemented in `web/` and deliberately reads derived bundle outputs rather than recomputing them. It also displays NASA PGDA 69's 18.6-year average Sun/Earth visibility reference maps with all 17 PGDA 78 landing-region outlines; these reference layers are clearly separated from POLARIS mission-window outputs. Independent matched truth-set comparison and wider numerical horizon coverage remain open; neither is represented as complete.
