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
- `docs/ARCHITECTURE.md` — data and component boundaries
- `docs/SCIENTIFIC_CONTRACT.md` — frames, units, time, visibility and 5D semantics
- `docs/DATA_PROVENANCE.md` — source artifacts and checksums
- `docs/SCIENCE_VALIDATION_REPORT.md` — passed and uncompleted gates
- `docs/FINAL_AUDIT.md` — release classification and evidence

The browser interface is currently modular standards-based JavaScript rather than the requested React/TypeScript migration. That migration, an independent illumination truth-set comparison, and wider horizon coverage remain open work; none is represented as complete.

## Data and AI credits

- NASA GSFC shape-from-shading DEM: Bertone et al. (2026), [Zenodo doi:10.5281/zenodo.17954508](https://doi.org/10.5281/zenodo.17954508), CC-BY-4.0. It is used only in `research/long_features/` and the Decision Lab evidence; attribution is required.
- LROC `WAC_POLE_ILL_TWI_SOUTH_100M` polar illumination map, distributed through the Planetary Data System (PDS).
- NASA PGDA products 69, 78 and 90; NASA/JPL Horizons; and NAIF SPICE.
- AI use: Anthropic Claude (analysis, research scripts, Decision Lab page) and OpenAI Codex (integration).
