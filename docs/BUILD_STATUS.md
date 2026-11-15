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

---

## b-experience branch (Claude, 14 Nov 2026, UTC times)

Rule for this branch: the viewer and Blender **only read** science-bundle-v2 files. They never compute skylines, visibility,
margins or metrics. Synthetic content is always labelled DEMO.

### 0. Baseline before any b-experience change (15:00 UTC)

Run on the Mac in the Cowork Linux shell. The macOS `.venv` can't run there, so a Python 3.10 env with the
`requirements-science.txt` packages was used.

| Suite | Command | Result |
|---|---|---|
| Blender geometry | `python -m unittest discover -s blender -p 'test_*.py'` | 9/9 pass |
| NASA/JPL ingest | `python -m unittest discover -s app/scripts -p 'test_*.py'` | 6/6 pass |
| App JS | `cd app && npm test` | 15/15 pass |
| Schema/bundles | `python app/scripts/verify_artifacts.py` | 3 v2 bundles valid |

Git: the folder was not a repo. Created `codex-snapshot` (folder as found, incl. Codex's work) and `b-experience` on top.
`.gitignore` excludes `.venv`, `node_modules`, the six 41 MB PGDA 78 GeoTIFFs (hashes are in the bundles) and `dist/*.zip`.

### 1. Scaffold `web/` (Vite 6 + React 19 + TypeScript 5.8 + Vitest 3 + Playwright 1.63): DONE

`app/` is untouched and still runs. Types: `web/src/bundle/types.ts`, from `docs/SCIENTIFIC_CONTRACT.md` and
`schemas/science-bundle-v2.schema.json`. `data/bundles/fixture.json` does not exist yet, so the only numeric mock is
`web/public/bundles/demo-fixture.json`, generated by `web/scripts/make_demo_fixture.py` and badged DEMO everywhere.

### 2. One store driving every panel: DONE

The zustand store holds UTC, site and scenario. The horizon chart, visibility strips, metrics/constraints with margins,
failures and the provenance drawer all derive from it. Samples are indexed by binary search, azimuth is interpolated on the
shortest arc, and times outside coverage are refused, never extrapolated.

**Finding:** the current Codex source bundles hold raw inputs only (DEM + JPL samples), with no skyline, visibility, margins or
metrics. The viewer shows "not in bundle" for those. `web/docs/VIEWER_BUNDLE_CONTRACT.md` proposes the additive
`datasets[i].derived` block for the science branch to emit.

### 3. Local 3D (three.js / R3F) + optional Cesium: DONE

- The DEM is drawn at 1:1 vertical scale, with the observer mast to scale.
- Sun and Earth rays use local az/el rotated into the DEM grid. When the bundle has derived outputs, they are clipped at its
  first-hit distance.
- Critical cells are clickable and open a cross-section built from the bundle's profile.
- Cesium Moon: asset 2684829 on `Ellipsoid.MOON`, with the token entered at runtime and held in memory only. Failure is
  shown and isolated.

### 4. Playwright: DONE

`cd web && npm run e2e`: 10/10 pass. Displayed margins equal the bundle values at 3 timestamps for each of 3 scenarios, as do
the metric values and visibility states. Also covered:

- between-sample labelling, and refusal of times outside coverage
- a failure click opening its cross-section
- a keyboard-only run (scrubber, scenario, failure, provenance open/close)
- the real Site01 bundle staying honest (SOURCE-BASED UNVALIDATED, JPL az shown, margins "not in bundle")
- a blocked Cesium CDN failing gracefully, with the token never stored
- an invalid bundle file being rejected
- no horizontal overflow at 390 px

`npm test`: 21/21 unit tests (Vitest), also run on this Mac from a clean `npm ci`. Screenshots are in `web/docs/screenshots/`.

### 5. Blender from bundle v2: DONE

`blender/build_from_nasa_bundle.py` was rewritten for `POLARIS-X5D-v2`. It refuses v1. Pure helpers live in
`blender/bundle_v2.py`, tested by `blender/test_bundle_v2.py` (12 tests). What it builds:

- an unexaggerated DEM mesh, 1 unit = 1 m
- a SUN lamp keyframed per sample (CONSTANT interpolation) along the bundle's JPL direction, rotated from local into grid axes
- rays clipped at the bundle's first hit, or labelled "not evaluated"
- start/mid/end renders, a `.blend`, a `.glb`, and `*_scene_manifest.json` with the bundle SHA-256

Run: `bash run_blender_bundle_v2.command [bundle.json] [--samples 64 --resolution 1920x1080]`. Outputs built with
Blender 5.3.0 (bpy):

- `blender/output/POLARIS_X_connecting_bundlev2*`: Site01 source bundle, sha256 `6a16ee59…4fb6`, SOURCE-BASED UNVALIDATED.
- `blender/output/POLARIS_X_demo-ridge_bundlev2_DEMO*`: DEMO fixture.

The manifests store a **pixel** hash of each render (`pngPixelSha256`, the decompressed IDAT stream). The file-transfer path to
this Mac inserted C2PA metadata chunks into the PNGs, which changes whole-file hashes but not pixels. Verified on this Mac:
bundle, `.blend`, `.glb` and render-pixel hashes all match.

### Open issues for the science branch (not fixed here; numbers belong to science)

1. `app/src/science.js` `horizonProfile` still steps rays along grid `(sin az, cos az)`. JPL azimuths are local, and at Site01
   local north is grid bearing ≈222.5°. The legacy app's Site01 "Sun 0 % / Earth 100 %" is suspect. Person A's separate
   a-science bundle reports Sun 81 % / Earth 66 % for the same window.
2. Emit `derived` (see `web/docs/VIEWER_BUNDLE_CONTRACT.md`) so the viewer can show real margins.
3. The schema's `validation.status` enum lacks `DEMO_ONLY`, which the contract defines.
4. Site coordinates are the PGDA 78 tile centres. The ROI centroids (e.g. Site01 ROI6, Site04 ROI3/4) are the real sites.

### Use of AI

`web/`, `blender/bundle_v2.py`, `blender/test_bundle_v2.py`, `blender/build_from_nasa_bundle.py` (v2) and
`run_blender_bundle_v2.command` were written by Claude (Anthropic) on the `b-experience` branch. Commits carry a
`Co-Authored-By: Claude` line. The `codex-snapshot` content was written largely by OpenAI Codex.

## C1 — Decision Lab integration (15 Nov 2026)

- Added the byte-identical static Decision Lab and reference data under `web/public/lab/`; `index.html` SHA-256 is `210d2fa5e9049dd53969f237d4f84f8d93df2cf280ae30acbae70ebc47cf4e0f`.
- Added the relative-base `Decision Lab` header link, long-feature write-up, standalone research code/results and required CC-BY-4.0 attribution README.
- `cd web && npm run build` passed and produced `dist/lab/index.html`; the dedicated Playwright smoke test passed 1/1 with no page errors and a loaded headline.
- Unverified: standalone research scripts and supplied result JSON were integrated as a handoff and were not independently rerun in this task.

## C2 — float32 precision audit (15 Nov 2026)

- Audited Python float32 and lunar-radius uses across `science/`, `blender/`, `tools/` and the integrated batch code. Repo science already promotes DEM samples to float64; no science solver file required a numerical change.
- The batch handoff already reads float64. Added a regression that opens a float32 GeoTIFF, proves radius-plus-height is float64, and checks the committed Site04 ROI3 anchor is exactly 94.362 %; made the unrelated SciPy sampler import lazy so this read-path test runs in the repo environment.
- Batch precision tests passed 2/2 and the full repo science suite passed 47/47.
- Unverified: previously published float32 batch outputs and PGDA 69 RMSE values were not regenerated; they remain superseded as documented in the handoff.

## C3 — bundle-traceable Decision Card (15 Nov 2026)

- Added `science/decision_card.py` and deterministic JSON plus print-only, no-JavaScript HTML cards for Site04 ROI3 and Site01 ROI6 under `data/cards/`; every numeric value carries an exact bundle path, or two source paths for a signed margin.
- Site04 reproduces bundle values 94.362 % Sun (87.537–97.329 clone range) and 72.107 % Sun+Earth (64.392–74.481); coverage, k/N, ridges, source versions and the raw bundle SHA-256 are included.
- Four Decision Card tests and the full 51-test science suite pass; deterministic JSON/HTML byte equality, numeric traceability and missing-optional omission are covered. The Site04 print layout was rendered and inspected.
- Partial: current bundles do not carry the 120 h team gap threshold or 1.75 m certainty height. The gap observation is shown without a verdict/margin and certainty height is omitted rather than hardcoded from the handoff.
