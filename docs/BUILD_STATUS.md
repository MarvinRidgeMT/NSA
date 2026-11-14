# Build status

Updated: 14 November 2026

Overall release status: **working source-backed research prototype; independently unvalidated**.

## Phase progress

| Phase | Status | Delivered |
|---|---|---|
| 1. Audit and baseline | Complete | Read `AGENTS.md`, inspected app/Blender paths, captured environment, ran the original 6 Python and 13 JavaScript tests before edits. |
| 2. NASA/JPL ingest | Working, unvalidated | PGDA 90 regional COG crops, PGDA 78 Site01 5 m/RMS/four clones, raw Horizons Sun/Earth responses, checksums, frame declarations and strict parser gates. |
| 3. Scientific engine | Working, unvalidated | Exact spherical curvature, finite-DEM 360° horizon, first blocking cell/clearance evidence, UTC coverage checks, two source sites, named fifth-dimension realizations and deterministic stress scenarios. |
| 4. Blender | Verified working as an artifact pipeline | Blender 5.3 source/demo builds, named collections, two DEM scales, five cameras, UTC frame mapping, editable `.blend`, GLB v2, metadata/manifests and three evidence renders per scene. |
| 5. Interactive interface | Verified working | Full-bleed NASA Eyes-class presentation, cinematic camera drift, progressive mission drawer, compact playback, synchronized analysis deck, source cache, full-bundle import, realization selector, WebGL/fallback terrain, four-site comparison, reports and optional Cesium. |
| 6. Integration and QA | Verified working for implemented scope | 9 geometry tests, 6 ingest tests, 15 JavaScript tests, JSON Schema/raw hashes, localhost and direct-file Chrome model smoke tests, Blender open check and GLB/manifest checks. |
| 7. Visual refinement | Complete for current experience | Immersive terrain-first composition, dense 257²/301² source meshes, circular terrain footprint, smooth low-angle regolith shading, disclosed 2.4× display relief, schematic surface node, sparse glass HUD, cinematic motion and inspected desktop renders. |
| 8. Documentation | Complete for current scope | Architecture, scientific contract, provenance, validation report, final audit and updated launch instructions. |
| 9. Packaging | Complete for current scope | Self-contained Mac ZIP excluding the rebuild-only `.venv` and full upstream GeoTIFF archive; generated bundles, raw JPL evidence and Blender artifacts are included. |

## Source cases

- Site01 full case: 80 m regional crop, 5 m nominal crop, total-Z RMS crop, four deterministic LDEM realizations and 337 hourly Sun/Earth samples.
- Two-site case: Site01 plus Site04 regional crops and 337 hourly Sun/Earth samples per site.
- Time span: `2026-11-14T14:00:00Z` through `2026-11-28T14:00:00Z`.
- Every case is labelled `SOURCE_BASED_UNVALIDATED` because the independent illumination gate is `NOT_RUN`.

## Reproduction commands used

The full Site01 command used local PGDA 78 files and a bundle-specific raw-response directory:

```bash
.venv/bin/python app/scripts/prepare_science.py \
  --sites connecting --pixels 401 --local-pixels 401 \
  --start 2026-11-14T14:00:00Z --days 14 --step-minutes 60 \
  --local-dem-file app/data/source/pgda78/Site01/Site01_final_adj_5mpp_surf.tif \
  --error-file app/data/source/pgda78/Site01/Site01_final_adj_5mpp_toterr.tif \
  --clone-file 001=app/data/source/pgda78/Site01/Clones/Site01_final_adj_5mpp_0001_err.tif \
  --clone-file 002=app/data/source/pgda78/Site01/Clones/Site01_final_adj_5mpp_0002_err.tif \
  --clone-file 050=app/data/source/pgda78/Site01/Clones/Site01_final_adj_5mpp_0050_err.tif \
  --clone-file 100=app/data/source/pgda78/Site01/Clones/Site01_final_adj_5mpp_0100_err.tif \
  --raw-dir app/data/raw/jpl/site01 \
  --output app/data/polaris-source-site01-2026-11-14-v2.json
```

The compact comparison source was generated with:

```bash
.venv/bin/python app/scripts/prepare_science.py \
  --sites connecting shackleton --pixels 401 \
  --start 2026-11-14T14:00:00Z --days 14 --step-minutes 60 \
  --raw-dir app/data/raw/jpl/two-site \
  --output app/data/polaris-source-two-site-2026-11-14-v2.json
.venv/bin/python app/scripts/make_offline_cache.py \
  app/data/polaris-source-two-site-2026-11-14-v2.json \
  --output app/data/polaris-offline-source-case.json
```

## Known incomplete requirements

- The browser remains modular JavaScript; it was not migrated to React/TypeScript.
- Independent illumination validation against a frozen external truth set is not complete.
- Numerical horizons are finite to the supplied crop, not global.
- Site04 does not yet have its PGDA 78 5 m/RMS/clone layers; Site07 and Site11 remain demo inputs.
- Cesium token-based live Moon tiles were not exercised end-to-end and are never used as numerical elevations.
- No thermal, electrical power, link-budget, DSN, hazard, navigation or flight-certification model is included.

Directly opening `app/index.html` is supported by the checked `app/dist/polaris-file.js` distributable. It embeds the compact source cache and avoids `file://` module/fetch restrictions; `npm run build:file` regenerates it.

## Highest-value next work

1. Execute and document a pre-registered, independent illumination comparison with frame-compatible authoritative data.
2. Extend horizon terrain coverage and quantify sensitivity to crop radius/resolution at all four sites.
3. Migrate the verified engine/UI contract to React/TypeScript only after preserving numerical regression coverage.
