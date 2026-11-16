# Build status

Updated: 14 November 2026

Overall release status: **working source-backed research prototype; independently unvalidated**.

## Phase progress

| Phase | Status | Delivered |
|---|---|---|
| 1. Audit and baseline | Complete | Read `AGENTS.md`, inspected app/Blender paths, captured environment, ran the original 6 Python and 13 JavaScript tests before edits. |
| 2. NASA/JPL ingest | Working, unvalidated | PGDA 90 regional COG crops, PGDA 78 Site01 5 m/RMS/four clones, raw Horizons Sun/Earth responses, checksums, frame declarations and strict parser gates. |
| 3. Scientific engine | Working, unvalidated | Exact spherical curvature, finite-DEM 360° horizon, local-ENU-to-polar-grid rotation, first blocking cell/clearance evidence, UTC coverage checks, two source sites, named fifth-dimension realizations and deterministic stress scenarios. |
| 4. Blender | Verified working as an artifact pipeline | Blender 5.3 source/demo builds, named collections, two DEM scales, five cameras, UTC frame mapping, editable `.blend`, GLB v2, metadata/manifests and three evidence renders per scene. |
| 5. Interactive interface | Verified working | Full-bleed NASA Eyes-class presentation, embedded official NASA SVS global Moon, cinematic cameras, progressive mission drawer, compact playback, synchronized analysis deck, full source cache, realization selector, Three.js/fallback terrain, four-site comparison, reports and optional Cesium. The typed React viewer also includes a source-labelled PGDA 69 whole-pole/ROI reference map. |
| 6. Integration and QA | Verified working for implemented scope | 21 geometry/Blender tests, 6 ingest tests, 18 JavaScript tests, 26 React unit tests, 11 React Chrome E2E tests, JSON Schema/raw hashes, PGDA 69 layer checks, localhost/direct-file model smoke tests and NASA/Blender GLB checks. |
| 7. Visual refinement | Complete for current experience | Full 401² 5 m surface plus 241² regional context (about 435K triangles), visible coverage boundary, presentation-only alpha/height LOD seam, low-angle regolith shading, disclosed 2.38× display relief, target rays, sparse glass HUD, cinematic motion and inspected local/global renders. |
| 8. Documentation | Complete for current scope | Architecture, scientific contract, provenance, validation report, final audit and updated launch instructions. |
| 9. Packaging | Complete for current scope | Self-contained Mac ZIP excluding the rebuild-only `.venv` and full upstream GeoTIFF archive; generated bundles, raw JPL evidence and Blender artifacts are included. |

Current archive: `dist/POLARIS-X5D-SourceBuild-Mac.zip`. It includes the embedded NASA Moon assets, direct-file runtime, generated PGDA 69 layers and builder, React production build and source. `package_release.command` reproduces it and prints the final size and SHA-256.

## Source cases

- Site01 full case: 80 m regional crop, 5 m nominal crop, total-Z RMS crop, four deterministic LDEM realizations and 337 hourly Sun/Earth samples.
- Two-site case: Site01 plus Site04 regional crops and 337 hourly Sun/Earth samples per site.
- Time span: `2026-11-14T14:00:00Z` through `2026-11-28T14:00:00Z`.
- Every case is labelled `SOURCE_BASED_UNVALIDATED` because the independent illumination gate is `NOT_RUN`.
- The generated runtime cache includes all Site01 local layers, both regional source cases, explicit local-to-grid bases and the saved JPL records; the embedded NASA global Moon is visual context only.

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

- The primary direct/offline application remains modular JavaScript/Three.js; the separate `web/` React/TypeScript viewer is implemented as a read-only bundle consumer.
- Independent illumination validation against a frozen external truth set is not complete.
- Numerical horizons are finite to the supplied crop, not global.
- Site04 does not yet have its PGDA 78 5 m/RMS/clone layers; Site07 and Site11 remain demo inputs.
- Cesium token-based live Moon tiles were not exercised end-to-end and are never used as numerical elevations.
- No thermal, electrical power, link-budget, DSN, hazard, navigation or flight-certification model is included.

Directly opening `app/index.html` is supported by the checked `app/dist/polaris-file.js` distributable. It embeds the full runtime cache, Three.js application and NASA global Moon and avoids `file://` module/fetch restrictions; `npm run build:file` regenerates it.

## Highest-value next work

1. Execute and document a pre-registered, independent illumination comparison with frame-compatible authoritative data.
2. Extend horizon terrain coverage and quantify sensitivity to crop radius/resolution at all four sites.
3. Emit versioned derived real-site outputs so the React/TypeScript viewer can display margins and metrics without recomputing science.

## 14 November continuation: terrain/global model and frame remediation

- Added NASA SVS 14959's official 8K LRO color-plus-height Moon GLB for offline global navigation (2.02M vertices / 1.02M triangles) and retained the compact color-only file as fallback; both SHA-256 values are frozen and verified.
- Replaced the prior local preview renderer with a source-backed Three.js scene using the full Site01 401² 5 m layer over a 241² rendering of the 80 m regional crop. The finite local footprint remains outlined; a presentation-only 240–300 m alpha/height fade removes the LOD crack and never feeds the solver.
- Corrected a critical legacy science defect: JPL local ENU azimuths and east/north landing offsets are now rotated into the south-polar stereographic DEM grid. Target rays and lighting use the same frame transform. Added regressions for the Site01 basis and a rotated local-east ridge.
- The corrected 14-day, hourly Site01 regional internal run gives 72.0% Sun-centre visibility and 69.3% Earth-centre visibility at the default observer. These are implementation outputs only and remain `SOURCE_BASED_UNVALIDATED`.
- Refreshed localhost/direct-file/global screenshots and verified nonempty canvases with no browser console or page errors.
- Integrated NASA PGDA 69 average Sun/Earth visibility as a clearly separate reference layer with 17 PGDA 78 ROI outlines. All eight raw source files are present locally and hash-pinned; the UI states why its 18.6-year surface/disc-edge averages cannot be treated as a matched validation of the POLARIS mission-window solver.

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

### Science-branch handoff issues recorded at that checkpoint


## C1 — Decision Lab integration (15 Nov 2026)

- Added the byte-identical static Decision Lab and reference data under `web/public/lab/`; `index.html` SHA-256 is `210d2fa5e9049dd53969f237d4f84f8d93df2cf280ae30acbae70ebc47cf4e0f`.
- Added the relative-base `Decision Lab` header link, long-feature write-up, standalone research code/results and required CC-BY-4.0 attribution README.
- `cd web && npm run build` passed and produced `dist/lab/index.html`; the dedicated Playwright smoke test passed 1/1 with no page errors and a loaded headline.
- Unverified: standalone research scripts and supplied result JSON were integrated as a handoff and were not independently rerun in this task.
- Batch-2 handoff update: the four-site Decision Lab (`Site01 RoI 6`, `Site04 RoI 3`, `Site07 RoI 1`, `Site11 RoI 4`) is byte-identical to handoff v2; `index.html` SHA-256 is `2aa9201cab410de661ec07dbbc2670b02bb83c1c743c03e21a246132f017751f`.

## C2 — float32 precision audit (15 Nov 2026)

- Audited Python float32 and lunar-radius uses across `science/`, `blender/`, `tools/` and the integrated batch code. Repo science already promotes DEM samples to float64; no science solver file required a numerical change.
- The batch handoff already reads float64. Added a regression that opens a float32 GeoTIFF, proves radius-plus-height is float64, and checks the committed Site04 ROI3 anchor is exactly 94.362 %; made the unrelated SciPy sampler import lazy so this read-path test runs in the repo environment.
- Batch precision tests passed 2/2 and the full repo science suite passed 47/47.
- Unverified: previously published float32 batch outputs and PGDA 69 RMSE values were not regenerated; they remain superseded as documented in the handoff.

## C3 — bundle-traceable Decision Card (15 Nov 2026)

- Added `science/decision_card.py` and deterministic JSON plus print-only, no-JavaScript HTML cards for Site04 ROI3 and Site01 ROI6 under `data/cards/`; every science value carries an exact bundle path, derived margins cite their operands, and the mission limit is explicitly identified as a team requirement.
- Site04 reproduces bundle values 94.362 % Sun (87.537–97.329 clone range) and 72.107 % Sun+Earth (64.392–74.481); coverage, k/N, ridges, source versions and the raw bundle SHA-256 are included.
- `--max-dark-h` defaults to the team requirement of 120 h. Site04's bundle-carried 19.4434 h nominal interval passes with 100.5566 h headroom; the cards say nominal-only because these bundles do not carry per-clone longest-gap values.
- Five Decision Card tests pass; deterministic JSON/HTML byte equality, bundle numeric traceability, team-threshold provenance, override behavior and missing-optional omission are covered. Certainty Height remains omitted: A2 is not on this branch, although commit `971df9a` on `origin/a-science` contains the separate fine-sweep batch artifact.

## C4 — Playwright traceability scan (15 Nov 2026)

- Added `web/tests/e2e/traceability.spec.ts`, which scans every indexed bundle's rendered main workspace for visible numbers followed by `%`, `h`, `m` or `°` and requires a bundle/result source plus one allowed classification.
- Report-only baseline: 1,173 scanned elements failed across 11 bundles. Added bundle-path and cautious classification attributes to the workspace boundary without changing, deleting or hiding any displayed number.
- Strict result: 0 failures across 1,172 currently rendered elements: 1,020 SOURCE-BASED, 50 SCENARIO, 102 DEMO and 0 VALIDATED. Scenario rows now carry their honest local classification instead of inheriting the source-bundle classification.
- A dedicated regression loads the synthetic fixture, requires a DEMO workspace, and rejects any SOURCE-BASED or VALIDATED descendant. The two traceability Playwright checks pass 2/2.
- Web unit tests pass 35/35, TypeScript typecheck passes and the production build succeeds. The one-element scan-count variation is due to dynamic rendering; the failure count is deterministic at zero.

## C5 — reproducibility hash (15 Nov 2026)

- Added executable `scripts/repro_hash.sh`; it verifies and reuses the committed Horizons raw responses, runs the existing Site04 ROI3 1 m science builder into a temporary directory, and does not modify the source archive.
- Canonical JSON uses sorted keys/compact separators and 12-decimal float normalization. Excluded fields are `generated_utc`, `generator.git_commit`, `generator.command`, environment-only DEM `transport`, and the separately generated `derived` extension scope; no hostname field is present.
- Mac result: `REPRO_HASH_MATCH`, generated and committed SHA-256 both `492b39151092301d81933584dde2b742d9babc99379e38b60e813dbd729d402f` in 1.67 s; `bash -n` also passes.
- A second machine can run `scripts/repro_hash.sh` from the repo root with the checked-in raw archive, cached DEM inputs and `.venv`; no second-machine result was available in this task.

## C6 — data and AI credits (15 Nov 2026)

- Added the required README attribution for the Bertone et al. (2026) NASA GSFC SfS DEM, including its CC-BY-4.0 license, Zenodo DOI and its limited use in long-feature research and Decision Lab evidence.
- Added LROC WAC/PDS, NASA PGDA 69/78/90, JPL Horizons and NAIF SPICE credits.
- Added the requested AI disclosure for Anthropic Claude and OpenAI Codex without changing existing project claims or status wording.
- Documentation-only change; final repository regression results are recorded in the completion report.

## D2 — standalone Solver API (15 Nov 2026)

- Added `tools/polaris_solver/`, a standalone JSON/CLI/localhost API that depends on NumPy, SciPy, pyproj and rasterio but does not import from `science/`. NASA rasters and raw Horizons responses use the ignored `data/external/` cache selected by `POLARIS_DATA`.
- The supplied real-input API tests pass 5/5. Site04 RoI 3 at 1 m reports 94.36 % Sun, 72.11 % Sun+Earth and a 19 h longest dark run; the three-clone and cautious-label checks also pass.
- Against the committed hourly bundle metrics, Site04 differs by 0.002 points (Sun) and 0.003 points (Sun+Earth); Site01 RoI 6 differs by 0.000 and 0.002 points respectively. All are within the required 0.01 points.
- The README exposes the request-file CLI, local server and tool-spec commands, and states that k of N is a terrain-clone count rather than a probability.

## D3 + v3 lab (2026-11-15, Claude, after Codex hit its limit)

- D3: research/long_features synced (sites.py, step15/17/18/18b/18c, surrogate, correlated-error planner incl. out-of-sample train 1–10 / test 11–20). Commit "research: sync long-features research copy (D3)".
- v3 Decision Lab copied to web/public/lab/ (index.html SHA-256 d12e0896f70c34dc389e89a0b47847ad7b569aa95e7dbb6c75c788bcbe4d36dc, verified on disk). Adds SfS-vs-LOLA at the site (step19) and 13-RoI SfS heights (step20); results sfs_result.json, hot_corr*.json, hotspots_report.json updated in research copy.
- Verified: `npm run build` OK (clean npm ci on Linux scratch copy; Mac node_modules untouched). Playwright full suite 25/25 passed against that build, incl. decision-lab four-site spec; TRACEABILITY_SCAN scanned=1171 failed=0 bundles=11.
- Existing bundle numbers unchanged. No push, no merge.
1. **Resolved in the continuation above.** `app/src/science.js` now rotates local JPL azimuth and local landing offsets into the DEM grid; matching JavaScript, TypeScript and Blender basis tests pass.
2. Emit `derived` (see `web/docs/VIEWER_BUNDLE_CONTRACT.md`) so the viewer can show real margins.
3. The schema's `validation.status` enum lacks `DEMO_ONLY`, which the contract defines.
4. Site coordinates are the PGDA 78 tile centres. The ROI centroids (e.g. Site01 ROI6, Site04 ROI3/4) are the real sites.

### Use of AI

`web/`, `blender/bundle_v2.py`, `blender/test_bundle_v2.py`, `blender/build_from_nasa_bundle.py` (v2) and
`run_blender_bundle_v2.command` were written by Claude (Anthropic) on the `b-experience` branch. Commits carry a
`Co-Authored-By: Claude` line. The `codex-snapshot` content was written largely by OpenAI Codex.

---

## 14 Nov 2026, 17:00–17:45 UTC (Claude, b-experience working tree, continuing docs/CLAUDE_HANDOFF.md)

Gates from the handoff, in order. Evidence paths are repo-relative.

| Gate | Status | Evidence |
|---|---|---|
| Live inspection of :5173 at 1512×982 and 1920×1080 | done | no console errors, no document overflow, 0 native-styled controls (`docs/VISUAL_REGRESSION_AUDIT.md`) |
| `docs/VISUAL_REGRESSION_AUDIT.md` | written | before = user's 11:22 capture copied to `app/docs/visual-audit/before-user-capture-1122ET.png`; after = `after-*.png` + browser assertions |
| `docs/UX_ACCEPTANCE.md` | written | Sky / Decision / Evidence gates (the 14 Nov product direction), each VERIFIED / UNVALIDATED / BLOCKED / NOT RUN |
| P1 values + explanation | added to `docs/SCIENCE_VALIDATION_REPORT.md` §P1 | frame bug, both rows, hashes, a-science cross-check |
| Local terrain: camera presets, softer coverage outline, cancelable global→local flight, regional camera, measured frame time | done in `app/src/scene.js`, `main.js`, `pro.js`, `index.html`, `styles.css`; `app/dist/polaris-file.js` rebuilt | presets `REGIONAL`, `OBSTRUCTION` (first-hit close-up); eased log-distance flights cancel on drag/Escape; `getPerf()`: 8.3 ms mean, 8.9 ms p95, 1.28 M tris, 421 MB heap on the Mac |
| Synchronized event navigation | done | `⇤ ⇥` buttons and `[` `]` keys jump to the previous/next Sun or Earth transition; the note names the bracketing samples and says the crossing is not refined |
| 5D nominal-vs-perturbed with binding constraint and recomputed repair | app/: unchanged (9 stress scenarios); web/: 22-scenario table with deltas and the repair row already read from a-science bundles | `web/tests/e2e/science-v2.spec.ts` |
| Blender parity at the exact Site01 timestamp | NOT RUN this pass | `blender/output/*_scene_manifest.json` still carries the pre-correction bundle hash `6a16ee59…`; the bundle itself is unchanged, so geometry is the same, but renders were not regenerated |
| Full checks | app `npm test` 21/21 (Mac); web `tsc` clean, Vitest 46/46 (Mac), 45/45 + Playwright 21 pass / 1 skipped (cloud); Blender geometry 21/21, ingest 6/6, `verify_artifacts.py` OK (4 v2 bundles, NASA GLBs, PGDA 69) in the Mac's Linux VM with `$HOME/pxenv`; `browser_smoke.py` and Blender renders: NOT RUN this pass (no Chrome/Blender in the VM) | — |
| Screenshots, release ZIP | NOT RUN (ZIP remains stale: `58025570…164d4b`) | run `bash package_release.command` after the smoke test |

### Decision-evidence engine in the React viewer (new direction, PRODUCT_EXPANSION 14 Nov)

Viewer-side implementation of the four signature features; the solver side is the a-science P2 queue. Contract for the
additive bundle fields (`attribution`, `coverage`, `certainty_curve`, `margin_range`) is in
`web/docs/VIEWER_BUNDLE_CONTRACT.md` §Decision-evidence fields.

- Three workspaces over one store: **Sky** (3D, horizon chart with ridge highlight, margin ribbon, strips, failures,
  events), **Decision** (metrics/constraints, 5D table, certainty height, coverage gauge), **Evidence** (ridge of record,
  provenance, limitations, PGDA 69 map). URL hash `#sky|#decision|#evidence`; arrow keys between tabs.
- **Margin ribbon** (`web/src/components/MarginRibbon.tsx`): bundle margins per sample, near-zero band (±0.25° display
  default or the bundle's value), unknown hatch, realization range when provided; click/arrow keys seek; the sign of every
  margin is checked against the bundle's visible flag and any disagreement is shown in red.
- **Ridge of record** (`RidgePanel.tsx`): from `derived.attribution` when present; otherwise the bundle's per-bin critical
  cell for every blocked sample, tallied per cell and merged across adjacent bins of one DEM layer (display grouping,
  totals unchanged). Click → clock seeks, horizon chart and 3D panorama highlight the bin with an eased camera move.
  Site01 (tile centre, 14 d): Earth blocked in 114 of 337 samples, all by terrain 50–80 m away at az 130.5–136.0° in the
  PGDA 78 5 m tile; Sun blocked in 64 samples by terrain 90–120 m away at az 94–125.5°.
- **Coverage gauge** (`CoverageGauge.tsx`): from `derived.coverage` when present; otherwise the share of blocked samples
  whose controlling cell lies in the near (clone) layer, labelled as a display tally; < 90 % shows the qualification text.
- **Certainty height** (`CertaintyHeight.tsx`): curve, min tested feasible height and agreement height from
  `derived.certainty_curve`; otherwise the bundle's single-realization mast scenarios as a table, explicitly not a curve.
- Adapter reads the IMPLEMENTATION_PROMPT A1–A3 bundle shapes verbatim (`dist_km`, `az_span_deg`, `*_loss_h`, `ctrl_h`; `covered_frac`; the per-mast `pass:"k/N"` rows + `certainty_height_m`) as well as the fuller contract shape; unit-tested against both.
- Palette aligned to DEMO_30S_PLAN / Design v2 (INDEX C15): Sun #F2B33D, Earth #4A90E2, teal #2EC4B6 accent, failure #E5484D; no violet anywhere — the near-zero band is teal hatching, the realization range is a grey band.
- Adapter accepts `schema: polaris-science-results-v1` (the science branch's 14 Nov rename) as well as `science-bundle-v2`;
  `sync-bundles` also reads `../data/viewer/*.json`.
- Tests: `web/tests/unit/evidence.test.ts` (13), `web/tests/e2e/decision-evidence.spec.ts` (4); existing e2e specs updated
  for the tabs. Screenshots `web/docs/screenshots/10-evidence-ridge-of-record.png`, `11-decision-certainty-coverage.png`.

Still open after this pass: Blender parity rerun, `browser_smoke.py` + full Python suite + release ZIP on the Mac, the
a-science `data/viewer` ROI export (needs `git fetch origin a-science` from Terminal: the VM has no GitHub credentials),
and the solver-side P2 fields.

### 14 Nov 2026, 13:00 EST (18:00 UTC) — small fixes after a live look (Claude, b-experience working tree)

Times from here on are EST (UTC−5), per the team rule.

- `app/src/styles.css`: at widths ≤ 760 px the scene-legend pills stretched to ~160 px tall boxes over the terrain (the
  container kept `top:300px` from the base rule while the narrow rule added `bottom:240px`, and wrapped flex lines
  stretched). Fix: `top:auto` + `align-content/align-items:flex-start` and only the first three pills on narrow widths.
  Verified live at 698 px: pills 23 px tall.
- `app/src/scene.js`: the OBSTRUCTION close-up was dominated by schematic markers tens of metres wide (impact sphere up to
  55 m radius next to a 70 m hit). In that preset the markers now render at 0.12× and the rays at 0.25× (visual only;
  hit positions and science unchanged); other presets restore 1×. `app/dist/polaris-file.js` rebuilt; app `npm test` 21/21.

### 14 Nov 2026, 13:40–13:56 EST — Mac-only checks, A1 on real data, Part B merge, team answers (Claude, b-experience session A)

**Mac-only checks, run by Anish in Terminal (~13:40 EST), all PASS:**

| Check | Result |
|---|---|
| `git fetch origin a-science` | FETCH_HEAD = `971df9a` (A1 Ridge of Record `13d23d4` + third-computer batch results) |
| `bash test_all.command` | geometry 21/21, ingest 6/6, direct-file build OK, app JS 21/21, Python syntax OK, schema/bundle/GLB/PGDA 69 integrity OK |
| `tests/browser_smoke.py --screenshot` | PASS (localhost + direct-file models, source cache, full bundle, clone selection); after-screenshots regenerated |
| `bash package_release.command` | `dist/POLARIS-X5D-SourceBuild-Mac.zip`, 161 MB, SHA-256 `2ff92c00bd810a0ce46741716adf7ce9208cd6d5c6409ac51cca3b349f63986d` (replaces the stale `58025570…164d4b`) |

**Science data copied in (untracked, from `git show FETCH_HEAD:…`, nothing else on a-science touched):** `data/bundles/*_roi*_mast{1,10}m.json`
(6) and `data/viewer/polaris-x5d-roi-2026-11-14-v2.json`. `cd web && npm run sync-bundles` lists them.

**Viewer (web/):**
- Reads the real A1 output: `derived.attribution` under the results bundle's top-level `derived` and in the export's
  `datasets[i].derived` (`dist_range_km`, `min_gap_deg`, `sun/earth_ctrl_h`, `of_record`, `per_bin.ridge_idx`). Ridges of record
  are listed first; the "blocked now" line names the ridge from `per_bin`; clicking a ridge seeks to the first sample that ridge
  blocks (lookup only). Site04 ROI3, 1 m: 3 ridges of record among 60 — R3 (16 m bump, near 5 m tile) 19 h Sun loss; R1
  (128 km, far 80 m) and R2 (0.18 km) Earth loss 41 h / 34 h. Every Sun-loss hour maps to a ridge of record (unit test).
- **Part B merge (Anish: "merge both"):** the `integration` build's DEMO decision fixture (`scripts/make_decision_fixture.py`,
  `public/bundles/demo-decision-fixture.json`), its validator refusals (source enum, ridge ids, `pass` k/N, min ≤ median ≤ max,
  coverage range, A4 array lengths), its wording ("passes on k/N alternate terrain maps tested from a h m mast") and the < 50 %
  coverage caveat are now in this tree, on top of the three workspaces. Per-requirement pass counts are shown separately; a joint
  count is never derived from marginal counts. The `integration` worktree itself was not edited.
- **Thresholds (Anish, ~13:50): Sun ≥ 70 %, Sun+Earth ≥ 40 %** (`web/src/bundle/requirements.ts`), applied only when a bundle declares
  none, labelled "team requirement" on screen.
- **T-ORG-02:** one A1–A4 contract in `web/docs/VIEWER_BUNDLE_CONTRACT.md` § "Decision evidence A1–A4 — single version".
- **T-ORG-03:** hosted preview rebuilt from the ROI bundles + export (tile-centre bundles removed).
- Tests: Vitest 54/54 (Mac), 53 + 1 skipped (cloud); Playwright 25 pass + 1 skipped (cloud; the skip needs Codex's source bundle).
  New screenshots `web/docs/screenshots/12-…site04-roi3.png`, `13-sky-site04-roi3-ridge.png`, `14-decision-certainty-demo-fixture.png`.

**Team answers (T-ORG-05, Anish ~13:50 EST):** deadline is **23:59 Sun 15 Nov** (Anish's answer to the 12:00 freeze question);
history: **rebase the web/ and blender/ work onto a-science**; thresholds Sun ≥ 70 %, Sun+Earth ≥ 40 %; Part B: merge both.

Still open: the rebase itself (not started); a-science A2 (certainty curve) and the push of A3/A4 (`d14af8d`); Blender parity.

### 14 Nov 2026, 14:06–14:35 EST — verification, live audit, Ridge of Record as the signature interaction, Certainty Height on real batch data (Claude, b-experience session A)

Scope: `web/` (the current bundle viewer), one new tool under `tools/certainty/`, docs. Not touched: `app/` (Codex), `science/` and
the a-science branch, the `integration` worktree. No reset, rebase, commit or push. Working tree still uncommitted (101 entries).

**Handoff claims verified against the repo (14:06):** branch `b-experience` @ `8079924`; `origin/a-science` = FETCH_HEAD = `971df9a`
(A1 + batch results); **`d14af8d` (A3/A4) is not in this clone** (`git cat-file` fails) → Coverage Gauge and the ribbon's clone band
still run on fallbacks / the DEMO fixture, labelled as such; release ZIP SHA-256 `2ff92c00bd810a0ce46741716adf7ce9208cd6d5c6409ac51cca3b349f63986d`
recomputed and equal. `git worktree list` marks the `integration` worktree "prunable" from the VM (macOS path); it was not touched — do
not run `git worktree prune` from the VM.

**Ridge data checked in the bundle (Site04 ROI3, 1 m):** R3 `relief_m` = +1.563 m (ridge `height_m` 1739.069 − site 1737.506),
`dist_range_km` 0.012–0.169, 19 Sun-loss h; R1 127.7–129.6 km (far 80 m DEM), 41 Earth-loss h; R2 0.18 km, `relief_m` −1.76 m,
34 Earth-loss h. Loss hours are hourly samples × 1 h, **disjoint** (Sun 19 = 19 blocked samples; Earth 41 + 34 = 75 blocked samples).

**Ten problems found in the live audit (1512×982, 1440×900, 1920×1080, 820×1180, 390×844; 3 workspaces), ranked, and what was done:**

| # | Problem | Status |
|---|---|---|
| 1 | **Science sync:** viewer mapped a body azimuth to a skyline bin by rounding down; the science branch uses the nearest bin (bins are centred). 4 of 75 Earth-loss hours showed the wrong ridge in "blocked now" / ridge seek. | **Fixed** (`binForAzimuth` nearest); unit test reproduces the bundle's per-ridge hours exactly for Sun and Earth. |
| 2 | Ridge of Record lived only in a table; Sky said nothing about what blocks the Sun/Earth. | **Fixed:** Sky callout per blocked target (ridge id, distance range, bearing, height vs site ground, hours, this obstruction's start/end, before/after jump); ridge auto-highlights when a target becomes blocked; whole ridge span highlighted on the horizon chart and the panorama. |
| 3 | The 16 m / 1.6 m rise was invisible in 3D: mesh decimated to 10 m, 2.5 m-wide "1 m mast", 8 m markers, camera 700 m away, flat fill light. | **Fixed (export bundle, real DEM):** full 401² 5 m mesh, true-scale mast, constant-screen-size markers, low-fill hard Sun light, ridge line drawn from `per_bin.ctrl_dist_m`, eased log-distance camera move to a close view behind the mast on selection. |
| 4 | Far ridge R1 (128 km) could look like local terrain. | **Fixed:** callout badges "80 m regional DEM" and says the alternate maps do not vary it; in the DEM view the caption says "beyond this 2 km DEM crop: not drawn". No terrain is drawn beyond source coverage. |
| 5 | "Height 4970 m / 1739 m" (absolute DEM heights) read as ridge heights. | **Fixed:** "Height vs site" = `relief_m`; absolute height in the tooltip. |
| 6 | Certainty Height had no real data (A2 not emitted). | **Fixed with existing hashed outputs:** sidecar from the committed batch CSVs (below). |
| 7 | Evidence overflowed horizontally (1605 px at 1512; 580 px at 390); Decision overflowed at 390. | **Fixed;** e2e asserts no horizontal overflow for every workspace at 390 and 820 px. |
| 8 | Uncaught `removeChild` page error when leaving Sky (canvas torn down under drei labels); camera reset on every tab switch. | **Fixed:** Sky stays mounted (hidden) and pauses its render loop; e2e asserts zero page errors across tab switches. |
| 9 | 3D scene started ~440 px down; header and clock used two rows each. | **Improved:** one-row header ≥ 1200 px, one-row clock, scene height `clamp(380px, 54vh, 640px)`, callouts moved beside the scene. |
| 10 | Hero case did not open first; Certainty chart squeezed 87–100 % into the top of a 0–100 axis with colliding labels. | **Fixed:** Site04 ROI3 1 m opens first; ordinal sampled-height axis, zoomed y range, whiskers per sampled height. |

Not done (confirmed remaining): global Moon → site flight in `web/` (exists only in `app/`); margin-ribbon visual redesign; Blender
parity; typography/design-system pass; the NASA Eyes / 14islands comparison and the three art-direction concepts were **not** produced
in this pass (implementation was prioritised; `claude/ART_ARCHITECTURE` holds the design proposal).

**Certainty Height (real, batch):** `tools/certainty/build_certainty_sidecar.py` (stdlib; no solver run) reads
`data/batch/2026-11-14/certainty_height{,_fine}/clone_sweep_summary.csv` (extracted from FETCH_HEAD `971df9a`, untracked copy) →
`web/public/certainty/sidecar.json`. Site04 ROI3, nominal + 20 clones, 10 sampled masts (1, 1.25, 1.5, 1.75, 2, 3, 5, 7, 10, 15 m):
team requirements (Sun ≥ 70 %, Sun+Earth ≥ 40 %) pass on 20/20 maps at every sampled mast, so **minimum tested feasible height = 1 m
(the lowest sampled)**; **agreement height (Sun spread ≤ 1.0 pt) = 1.75 m**; Sun 100 % on every tested map from 1.75 m (the batch
README's "Certainty Height"). Site01 ROI6: all three = 1 m. Batch ≠ repo solver (2 knife-edge samples at 1 m); the panel states this
and the CSV hashes. A bundle's own `derived.certainty_curve` will override the sidecar when a-science emits A2.

**Bundle fields consumed (no new field names invented):** `derived.attribution.{ridges[].{id, dist_km, dist_range_km, az_span_deg,
height_m, relief_m, source, sun_loss_h, earth_loss_h, sun_ctrl_h, earth_ctrl_h, min_gap_deg, of_record}, per_bin.{ridge_idx,
ctrl_dist_m, gap_deg, source}, scenarioId}`, `samples[].{sun,earth}.{az_deg, center_visible, margin_deg}`, `skyline.{azimuth_deg,
elevation_deg, critical}`; export `datasets[].dem` (drawing only). Contract updated: `web/docs/VIEWER_BUNDLE_CONTRACT.md` (lookup
rules, sidecar format).

**Tests actually run this pass:** Mac (Linux VM, `$HOME/webcheck`): `tsc --noEmit` clean, Vitest **57/57**. Cloud (Chromium, software
GL): Vitest 56 + 1 skipped, Playwright **27 passed, 1 skipped** (the skip needs Codex's source bundle), production build OK.
Not rerun this pass: `test_all.command`, `browser_smoke.py`, release packaging (no `app/` change since Anish's 13:40 run; the ZIP does
not contain this pass's `web/` changes).

**Performance:** measured only under software GL in the cloud (mean frame 219 ms with the 401² mesh; bundle load 0.15–1.5 s): **not
representative**. FPS, frame spikes and memory of `web/` on the Mac GPU: NOT MEASURED (the VM cannot serve the viewer to a Mac
browser; run `cd web && npm run dev` and open http://localhost:5174).

**Screenshots:** `web/docs/screenshots/12-evidence-ridge-of-record-site04-roi3.png`, `13-sky-site04-roi3-ridge.png`,
`15-sky-dem-ridge-r3-true-scale.png`, `16-decision-certainty-height-batch-site04-roi3.png`.

**Still SOURCE-BASED UNVALIDATED:** every ridge, margin, visibility and certainty number. Blockers: A3/A4 push (`d14af8d`), A2 in
bundles, Sid's acknowledgement of the contract, the rebase decision's execution, the freeze policy.

**Correction, 14:35 EST (after re-reading the project docs):** A3/A4 **are on GitHub** as `d7b5463` (Sid's push after rebasing
`d14af8d`; a-science 14:15), and A2 is done locally on Sid's Mac (`4bb48b5`, push pending; it emits `derived.certainty` plus flat
`derived.certainty_curve` / `certainty_height_m`, and reproduces 1.75 m at Site04 ROI3 with the repo solver). They are simply **not in
this Mac clone yet**: its last fetch (13:40) stopped at `971df9a`, and the VM cannot fetch. Next step for Anish in Terminal:
`git fetch origin a-science`, then copy the regenerated `data/bundles/*_roi*` and `data/viewer/*.json` out of FETCH_HEAD (as at 13:45)
and `cd web && npm run sync-bundles`. The viewer already reads `derived.coverage` and `derived.margin_series`; **unverified until then**:
that a-science's actual A3/A4/A2 key names match what the adapter expects, and which criterion its `certainty_height_m` uses (team
requirements vs 100 % Sun on every map) — the panel labels a bundle-supplied value "as the bundle defines it" for that reason.
a-science acknowledged the single contract (T-ORG-02) at 14:15.

### 2026-11-14 17:41 EST — web/dist rebuilt (b-experience session A)
- `web/dist` rebuilt from the current uncommitted `web/` sources (bundle `index-B28sWnr5.js`; 14 bundles + certainty sidecar). Build output only, git-ignored; no source changes. Serve with `python3 -m http.server 4173 -d web/dist` → http://127.0.0.1:4173.

### 2026-11-14 17:57 EST — app/ simple UI layer (b-experience session A)
Request (Anish): "clean up the ui, make it easy for someone to use", modelled on NASA's own web viewers.
- Pattern taken from NASA Eyes on the Solar System / Moon Trek (layout ideas only; no NASA code, logos or assets copied):
  full-screen 3D; place name top-left; one "View" card on the right; one summary card and one time bar at the bottom;
  Settings / Charts / Rotate on the left; everything else on demand.
- `app/src/styles.css`: new block "Simple UI layer", scoped to `.simple-ui` (delete that class from `#app` in
  `app/index.html` to get the old layout back). Hidden: decorative grid, fixed "PX SURFACE NODE" label (it did not track
  anything), observer HUD (values stay in Settings), mission code, duplicate status pills. Type raised from 6–9 px to 10–22 px.
- `app/index.html`: `simple-ui` class; button labels in plain words (Settings, Charts, Rotate, Perspective…, Local terrain /
  Whole Moon, Export report, Fullscreen). Every element id kept; no JS, science or data change; `dist/` not rebuilt.
- Checks: app tests 21/21; headless Chromium at 1512×982 and 1280×800: no collisions among browser_smoke's pairs plus
  four new ones, no page scroll, no page errors. 390 px phone layout unchanged (Codex's mobile rules). Screenshots:
  `app/docs/visual-audit/simple-ui-1512x982.png`, `simple-ui-1280x800.png`. `browser_smoke.py` not re-run on the Mac yet.

---

## Rebuild phases (master rebuild prompt, started 2026-11-14 19:26 EST, b-experience session A)

Phase list from `POLARIS_X_FABLE_5_2_MASTER_REBUILD_PROMPT.md` (Anish's Documents folder; not in the repo). Status is what was
actually run in this working tree. Nothing here changes the release status: **SOURCE_BASED_UNVALIDATED**.

| Phase | Status | Evidence |
|---|---|---|
| 0. Protect and reproduce | **Done** (2026-11-14 19:26) | below |
| 1. Source registry + texture feasibility | **Registry done; texture found, registered, half downloaded** (archive rate limit) | below |
| 2. Shared scientific/render contract | **Contract, schema, validators, solver guards and tests done; consumers not wired yet** | "Phase 2" below |
| 3. Unified application shell | Not started (two shells remain: `app/` and `web/`) | — |
| 4. Multiscale terrain, seam removal | Not started | — |
| 5. Lunar material, shadows, lighting | Not started (Phase 1 texture is its input) | — |
| 6. Camera-led experience | Partly present from earlier work (presets, flights in `app/`); not re-verified under this prompt | — |
| 7. 4D / 5D completion | Partly present (timeline, events, scenarios); not re-verified | — |
| 8. Blender parity | Not started (v2 manifest still `derivedOutputsPresent: false`) | — |
| 9. QA, performance, packaging | Not started; release ZIP is stale | — |

> **Updated 22:50 EST:** this table is the 19:26 snapshot. Current status of every phase: section "Rebuild phases 1, 3–9 — 14 Nov 2026 20:00–22:20 EST" below (Phase 1 complete; 3–6 done or partly done in `web/`; 8 prepared, not run; 9 partly).

### Phase 0 — protect and reproduce (done)
- Git: branch `b-experience` @ `8079924` = `origin/b-experience`; 101 modified/untracked paths, all kept. No reset, checkout,
  clean, stash, commit or push. `integration` worktree untouched.
- Concurrent work seen: `tmp/web_before_penumbra_20261114_1906.tgz`, `tmp/penumbra_src_snapshot.tgz`,
  `tmp/penumbra_data_snapshot.tgz` (19:04–19:09 EST, another session, apparently preparing the "Penumbra" redesign of `web/`).
  No `web/` source file had changed when checked (19:15). **This pass did not edit `web/` or `app/`.**
- Baseline, run in the Mac's Linux VM unless noted:
  - `python3 -m unittest discover -s blender -p 'test_*.py'` → **21/21 pass**
  - `cd app && npm test` → **21 pass, 0 fail, 0 skipped**
  - `web`: `tsc --noEmit` clean; Vitest **57/57 pass** (9 files); `vite build` OK at 17:41 EST (not re-run; no `web/` change since)
  - Not run in this pass: `bash test_all.command`, `app/tests/browser_smoke.py`, web Playwright, Blender CLI (need macOS
    Chrome / Blender; the VM has neither).
- "Before" captures: `app/docs/visual-audit/after-1512x982.png`, `after-1920x1080.png`, `app/docs/browser-global-moon.png`
  (Mac Chrome smoke run, 17:38 EST) and `app/docs/visual-audit/simple-ui-1512x982.png`, `simple-ui-1280x800.png` (17:57 EST).
- Known baseline numbers kept for comparison: `app/` local scene 640K triangles (5 m + 80 m LOD), global Moon 1.02M triangles;
  Mac Chrome 8.3 ms mean frame / 421 MB heap (12:03 EST measurement, 1.28M-triangle build).
- Mac host verification at 19:30 EST: `bash test_all.command` **passed**. Geometry 21/21, ingest 6/6, app 21/21,
  source tools 7/7, Python syntax, schema/bundle integrity, NASA SVS GLB hashes and PGDA 69 checks all passed. The command
  regenerated the runtime cache and direct-file bundle. Browser smoke, Playwright and Blender CLI remain separate checks.
- Concurrency recheck at 19:30 EST: the Penumbra session wrote shared `web/src` files and `web/tests/e2e/penumbra.spec.ts` at
  19:28:19 EST. Phase 2 must not edit `web/` until that session is finished and its current state has been re-baselined.

### Phase 1 — source registry and texture feasibility
- **Registry (done):** `tools/sources/build_source_registry.py` → `data/source_registry.json` (`polaris-source-registry-v1`):
  10 sources with role (numerical-authority / ephemeris-authority / reference-layer / visual-context / reference-only), URL,
  credit, frame, projection, pixel scale, limitations; 43 local files hashed (454 MB). **12 of 12 previously documented
  SHA-256 values match** (PGDA 78 nominal, RMS, four clones; both NASA SVS GLBs; four bundles/caches). PGDA 90 keeps
  decoded-crop hashes only (no whole-file hash is claimed). `--check` verifies without rewriting.
- **Texture feasibility (answer: yes, a registered product covers the Site01 hero footprint).**
  LROC "Controlled 1 m/pixel South Pole Average Mosaic", tile `NAC_POLE_SOUTH_CM_AVG_P892S2250` (88.5–90° S, 180–270° E),
  PDS3 32-bit float, 45488², 8.28 GB. Same projection family as PGDA 78/90 (south polar stereographic, 90° S / 0° E,
  R = 1737400 m, 1 m/px), controlled to LOLA tracks. Site01 (x −10999, y −11999 m) and both Site04 ROIs fall in this tile.
  - `tools/sources/fetch_lroc_nac_crop.py` reads the label, refuses to run if the geometry keys differ, and fetches only
    the window by HTTP byte ranges (resumable). Window = the app's Site01 5 m crop footprint, x −12000…−10000,
    y −13000…−11000 m → 2000 × 2000 px.
  - **1056 of 2000 rows fetched**, then the archive answered HTTP 429 (Retry-After 3600 s) because the first run used
    12 threads. The script now defaults to 2 threads with a pause and stops cleanly on 429. Rows are kept in
    `data/visual/lroc_nac_pole_south_cm_avg/site01_center_2km.partial`; re-running resumes. Resume scheduled ~20:30 EST.
    Live verification at 19:30 found no existing process or launchd job, so a conservative user launchd job was submitted
    as `com.polarisx.lroc.resume` for about 20:30 EST. It uses one thread, a 0.5 s pause, checks for another active Site01
    fetch before starting, and logs to `/tmp/polaris_lroc_resume.log`. The verified sleeping wrapper is
    `/tmp/polaris_resume_lroc.zsh`; it removes its transient launchd job on exit.
  - **Registration evidence** (`tools/sources/check_nac_dem_registration.py`, north half, 84,400 5 m pixels): the image's
    best alignment to the 5 m DEM is a shift of **x −5.7 m, y −0.3 m** (peak NCC 0.39 vs 0.37 at zero shift; search ±60 m,
    peak not at the edge). About one DEM pixel; good enough for a display texture, **not** a validation of either product.
    Result: `data/visual/lroc_nac_pole_south_cm_avg/site01_center_2km_north_half_registration.json`.
  - Limits written into the manifest/registry: the mosaic is an **average over 18,323 images**; its label says it "does not
    accurately represent any realistic lighting condition". Shading is baked in. It is **visual context only**: never an
    input to horizons, rays, elevations or metrics, and never shown as the lighting at a mission time.
- Not downloaded (reference-only entries): USGS/LROC WAC 100 m mosaic, SVS CGI Moon Kit, ShadowCam.
- Tests: `python3 -m unittest discover -s tools/sources -p 'test_*.py'` → **7/7 pass** (NAC pixel rule: tile corners, 2000-px
  window aligned to the 5 m grid, Site01 projected point; label parser; registry roles, hashes, no whole-file hash for
  remote-only sources). `test_all.command` includes a `[sources]` step (tests + registry `--check`) and passed on the Mac
  host at 19:30 EST. The test's source-registry file handle is now closed explicitly; the focused 7-test rerun passed
  without the earlier `ResourceWarning`.
- `.gitignore`: float32 copy and partial downloads under `data/visual/` ignored; the 8-bit PNG + manifest stay trackable.

### Next (in order)
1. Finish the NAC window (remaining 944 rows), full-window registration check, rebuild the registry → Phase 1 complete.
2. Phase 2: typed contract separating scientific terrain from visual layers (add `visualLayers[]` with role, product ID,
   registration, "VISUAL" label) + tests. Coordinate with the session working on `web/` first (see concurrent work above).
3. Phase 5 quick win once the texture is complete: drape it on the 5 m mesh in `app/` as an "ALBEDO (LROC NAC AVG, VISUAL)"
   surface layer, default lighting unchanged.

### 2026-11-14 19:05–19:55 EST — Penumbra V3 implemented in `web/` (Claude strategy/design session)
Request: "PENUMBRA V3: complete website rescue and visual implementation". Target chosen: `web/` (see `docs/FRONTEND_SOURCE_OF_TRUTH.md`);
`app/` (5173, not running at 19:05) untouched; no science, bundle, schema or contract change; nothing committed or pushed.
- **What:** Penumbra tokens + self-hosted fonts; one-row shell; Story landing at `/` (numbers read from the certainty/coverage sidecars and the
  bundle); Explore as a full-viewport stage (real 401² × 5 m DEM by default via the ROI export's Site04 ROI3; skyline-only bundles labelled
  HORIZON GEOMETRY); floating instrument; temporal bar with full-width ribbon; named camera views (1.4 s, interruptible, reduced-motion cut);
  black-sky scene with ACES, key light from the bundle Sun azimuth + illustrative shadows, Sun disc on the true direction; batch Coverage
  Gauge rings (new `tools/certainty/build_coverage_sidecar.py` → `web/public/certainty/coverage.json`, verbatim copy with SHA-256);
  Decision Card print view; ribbon/strip per-sample `<title>` nodes replaced by one summary + on-demand table; responsive tablet/mobile.
  Details and file list: `docs/PENUMBRA_IMPLEMENTATION_STATUS.md`. QA: `docs/VISUAL_QA.md`. Rendering honesty + measured performance:
  `docs/RENDERING_VALIDATION.md`. Screenshots: `web/docs/screenshots/penumbra/{before,after}/`.
- **Tests:** `tsc` clean (Mac VM and cloud). Vitest **56 passed, 1 skipped** (Mac VM; 79 + 1 skipped at 19:44 after another session added `tests/unit/visual-layers.test.ts`). Playwright (cloud, Chrome + SwiftShader, same sources and
  bundles): **29 passed, 6 failed**. The 6 failures are the same 6 tests that fail on the sources from before this pass (baseline run
  19:20: 22 passed, 6 failed): `decision-evidence.spec.ts:64`, `:91`, `real-and-fallbacks.spec.ts:11`, `science-v2.spec.ts:14`, `:42`, `:56`
  (they expect older panel text / test ids such as `display tally` in the ridge panel or `sun-az` on the Sky page). New: `penumbra.spec.ts`
  (7 tests, all pass): story numbers = sidecars; real-surface default + mode labels; no overlap at 1440×900; camera views under reduced
  motion; decision card + coverage = sidecars; fonts; ribbon a11y summary + table.
- **Performance (Mac M5 Pro, ANGLE Metal, 1440×900, DPR 2, 401² DEM + shadows, camera transition):** mean frame interval 8.4 ms, p95 9.2 ms,
  max 16.7 ms, heap 122 MB, FCP 176 ms. GPU memory not measured. 19:55 fix: the camera now re-frames when the site changes (the opening view switches the export from Site01 ROI6 to Site04 ROI3; the old camera could sit inside the new terrain and show black); built preview checked at 4173: terrain visible within 4 s.
- **Build:** `web/dist` rebuilt from these sources with `vite build --emptyOutDir=false` (the VM cannot delete files; stale hashed assets from
  older builds remain in `web/dist/assets` and are unreferenced). Rollback: `tmp/web_before_penumbra_20261114_1906.tgz`.

### Phase 2 — shared scientific/render contract (2026-11-14 19:45 EST, b-experience session A)

State checked first (19:39 EST): branch `b-experience` @ `8079924`, 113 dirty paths, nothing reset. The NAC download was
still 1,056 / 2,000 rows (`resume_2030.log` empty; the launchd resume is due ~20:30), so **no second downloader was
started**. Penumbra was still writing shared `web/` files (`App.tsx`, `styles.css`, `Scene3D.tsx`, `MarginRibbon.tsx`,
`VisibilityStrips.tsx`, last write 19:43:32), so **no shared `web/` file was edited**; only two new files were added there.

Delivered:
- `schemas/visual-layers-v1.schema.json` — `polaris-visual-layers-v1`: display rasters with `status: VISUAL`,
  `numericalAuthority: false`, artifact + source hashes, projection/frame, pixel-edge bounds, registration
  (`display-alignment-evidence-only`), display stretch, limitations. DEM fields are forbidden on a layer.
- `schemas/fixtures/visual-layers-cases.json` — one shared case file: 1 valid fixture, **20 invalid cases** (missing/incorrect
  VISUAL status, numerical-authority claim, unknown projection, wrong radius, unknown units, bad hashes, smuggled `values` /
  `verticalUnits`, inverted or mismatched bounds, unknown role, no limitations, registration called "validated", absolute
  path, wrong release status, duplicate ids) and solver-guard cases.
- Three validators with the same rules: `tools/sources/visual_layers.py`, `app/src/visual-layers.js`,
  `web/src/bundle/visualLayers.ts` (+ `layerCoverageOnCrop`).
- **Solver guards:** `blender/polaris_geometry.py` (`validate_dem`, `terrain_horizon`, `trace_visibility`) and
  `app/src/science.js` (`horizonProfile`, `terrainRayProfile`) now raise `VISUAL_LAYER_AS_DEM` when handed a visual layer.
  No numerical path changed for real DEMs. `app/dist/polaris-file.js` rebuilt (121,412,701 bytes, +466).
- `tools/sources/build_visual_layers.py` → `data/visual/visual_layers.json`; a window becomes a layer only when fully
  downloaded and registered over the full window. Nothing written yet (download incomplete). `--check` added to
  `test_all.command` `[sources]`.
- `tools/sources/check_nac_dem_registration.py` accepts `--image-tif` and records window, DEM and status.

Verification (Mac Linux VM; macOS-only steps not run here):
| Command | Result |
|---|---|
| `python3 -m unittest discover -s tools/sources -p 'test_*.py'` | **17 run, 15 pass, 2 skipped** (skips: jsonschema absent in system python; generated file not yet present). With the science env (jsonschema 4.26): 1 skip |
| `python3 -m unittest discover -s blender -p 'test_*.py'` | **21/21 pass** |
| `cd app && npm test` | **25 pass, 0 fail** (21 existing + 4 visual-layer/guard tests) |
| `web`: `tsc --noEmit` | clean (Penumbra in-flight tree + new files) |
| `web`: Vitest | **80/80 pass**, 10 files (57 existing + 23 new) |
| `web`: `vite build` | OK after installing Penumbra's three `@fontsource/*` packages in the test copy |
| `bash -n test_all.command` | syntax OK; full script **not re-run** since these edits |
| web Playwright, browser smoke, Blender CLI, 1512/1920/390 visual audit of Penumbra | **not run** (Penumbra still changing; macOS needed) |

Penumbra baseline seen (not mine, not edited): new deps `@fontsource/instrument-serif`, `inter-tight`, `jetbrains-mono`;
new `web/src/components/{Header,Story,DecisionCard,VisibilityStrips}.tsx`, `store/camera.ts`, `three/CameraRig.tsx`,
`bundle/coverageSidecar.ts`, `public/penumbra/*`, `public/certainty/coverage.json`, `tests/e2e/penumbra.spec.ts`,
`docs/screenshots/penumbra/`. Its tree type-checks, passes the 57 existing unit tests and builds.

Not done in Phase 2 (next, in order):
1. When the NAC window completes: verify 2000², hashes, full-window registration → `build_visual_layers.py` →
   Phase 1 complete, `visual_layers.json` exists.
2. Wire consumers to that one file: `web/scripts/sync-bundles.mjs` copies it + the PNG to `web/public/visual/`; the app's
   `build/file-entry.js` / `main.js` loads it. Only after Penumbra stops writing `web/src`.
3. Then the small Phase 5 preview: "LROC NAC AVG · VISUAL" surface layer on the 5 m mesh in `app/`, geometry and Sun unchanged.

## Penumbra Apex — 14 Nov 2026, 20:05–20:55 EST (Claude, Penumbra session)
Scope: `web/` only (React viewer). No science, solver or bundle change.
- Fixed: deep links to unlisted bundles silently loaded another bundle (5 failing tests); stale `real-and-fallbacks` test reordered (JPL angles live in Decision).
- Added: Certainty Height instrument in Explore (sampled heights only; 1 m/10 m switch the bundle series), Ridge of Record list + Inspect/Return with ribbon run outline, lighting toggle (display ≥ 0.5° vs true elevation) with on-screen tag (also in session A's `TerrainSurface.tsx`, one line), mast-eye camera fix, guided 5-scene demo, source tags (`bundle` vs `batch sweep`), coverage explanation, "realizations" wording.
- New files: `src/components/{MastInstrument,Guide}.tsx`, `src/store/ui.ts`, `src/bundle/ridgeSeek.ts`, `tests/e2e/apex.spec.ts`.
- Merged with session A's Phase 4/5 edits in `App.tsx`, `styles.css`, `three/Scene3D.tsx` (3-way merge, both kept; hashes checked before overwrite).
- Verification: tsc clean; Vitest 89 pass / 1 skip; Playwright 41/41 (cloud); `vite build` OK on the Mac; dev/preview parity checked in the Mac browser.
- Release artifacts in `tmp/` with SHA-256 in `docs/RELEASE_READINESS.md`. Docs: `PENUMBRA_FINAL_VISUAL_AUDIT.md`, `BROWSER_TEST_RECONCILIATION.md`, `SCIENCE_LABEL_AUDIT.md`, `PRODUCTION_PARITY.md`, `RELEASE_READINESS.md`.
- Not done: GPU frame rate on the Mac; Playwright on the Mac; commit/push (not authorized).

## Final visual-quality pass — 14 Nov 2026, 21:10–23:00 EST (Claude, Penumbra session)
Scope: `web/` only; no science, solver, bundle or DEM change. Explorer: Lunar-Lambert shading, DEM-marched cast shadows on the 5 m crop (once per sample, 1.1 ms on the M5 Pro), Display vs Scientific light modes named on screen, cross-lit Approach camera chosen from the bundle skyline, sight lines with skyline line, margin arc and bundle-valued labels (distant ridges labelled "beyond this crop"), one-line control row at 1440, compact instrument, Ridge of Record profile view with one camera move. Decision: hero = Decision Card + 1 m vs Certainty Height comparison + takeaways; tables, hashes and method in expandable sections; coverage warning visible.
Merged again with session A's edits made after 21:14 (Global Moon overlay, Moon button, 390 px header fix, its shading tweak): both kept except the shading lines, where the Lunar-Lambert model replaces the soft-knee curve (noted in REBUILD_PHASES). Hashes checked before writing; recovery copy `tmp/web_before_final_visual_2231.tgz`.
Verification: tsc clean (cloud + Mac); Vitest 89 pass / 1 skip; Playwright 51 pass, 1 skipped (by design), 0 failed of 52; dev = production screenshots (pixel-identical); Mac build OK. Not committed or pushed. Docs: sections appended to PENUMBRA_FINAL_VISUAL_AUDIT, RENDERING_VALIDATION, BROWSER_TEST_RECONCILIATION, PRODUCTION_PARITY, RELEASE_READINESS; screenshots `web/docs/screenshots/penumbra/final/`.

### Rebuild phases 1, 3–9 — 14 Nov 2026 20:00–22:20 EST (b-experience session A)

Clock note: the Mac's Linux VM clock lagged the real clock by up to ~20 minutes during this pass; times here are from the
cloud clock (UTC − 5). Release status unchanged: **SOURCE_BASED_UNVALIDATED**. Nothing reset, committed or pushed.

Concurrency: the Penumbra "Apex" session edited `web/` 20:05–20:55 and merged with this session's `App.tsx`,
`styles.css`, `Scene3D.tsx` changes (its note above). Its tree was the baseline for everything after 21:00.

| Phase | Status after this pass | Evidence |
|---|---|---|
| 0 | Done | earlier section |
| 1 Source registry + texture | **Complete** | registry 12/12 hashes; LROC window 2000×2000 complete; full-window registration; `visual_layers.json` generated |
| 2 Shared contract | **Complete for visual layers**; consumers wired in `web/` (app loader not wired: `app/` has no image layer UI) | contract tests in three languages; web e2e |
| 3 One application shell | **Decided and partly done**: `web/` is the shell (Penumbra's `FRONTEND_SOURCE_OF_TRUTH.md`); the global Moon now exists in it. `app/` remains as the legacy direct-file viewer; its 8K topographic globe and stress-test panels are not ported | `GlobalMoon.tsx`, e2e |
| 4 Multiscale terrain | **Partly done**: two static levels (5 m crop + 80 m regional crop) with a cut-out and skirt. No clipmap/quadtree, no intermediate ring, no per-tile culling | screenshots `rebuild/explore-*` |
| 5 Material, shadows, lighting | **Done for the display model**: registered LROC albedo on Site01, neutral regolith elsewhere, horizon-map shadows without a shadow-map rectangle, debug layers. No DEM-derived normal maps or micro-normal detail; uncertainty layer not available in these bundles | screenshots; e2e |
| 6 Camera-led experience | **Done in `web/`**: Moon → South-pole context → Approach / Regional / Mast-eye / Ridge of Record / Overhead (the last five are Penumbra/Apex's) | e2e "global Moon"; Apex tests |
| 7 4D / 5D | Unchanged by this pass (Penumbra/Apex: timeline, events, mast heights, scenarios). Deep link still only `?bundle=` + workspace hash | — |
| 8 Blender parity | **Prepared, not run**: builder gained the display-only regional context; `rebuild_blender_hero.command` builds Site04 ROI3 from the ROI export (401² 5 m crop, derived ray states). Blender is not available in the VM (Linux aarch64) | `blender/` tests 25/25; no new `.blend`/GLB/render |
| 9 QA, performance, packaging | **Partly done**: all unit suites and cloud Playwright pass; Mac-only checks, Mac GPU timing and the release ZIP are not done | table below |

#### Phase 1 completion evidence
- Download finished 22:04 EST with 15 block requests of 50 rows (`--block-rows 50 --threads 1 --pause-s 2`; no HTTP 429).
  History: 1,056 rows (12 threads, then 429), 230 rows (launchd job at ~20:30, then stopped), 714 rows (block requests).
- Products in `data/visual/lroc_nac_pole_south_cm_avg/`:
  - `site01_center_2km_1m_8bit.png` 2000×2000, 8-bit grey, SHA-256 `8ff9a6248a2614838b20aa361c12c7ede0f871aaa6200a4b06ab3105687ef5e4`, no no-data pixels;
  - `site01_center_2km_1m_f32.tif` 2000×2000 float32, origin (−12000, −11000), 1 m, north-up, bounds x −12000…−10000 / y −13000…−11000,
    SHA-256 `e2cee071d519dcbe3b10896b7b81065859097cd6c6fa3751b25958c5937db3c1` (git-ignored copy);
  - `site01_center_2km_manifest.json`: raw window SHA-256 `35ef3b5805cdee4e43f3a8d23066a165d3f4bce8aceafbeb74005e759d4be991`
    (re-computed from the row file and equal; GeoTIFF pixels equal the raw window), samples 33489–35488, lines 11001–13000,
    valid fraction 1.0, value range 0.0144–1.087, display stretch 0.0224–0.4409 (0.5–99.5 percentile).
- **Full-window registration** against the PGDA 78 Site01 5 m DEM (160,000 5 m pixels):
  image shift **x −6.01 m, y +1.15 m**, peak NCC **0.416** (0.374 at zero shift), search ±60 m, peak not at the edge.
  `site01_center_2km_registration.json`. Display-alignment evidence only; not a validation of either product.
  No shift is applied in the renderer (`appliedShiftM` 0, 0).
- `data/visual/visual_layers.json`: one layer `lroc-nac-avg-site01-center-2km` (`LROC NAC AVG · VISUAL`). It covers 100 % of the
  Site01 site-centre crop and 78 % of the Site01 ROI6 crop; Site04 has no registered image (not downloaded).
- The VM cannot delete files: the finished `.partial`, `.rows`, the north-half registration and the empty resume log were moved
  to `tmp/_to_delete/` (git-ignored). The fetch script now tolerates a failed cleanup.

#### What was built (files)
- `tools/terrain/terrain_context.py`, `build_terrain_context.py`, `test_terrain_context.py`: display-only regional copy and
  horizon maps → `data/visual/terrain_context/{site04_roi3,site04_roi4,site01_roi6,connecting}/` (≈ 4.5 MB each, ~15 s each).
- `web/src/bundle/terrainContext.ts`, `web/src/three/TerrainSurface.tsx`, `web/src/three/GlobalMoon.tsx`,
  `web/src/store/surface.ts`, `web/src/components/SurfaceLayer.tsx`; edits in `Scene3D.tsx` (context loading, far plane,
  log depth, `preserveDrawingBuffer` off, globe overlay), `HorizonDome.tsx` (`preserveDrawingBuffer` off), `App.tsx`
  (Moon button, layer picker, chip), `store/camera.ts` (`context` view), `styles.css`, `scripts/sync-bundles.mjs`.
- `app/src/scene.js`, `app/src/pro.js`, `app/tests/browser_smoke.py`: `preserveDrawingBuffer` off with a render-then-read capture;
  `app/dist/polaris-file.js` rebuilt (121,412,765 bytes).
- `blender/bundle_v2.py` (`context_regional_dem`), `blender/build_from_nasa_bundle.py` (`--context-dir`, context mesh, manifest
  `regionalContext`), `blender/test_bundle_v2.py` (+4 tests), `rebuild_blender_hero.command`.
- `tools/sources/fetch_lroc_nac_crop.py` (`--block-rows`), `build_source_registry.py` (display-only files), `test_all.command`
  (`[terrain]` step), `package_release.command` (adds `data/` display and bundle files, the hero command; excludes float32/partials).

#### Verification actually run
| Check | Where | Result |
|---|---|---|
| `python3 -m unittest discover -s blender -p 'test_*.py'` | Mac VM | **25/25 pass** |
| `python -m unittest discover -s tools/sources -p 'test_*.py'` (science env) | Mac VM | **18/18 pass, 0 skipped** (2 skipped with system python: no jsonschema) |
| `python -m unittest discover -s tools/terrain -p 'test_*.py'` | Mac VM | **7/7 pass** |
| `build_source_registry.py`, `build_visual_layers.py --check` | Mac VM | 12/12 documented hashes match; layers file valid and current |
| `cd app && npm test` | Mac VM | **25 pass, 0 fail** |
| `web`: `tsc --noEmit`, Vitest, `vite build` | Mac VM | clean; **90/90 pass** (11 files); build OK, copied to `web/dist` |
| `web`: Playwright, all 10 spec files | cloud, headless Chrome + SwiftShader | **49 passed, 0 failed, 0 skipped** (run in four parts: 13 + 28 + 7 + 1) |
| app capture path | cloud | context attribute `preserveDrawingBuffer` false; `render()` then `toDataURL` gives a 1.46 MB PNG; no page errors |
| `bash test_all.command`, `app/tests/browser_smoke.py`, Playwright on the Mac | — | **not run** after these edits (need the Mac host) |
| Blender CLI build, GLB re-import, renders | — | **not run** (no Blender in the VM) |
| Mac GPU frame time / memory with the context terrain | — | **not measured** (browser pane access was not granted while the user was away) |
| Release ZIP | — | **not rebuilt**; `dist/POLARIS-X5D-SourceBuild-Mac.zip` is the 13:40 build and is stale |

#### Evidence screenshots (cloud, software GL; layout and content evidence, not GPU evidence)
`web/docs/screenshots/rebuild/`: `explore-approach-regolith-1512x982.png`, `explore-context-{regolith,elevation,slope,coverage,shadow}-1512x982.png`,
`explore-context-regolith-sample7-1512x982.png`, `explore-mobile-390.png`, `global-moon-site-marker-1512x982.png`,
`site01-roi6-lroc-nac-avg-visual-1440x900.png`. (If some are missing or older: the Mac went offline while they were being copied
at 22:16; re-run `npx playwright test tests/e2e/terrain-context.spec.ts` on the Mac to regenerate all of them.)

#### Exact next steps on the Mac (in order)
1. `bash test_all.command` (now also runs `[sources]` and `[terrain]`).
2. `cd web && npm install && npm run build && npx playwright test` (Mac Chrome).
3. `cd app && ../.venv/bin/python tests/browser_smoke.py --screenshot`.
4. `bash rebuild_blender_hero.command` → check `blender/output/POLARIS_X_site04_roi3_bundlev2_scene_manifest.json`:
   `derivedOutputsPresent: true`, `dem.meshVerticesPerAxis: 401`, `regionalContext.n: 401`; look at the three renders.
5. `bash package_release.command` and record the printed SHA-256 here.

#### Limits that remain
- Shadows in the 3D view are a display model (horizon maps of the displayed crops + bundle skyline for farther terrain).
  They never set a visible/blocked state. Terrain between the crop edge and the solver's 280 km reach is represented only
  through the bundle skyline at the observer.
- The LROC image is an average of 18,323 images: display only, baked shading, not mission-time lighting.
- No independent illumination validation was performed. PGDA 69 stays a reference layer.

#### Follow-up, 14 Nov 22:50–23:00 EST (session A, after the Mac came back online)
- Penumbra's final visual pass (its section above) merged this session's 21:05–22:10 edits and replaced the soft-knee shading
  lines in `TerrainSurface.tsx` with its Lunar-Lambert model. Session A did not edit `web/src` again.
- Re-baseline of the merged tree (Mac VM): `tsc` clean; Vitest **90/90**; `vite build` OK and copied to `web/dist`
  (contains `context/`, `visual/`, `globe/`); Blender/geometry 25/25; source tools 18/18; terrain tools 7/7; app 25/25.
  Playwright on the merged tree: Penumbra reports 51 passed / 1 skipped of 52 (cloud); not re-run by session A.
- Screenshots `global-moon-site-marker-1512x982.png` and `site01-roi6-lroc-nac-avg-visual-1440x900.png` are in
  `web/docs/screenshots/rebuild/`. They show session A's shading from before Penumbra's replacement; the other
  `explore-*` files there are from 21:34 or earlier. Regenerate all with `npx playwright test tests/e2e/terrain-context.spec.ts`.
- **Interim release archive:** `dist/POLARIS-X5D-SourceBuild-Mac-20261114-2255.zip`, 259,193,368 bytes, 670 files,
  SHA-256 `d4179023879c0bc9752dd1ead05065286051e9a84d171b70d263a4e23d76474e`. Built in the VM by `package_release.command`
  (zip integrity test passed; key files checked present; no float32 copy, partial download, `node_modules` or `.venv` inside).
  It is **interim**: it was built before the Blender hero rebuild and before `test_all.command`, the browser smoke test and
  Playwright were run on the Mac host, and it contains this file as it was just before this note. The older
  `dist/POLARIS-X5D-SourceBuild-Mac.zip` (13:40) was left in place and is stale.

#### Final Mac gate, 14 Nov 22:50–22:56 EST (Codex continuation)

The merged source tree was quiet after Penumbra's 22:31 write before this gate began. Nothing was reset, committed or
pushed. Release status remains **SOURCE_BASED_UNVALIDATED**; these checks establish reproducibility and rendering, not
independent scientific validation.

| Check | Mac result |
|---|---|
| `bash test_all.command` | **pass**: Blender/geometry 25/25; ingest 6/6; app 25/25; source tools 18/18; terrain tools 7/7; schemas, bundle hashes and direct-file build pass |
| `cd web && npm install && npm run build` | **pass**; production bundle rebuilt from the merged source tree; npm reported 0 vulnerabilities |
| `cd web && npm test` | **89 pass, 1 intentional skip**; the optional full-bundle test skips because canonical `data/bundles/site01_2026-11-14_14d.json` is absent; no applicable test failed |
| `cd web && npx playwright test` | **52/52 pass** in native macOS Chromium, including terrain context, LROC visual layer, global Moon, time/scenarios, deep links, accessibility and 390 px layout |
| `cd app && ../.venv/bin/python tests/browser_smoke.py --screenshot` | **pass**: localhost and direct-file model, source cache, full bundle, clone selection and global Moon; screenshots regenerated |
| `bash rebuild_blender_hero.command` | **pass** in Blender 5.3.0; Site04 ROI3 uses the full 401 x 401, 5 m DEM plus the 401 x 401, 80 m display-only context; start/mid/end renders written |
| GLB clean-scene re-import | **pass**: 7 objects, 6 meshes, 1 light, 323,778 vertices and 641,068 polygons |

Fresh Blender hero artifacts:
- `.blend` 8.9 MiB, SHA-256 `50baa8ec016c9d200bc2cd2f3caefbb4bfc29664a6ec9f926b9ac2e479a557a1`;
- `.glb` 11 MiB, SHA-256 `3d59329c1a0ca735420f76ddbc16d56a9204d578393ff537f29d115980c06db2`;
- scene manifest SHA-256 `94f88753f21e44261405699e7f2546e9e588000ae0a788fa0793dcbbc5fd0986`.

The manifest records `derivedOutputsPresent: true`, 1:1 vertical scale, frame 1 =
`2026-11-14T00:00:00Z`, frame 169 = `2026-11-21T00:00:00Z`, and frame 337 =
`2026-11-28T00:00:00Z`. The three inspected renders show the same bundle ray states recorded in the manifest. The neutral
Site04 Blender material remains visibly softer and more patchy than the React presentation, especially at the local/regional
transition; this is a visual-quality limitation, not hidden as a science result. The React viewer is the product shell and
shows the actual terrain, while Blender remains an editable authoring/evidence artifact.

Final release archive (built after the gate above):
- `dist/POLARIS-X5D-SourceBuild-Mac.zip`, 275,282,673 bytes, 646 entries;
- SHA-256 `5f6294bb7b5e05e9e373100fe78e944a2e1b02996a48905905dc57df238f59c2`;
- `unzip -tq` reported no errors; required web, Moon, texture, terrain-context, registry and Blender hero files were checked
  present; no `node_modules`, `.venv`, partial/row download or `_f32.tif` display working copy is included;
- external checksum file: `dist/POLARIS-X5D-SourceBuild-Mac.zip.sha256`.

#### Mac-host verification by Anish (Terminal), 14 Nov 2026 late evening (recorded by session A from the pasted output)
- `bash test_all.command` → **"POLARIS X checks passed."** Geometry/Blender pure-Python **25/25**; NASA/JPL ingest **6/6**;
  direct-file build OK (`dist/polaris-file.js` 115.8 MB); app **25 pass, 0 fail, 0 skipped**; Python syntax OK; 4 v2 bundles,
  both NASA SVS GLBs and the PGDA 69 layer validated; `[sources]` **18/18, 0 skipped**; `[terrain]` **7/7**.
  (An earlier run in the same Terminal, before the Blender/terrain additions, showed 21 geometry tests and sources 17 with 1 skip.)
- `cd web && npm install && npm run build && npx playwright test` → build OK (645 modules; `Scene3D` chunk 1,032 kB);
  **Playwright 52 passed, 0 failed, 0 skipped** in 1.1 min on the Mac (9 workers), including all 8 `terrain-context.spec.ts`
  tests (the Site01 `LROC NAC AVG · VISUAL` check and the global Moon) and Penumbra's `visual-final.spec.ts`.
- `browser_smoke.py`: **not run yet.** The command was typed inside `web/`, so `cd app` failed. From `web/` use
  `cd ../app && ../.venv/bin/python tests/browser_smoke.py --screenshot`.
- Still not run: `bash rebuild_blender_hero.command`, final `bash package_release.command`. Mac GPU frame time not measured.

#### Phase 8 — Blender hero build has run (found 14 Nov ~23:15 EST; built on the Mac at 22:53 EST, Blender 5.3.0)
`blender/output/POLARIS_X_site04_roi3_bundlev2.{blend,glb}`, `_scene_manifest.json`, start/mid/end renders, log
`rebuild_hero_site04_roi3.log` (the output of `rebuild_blender_hero.command`; session A did not start it).
- Manifest: status `SOURCE-BASED UNVALIDATED`; `derivedOutputsPresent: true`; `dem.meshVerticesPerAxis: 401` (full 5 m crop);
  `regionalContext`: PGDA 90 80 m, 401², VISUAL, numericalAuthority false, 529 nodes lowered 40 m under the local footprint (visual cut).
- Hashes: `.blend` `50baa8ec016c9d200bc2cd2f3caefbb4bfc29664a6ec9f926b9ac2e479a557a1`,
  `.glb` `3d59329c1a0ca735420f76ddbc16d56a9204d578393ff537f29d115980c06db2`; bundle `5b93dd66…9cf51f`.
- **Web parity at the start frame (2026-11-14T00:00:00Z, sample 0):** Blender manifest Sun az 282.93° el 1.606° ray `clear`, margin
  +3.386°; Earth az 155.09° el −4.848° ray `blocked` (first hit 10 m), margin −4.167°. The React viewer at the same sample shows
  Sun az 282.9° el +1.61° Visible, margin +3.39°; Earth az 155.1° el −4.85° Blocked, margin −4.17°. Same bundle values in both.
  Mid (2026-11-21T00:00Z) and end (2026-11-28T00:00Z): both rays `clear` in the manifest; not compared on screen in the viewer.
- Start render inspected by session A: the lit 5 m crop on the rim, the regional context continuing into shadow, Sun ray from the
  observer. Honest limits: no transition frame was rendered; the GLB was not re-imported; the world still has a dim grey fill;
  no registered albedo in Blender (neutral elevation-ramp material); composition was not tuned.

#### Phase 9 — final Mac-host checks and release archive (Anish, Terminal, 15 Nov 2026 ~00:05 EST)
- `cd app && ../.venv/bin/python tests/browser_smoke.py --screenshot` → **"Browser smoke passed: localhost and direct-file
  models, source cache, full bundle, and clone selection."** Wrote `app/docs/browser-source-case.png`,
  `app/docs/visual-audit/after-1512x982.png`, `after-1920x1080.png`, `app/docs/browser-global-moon.png`,
  `app/docs/browser-file-launch.png`. This is the first smoke run with `preserveDrawingBuffer` off (render-then-read capture).
- `bash package_release.command` (one earlier attempt was interrupted with Ctrl-C, "zip error: Interrupted (aborting)"; the
  rerun completed) → **`dist/POLARIS-X5D-SourceBuild-Mac.zip`, 275,232,626 bytes (273 MB), 646 entries, SHA-256
  `634551699b661ccf0bc49cf64c47408977d55da3c8b0951684e4102fe63c6f77`**. Session A verified: zip integrity test passes; it
  contains the Site04 ROI3 Blender hero `.glb` + manifest, `web/dist/visual/visual_layers.json` and `data/source_registry.json`.
  `dist/POLARIS-X5D-SourceBuild-Mac.zip.sha256` updated to this value. The 22:55 interim archive
  (`…-20261114-2255.zip`) is superseded; it can be deleted.
- This archive contains `docs/BUILD_STATUS.md` as it was before this paragraph.

**Rebuild verification summary (all on the Mac host unless noted):** `test_all.command` passed (geometry 25, ingest 6, app 25,
sources 18, terrain 7, schemas/GLBs/PGDA 69); web Playwright 52/52; browser smoke passed; Blender 5.3.0 hero build with
derived ray states matching the viewer at the start sample; release archive built. Not done: Mac GPU frame-time measurement,
Blender transition-frame render and GLB re-import, clipmap/quadtree LOD, URL state for time/scenario/camera, independent
illumination validation. Release status: **SOURCE_BASED_UNVALIDATED**.


### Five remaining items — 15 Nov 2026 00:00–01:05 EST (session A)
Release status unchanged: **SOURCE_BASED_UNVALIDATED**. Nothing reset, committed or pushed.

| Item | State | Evidence |
|---|---|---|
| GPU frame time on the Mac | **Measured in the desktop browser pane (Metal); Chrome run scripted, not run** | `web/docs/perf/mac-browser-pane-2026-11-15.json`: idle 8.33 ms mean, p95 9.3 ms (120 Hz). Found and fixed a stall: drei `<Line>` relinked 2 shader programs and made 70 buffer allocations per time step (0.8–1.0 s hitch). New `web/src/three/StableLine.tsx` updates buffers in place: 0 links, 0 allocations per step, p95 9.2 ms. Remaining cost per step is the React render (~52–57 ms). The pane adds its own ~1 s pause after any task > 50 ms (reproduced with a synthetic task), so clean numbers need `npm run perf:mac` (`web/scripts/perf_mac.mjs`, headed Chrome with ANGLE Metal) |
| Blender transition frame + GLB reload | **Code done and tested (28/28); Mac rerun needed** | `bundle_v2.transition_sample` / `key_samples_with_transition` add a render at the first Sun (else Earth) visibility change — Site04 ROI3: sample 311, 2026-11-26T22:00Z→23:00Z, Sun. `blender/glb_check.py` reads the GLB without Blender; the builder re-imports the GLB in a factory-reset Blender and records `glbReimport` (mesh count, DEM/context vertex counts) in the manifest. Checked on the existing hero GLB: DEM and context 160,801 vertices each |
| Multi-level terrain | **Three levels in `web/`** | L0 5 m crop (401²), new **L1 20 m ring** (401² block means of the PGDA 78 5 m tile, ±4 km, equal to the 5 m means to 0.000 m), L2 80 m regional (±16 km). Each coarser level is cut out under the finer one with a skirt; the shadow march walks L0 → L1 → L2; coverage layer shows three tints. Packs rebuilt (`mid_f32.bin`, `mid_horizon_u8.bin`; 30 MB total). Site04 needed `Site04_final_adj_5mpp_surf.tif` (SHA matches the registry). Still no clipmap/quadtree streaming; Blender still uses L0 + L2 |
| Time, scenario, camera in the link | **Done** | `web/src/store/urlState.ts`: `?bundle=&site=&t=&sc=&cam=&layer=`; applied once after the first bundle load, written back with `replaceState`; a time outside the bundle is refused ("never extrapolates"). Unit 3/3, e2e 3/3 |
| Independent illumination validation | **Run against NASA SVS 4930 with a pre-registered protocol: PASS, low discriminating power** | `docs/validation/SVS4930_RESULT.md`. 331 compared samples, agreement 1.00, but no shadow case was tested. Not a validation of POLARIS; label unchanged |

Verification run in this pass: web `tsc` clean, Vitest **93/93** (12 files), `vite build` OK (Mac VM copy); cloud Playwright
`terrain-context` + `url-state` **10/10**; Blender unit tests **28/28**; terrain tools tests pass; context packs rebuilt with no NaN nodes.
Not run here: full Playwright on the Mac, `test_all.command`, Blender rebuild, `perf:mac`, packaging. The release ZIP
(SHA `634551…6f77`) predates this pass and is stale.

Mac commands, in order (from the project folder):
1. `bash test_all.command`
2. `cd web && npm run build && npx playwright test && npm run perf:mac && cd ..`
3. `bash rebuild_blender_hero.command` → manifest `glbReimport.ok: true` and a `transition` render
4. `bash package_release.command` → record the SHA-256 here.

#### Mac run by Anish, 15 Nov 2026 ~01:10 EST (recorded by session A from the pasted Terminal output)
- `bash test_all.command`: **passed** — Blender/geometry **28** (incl. the 3 new GlbAndTransition tests), ingest 6, app 25,
  sources 18, terrain 7, schemas/GLBs/PGDA 69.
- `cd web && npm run build && npx playwright test`: build OK; **62 passed, 3 failed** of 65 (9 workers):
  `penumbra.spec.ts:108` (ribbon table had 0 rows 5 s after opening), `visual-final.spec.ts:24` (Earth sight label hidden on Approach),
  `visual-final.spec.ts:43` (Sun sight label still shown 5 s after Mast-eye was pressed). The sight labels are moved by a per-frame
  callback, so these look like frame starvation under 9 parallel WebGL workers (Penumbra's new guided-demo specs run 40–80 s each).
  Session A ran the same two spec files in the cloud on the Mac's current `src/`, `tests/` and bundles: **10/10 pass**.
  Needs a confirming rerun on the Mac with one worker.
- Because the chain used `&&`, `npm run perf:mac` did not run; `rebuild_blender_hero.command` and `package_release.command` were run from
  `web/` and were not found. Blender rebuild, perf numbers and the new release ZIP are still outstanding.

#### Mac run by Anish, 15 Nov 2026 01:20–01:25 EST — all outstanding steps done (recorded by session A)
- **Playwright rerun, one worker** (`penumbra.spec.ts`, `visual-final.spec.ts`): **10/10 pass** (23 s). The three 01:10 failures were
  parallel-load timing, not regressions. Full-suite tally: 62 + these 3 = all 65 tests have passed on the Mac.
- **`npm run perf:mac`** → `web/docs/perf/mac-chrome-2026-11-15.json` (Chrome 157, ANGLE Metal, Apple M5 Pro, 3024×1852 canvas):
  idle, camera moves, time steps and playback all at **33.3 ms mean, p95 ≤ 34.3 ms, max 34.3 ms; 0 long tasks** during time steps
  and playback; first model visible 1.69 s; JS heap 55 MB. Every interval sits at 33.3 ms, so Chrome was capped at 30 fps (likely
  Chrome Energy Saver or macOS Low Power Mode; the Mac was on battery). This shows no dropped frames at the cap, including on time
  steps (the old ~1 s hitch is gone); it does not measure GPU headroom. The browser-pane run (120 Hz, idle p95 9.3 ms) is the uncapped figure.
- **`rebuild_blender_hero.command`** (Blender 5.3.0): four renders — start (frame 1), mid (169), **transition (frame 312, 2026-11-26T23:00Z:
  Sun clear → blocked between 22:00 and 23:00, first hit 16 m, bundle margin −0.04°; not refined)**, end (337). PNG SHA-256 of the
  transition render `9a6a02ce…0d20`. **GLB re-import: PASS** (same mesh count, DEM and context 160,801 vertices each, unchanged).
  Bundle SHA-256 `5b93dd66…cf51f`; status SOURCE-BASED UNVALIDATED.
- **`package_release.command`** → **`dist/POLARIS-X5D-SourceBuild-Mac.zip`, 304,866,066 bytes, SHA-256
  `0a7c4044285fe56731a7ebc1decf75954c394889f1ef562f002e75975dcdc134`**. Session A: zip integrity test passes; contains the transition
  render, the SVS 4930 protocol/result, the four `mid_f32.bin` packs and the Chrome perf JSON. `.sha256` file updated.
  The 22:55 interim archive (`…-20261114-2255.zip`) is still in `dist/` and can be deleted.

**State of the five items:** GPU frame time — measured (pane uncapped; Chrome capped at 30 fps, no drops). Blender transition frame
and GLB reload — done and passing. Multi-level terrain — 5 m / 20 m / 80 m in `web/` (no streaming LOD; Blender has 5 m + 80 m).
Link state — done. Illumination comparison — SVS 4930 run, PASS, low discriminating power. Release status: **SOURCE_BASED_UNVALIDATED**.

#### Repackage, 15 Nov 2026 01:35 EST (Anish)
`bash package_release.command` → **`dist/POLARIS-X5D-SourceBuild-Mac.zip`, 310230478 bytes, SHA-256
`ae12105e1e689e0f736c9b4f76e1f8784d84604fba36ffdac21d30e8877a7a5d`** (supersedes `0a7c4044…c134`; picks up docs written at 01:30 and
Penumbra's edits to that time). Integrity test passes; `.sha256` updated. `npm run perf:mac` was run from the project root (no
`package.json` there) and did not run; the 01:22 Chrome result stands.

#### `perf:mac` second run, 15 Nov 2026 01:37 EST (Anish) and a script fix (session A)
Same result as 01:22: every interval ≈ 33.3 ms (idle p95 33.8 ms; camera to South-pole context mean 35.2 ms with **one 167 ms frame** —
the first switch to that view builds the context terrain (now including the 20 m ring), a one-off hitch not seen at 01:22; playback p95 34.0 ms; time steps max 34.3 ms; 0 long tasks; first model 1.1 s; heap 55 MB). The Mac was on battery with a low
charge, and Chrome's Energy Saver caps animation at 30 fps then, even in a fresh profile. `web/scripts/perf_mac.mjs` now starts Chrome
with `--disable-features=BatterySaverModeAvailable,HighEfficiencyModeAvailable` and writes the power source (`pmset -g batt`) and
macOS Low Power Mode into the JSON. An uncapped Chrome figure still needs a rerun on mains power.

## Penumbra session · Final Apex directive (15 Nov 2026, 00:33–02:25 EST)
Summary and phase table: `docs/FINAL_APEX_AUDIT.md`. Changed in `web/` (merged with session A's concurrent work; hash-checked before every write):

| Area | Files |
|---|---|
| Cold launch | `src/bundle/bootIndex.ts` (new), `App.tsx` `coldLaunch()` + failure panel, `store/store.ts` `loadRetry`, `vite.config.ts` and `playwright.config.ts` bound to 127.0.0.1 |
| Guided demo | `components/Guide.tsx`: snapshot/restore, full per-scene state, Play/Pause, Evidence link, focus |
| Decision | `DecisionHero.tsx`: three heights, coverage beside the verdict; `DecisionCard.tsx`: 1.75 m figure, coverage line with the < 50 % warning |
| Evidence | `EvidenceRecord.tsx` (new): pipeline, "Not validated yet", dataset record |
| Sky | `HorizonWheel.tsx` (new) |
| 3D labels | `three/Scene3D.tsx`: azimuth/elevation; flip away from the instrument, with cached layout reads |
| Layout | `styles.css`: breadcrumb hidden below 1700 px, mobile overlays, bottom tab bar under 640 px; Reset view button |

Tests:
- New: `tests/unit/{bootIndex,shadow-orientation}.test.ts` and `tests/e2e/{cold-launch,guided-demo,final-apex}.spec.ts`.
- `apex.spec.ts`: one longer time limit, assertions unchanged.

Docs:
- New: `docs/{COLD_START_AND_PARITY,GUIDED_DEMO_VERIFICATION,SCIENTIFIC_RESULT_CONSISTENCY,FINAL_VISUAL_QA,PERFORMANCE_REPORT}.md`.
- `RENDERING_VALIDATION.md`: correction of the 1.08 ms shadow-pass claim.

Results: see RELEASE_READINESS (15 Nov). Scratch left in `tmp/`: `b3chk/` (an extracted copy used for a diff; this session cannot delete it).

### Terrain upgrade: NASA GSFC shape-from-shading relief, web + Blender — 15 Nov 2026 01:45–03:00 and 16:45–17:10 EST (session A)
Release status unchanged: **SOURCE_BASED_UNVALIDATED**. Nothing reset, committed or pushed. Project doc: `claude/TERRAIN_SFS_2026-11-15.md`.

- **Source:** NASA GSFC SfS models for the Artemis III candidate regions (Bertone, McKenna, Barker, Mazarico, Beyer, Petro 2025;
  Zenodo doi:10.5281/zenodo.17954508; CC-BY-4.0). Region 6 "Connecting Ridge", 5 m, same polar-stereographic lattice as PGDA 78.
  Covers Site01 ROI6 / Site01 centre fully and Site04 ROI3/ROI4 on the west ~34 % only. `app/data/source/gsfc_sfs_a3clr22/`.
- **Packs** (`tools/terrain/build_terrain_context.py`): `local_display_f32.bin` = (1 − w)·LOLA + w·SfS, w feathered over 200 m at the SfS
  edge; L1 ring (401² @ 20 m) built from the same blend. An 801² @ 10 m ring was tried and reverted (too slow to start; crashed test pages).
  SfS minus the solver crop: Site01 ROI6 1.20 m rms, **+1.97 m at the site point**; Site01 centre 1.13 m rms, +0.45 m; Site04 ~1.0 m rms.
- **Web:** relief on by default, "NAC relief" toggle (`surface-detail`), chip says DISPLAY ONLY + source + coverage + rms + "fine grain is
  synthetic"; display mesh shifted by a constant to meet the bundle ground at the observer (same shift on L1/L2); synthetic sub-5 m grain on
  the shading normal (Display mode only); fast typed-array grid meshes. `tests/e2e/sfs-relief.spec.ts` (new).
- **Blender:** `--surface sfs|lola` (default sfs); 5 m crop drawn from the SfS display surface where present, L1 ring added, 80 m context cut
  under the ring; same constant shift; new regolith material (albedo ~0.12, synthetic albedo variation + micro-bump, no specular); extra
  low cross-lit hero render; manifest `displaySurface`, `midRing`. `rebuild_blender_hero.command` passes `--surface` (env `SURFACE`), 64 samples.
- **Verified:** Mac VM `tsc` clean, Vitest 99/99; Blender unit tests **31/31** (3 new). Cloud Playwright on software GL: url-state 3/3 with the
  relief off; with it on, frames go 1.5 s → 2.25 s on SwiftShader and two tests time out (Site01 toggle test; url-state reload). Mac GPU run needed.
  **Not run:** Blender (needs the Mac), full Mac Playwright, perf, packaging. The Blender script changes are untested inside Blender.
- **Rules kept:** SfS relief, ring, grain and material are display only; rays, states, margins and every number come from the bundle (LOLA crop).

#### Mac run by Anish, 15 Nov 2026 ~17:05 EST, and fixes (session A, 17:25)
- `rebuild_blender_hero.command site01_roi6`: SfS display surface on 100 % of the crop (shift −1.97 m), L1 ring and 80 m context drawn,
  five renders incl. transition frame 63 and `hero_low`; **GLB re-import PASS**. Site04 ROI3: SfS on 34 % (shift 0.00 m), same checks PASS.
- Playwright `--workers=4`: **77 passed, 2 failed**: both phone-width (390 px) overflow by 10 px, caused by the new "NAC relief" button.
  Fixed in `styles.css` (toggle styled inside the display cluster; cluster wraps under 760 px); both tests pass in the cloud.
- Render review: grey sky in `hero_low` (the world fill light was visible to the camera), low hero framed mostly into shadow, surface soft.
  Fixed: camera rays see black space (Light Path mix), hero camera moved to the Sun side 40° off the Sun azimuth, finer/stronger synthetic
  micro-bump, 128 samples. Blender unit tests 31/31. **Needs a Blender rerun.** Release ZIP not rebuilt (still `ae12105e…7a5d`).

#### 17:20–17:45 EST (session A)
- Anish's 17:17 Blender rerun of Site01 ROI6: black sky fixed (fill light no longer visible to the camera), transition render frame 63
  reads well; `hero_low` still dark → +1 stop exposure for that view only (needs one more Blender run).
- Anish's 17:20 Playwright run of `final-apex` + `terrain-context` used a reused 17:11 `dist/` (`reuseExistingServer: true`), so the
  390 px fix was not in it. It also showed a real 1440 px fault: once the relief toggle appears, the layer picker ends 91 px past the
  camera row. Fix: the **"NAC relief on/off" toggle moved onto the surface chip** in the stage title (out of the camera row); stage title
  may be up to 700 px wide at ≥ 1100 px so the chips stay on one line above the light line. Cloud: 390 px tests pass; 1440 and 1180 px
  layouts measured (picker right = camera-row right; chip bottom above the light line; page width = viewport).
  Mac VM: `tsc` clean, Vitest 99/99; Blender unit tests 31/31. **Rebuild before Playwright** (`npm run build`) or the old dist is served.

#### Mac run by Anish, 15 Nov 2026 ~17:50–17:59 EST — terrain upgrade verified
- `npm run build && npx playwright test --workers=4`: **79 passed, 0 failed** (includes `sfs-relief`, phone-width and 1440 layout tests).
- `rebuild_blender_hero.command site01_roi6`: SfS display surface 100 % (shift −1.97 m), L1 ring + 80 m context, five renders,
  **GLB re-import PASS**; `hero_low` now readable (+1 stop). Remaining look limit: close views are soft because the relief is 5 m data.
- `package_release.command` → **`dist/POLARIS-X5D-SourceBuild-Mac.zip`, 373,117,372 bytes, SHA-256
  `8b66e3322c96656612de9d6414649abddfa6416cece119a4612a81070b2e7dcd`**; integrity OK; `.sha256` updated. Contains the Site01 ROI6 and Site04
  ROI3 Blender scenes and the context packs with `local_display_f32.bin`. The raw SfS GeoTIFF (`app/data/source/gsfc_sfs_a3clr22/`) is not
  in the ZIP (source data; re-download from Zenodo 17954508).
Release status: **SOURCE_BASED_UNVALIDATED**.

#### Site01 ROI6 as the opening site (Sid, 15 Nov 2026 18:15 EST; session A)
- **Blender:** `rebuild_blender_hero.command` now defaults to `site01_roi6` (`site04_roi3` as an argument).
- **Web:** new `src/store/siteDefaults.ts`. In the ROI export, **Explore opens on Site01 ROI6** (full NASA GSFC SfS relief); **story,
  Decision, Evidence and the guided demo stay on Site04 ROI3** (the decision story; Site01 ROI6 is 100 % Sun on all 20 clones). A site
  picked in the site menu or given as `?site=` is never switched. `App.tsx` route effect + no hard-coded Site04 after load;
  `Header.tsx` site menu marks the choice. Backups `tmp/App.before_site01.tsx`, `tmp/Header.before_site01.tsx`.
- **Tests:** `penumbra.spec.ts` "explore opens on real terrain" now expects Site01 ROI6 in Explore and Site04 on Decision; five
  Site04-specific Explore tests in `apex.spec.ts` / `final-apex.spec.ts` open `/?site=site04_roi3#sky`. Cloud: these 8 + guided demo pass.
  Mac VM: `tsc` clean, Vitest 99/99, Blender 31/31. Known edge: after a page reload on Explore the URL carries `site=site01_roi6`, so
  that tab then keeps Site01 on Decision too (the link counts as a choice).

## 15 Nov 2026 17:17–19:05 EST — final scientific validation (Penumbra session)

See `docs/FINAL_APEX_AUDIT.md` § Final scientific validation. Changed: `tools/certainty/build_certainty_sidecar.py` (options; defaults byte-identical), `web/public/certainty/sidecar.json` (float64 re-run). Added: `data/batch/2026-11-15_float64_rerun/`, `docs/validation/NAC_ILLUMINATION_RESULT.md`, `tools/validation/nac/`, `tools/validation/a11y/`. Mac tests pending.

#### Opening the viewer on other computers (15 Nov 2026 ~19:30 EST, session A)
- **Launchers:** `open_web_viewer.command` (Mac) and `open_web_viewer.bat` (Windows) serve `web/dist` on http://127.0.0.1:8765 with Python 3
  and open the browser (no Node or Blender). Added to `package_release.command` and the README "Launch" section. Repackage to include them.
- **Hosted copy (private claude.ai page, owner Sid, shareable from its Share menu):** https://claude.ai/artifact/PkR5bSAVdAZuUNK4xAPu8J.
  Built with `npx vite build --base ./` from the Mac tree at ~19:25 EST (140 files, 74 MB). The host serves only web file types, so in
  this copy every `.bin` terrain-pack file and the NASA SVS `.glb` globe carry an added `.wasm` suffix (context.json `file` names and the
  one globe path in the built JS changed to match); bytes and SHA-256 checks unchanged. Checked by serving the same files locally:
  Explore opens on Site01 ROI6 with the relief, Decision on Site04 ROI3, no failed requests or page errors. It is a snapshot: rebuild and
  republish after changes. Status shown on the page: SOURCE-BASED UNVALIDATED.

#### Mac run by Anish after the opening-site change (15 Nov ~19:40 EST) and fixes (session A, 20:05)
- `npm run build && npx playwright test --workers=4`: **75 passed, 4 failed**. Three were Site04-specific checks that now opened on Site01
  (terrain-context image-layer and global-Moon tests via `openExplore`, visual-final sight labels): they now open `/?site=site04_roi3#sky`.
  The fourth, guided-demo "Play advances" (12 s scene, 15 s test limit), timed out: on the story page the hidden scene built Site01's
  terrain and then rebuilt for Site04. Fix: `siteDefaults.ts` applies the page's site in the same store update that delivers the bundle,
  so only one terrain is built. Cloud cannot confirm that test (software GL is too slow for it either way); needs the Mac run.
- `package_release.command` → `dist/POLARIS-X5D-SourceBuild-Mac.zip`, 369 MB, SHA-256
  `9fc88f1599f6e5fbf1485b085564056ec62dcba4847099c29861121d022050ee` (includes the launchers; predates the 20:05 fixes). `.sha256` updated.
- Mac VM: `tsc` clean, Vitest 99/99.

#### Guided-demo "Play advances" test (15 Nov ~19:50 EST, session A)
Anish's run with the fixes: **78 passed, 1 failed** (guided-demo "Play advances": still on scene 1 after 15 s). Debugged in the cloud with
timer logging: the Play timer arms and fires correctly (with a 3 s scene the demo runs to 5/5), but on software GL (the Playwright config
uses SwiftShader) each 12 s scene takes ~16.5 s because the busy main thread delays the timer. Not an app fault; on a GPU the delay is
milliseconds. The test's wait for scene 2 is now 25 s (was 15 s), with a comment; the assertion is unchanged. Earlier "20:05" times in this
file's two previous sections were cloud-clock readings; the Mac clock (EST) read ~19:35–19:45 for that work.

#### Final Mac run, 15 Nov 2026 ~20:10 EST — all green
- `npm run build && npx playwright test --workers=4`: **79 passed, 0 failed**.
- `package_release.command` → **`dist/POLARIS-X5D-SourceBuild-Mac.zip`, 368 MB, SHA-256
  `236c57cc6ed1e3bbddca92a91831a28f5a1c6d9b3084abde9ee5c7a9383fd6ae`**; integrity OK; `.sha256` updated; includes the launchers.
- Hosted copy (https://claude.ai/artifact/PkR5bSAVdAZuUNK4xAPu8J) republished from the same source (version 5): new app scripts and
  bundle index; same `.wasm` renaming as before. Local check of the published files: Explore on Site01 ROI6 with relief, Decision on Site04
  ROI3, no failed requests or page errors.
Release status: **SOURCE_BASED_UNVALIDATED**.

## submission/merged (2026-11-15 21:05 ET, Claude): WIP merge of codex/lab-integration + session A web rebuild

- Base: codex/lab-integration (2582ad8/d24fae3). Added session A's uncommitted work from ~/Downloads/POLARIS-X5D-Blender-Codex (b-experience 8079924 + 446 files): 3D GlobalMoon, TerrainSurface, SfS relief, Story/Guide, Decision/Evidence workspaces, tools/terrain, tools/sources, tools/validation, docs.
- Conflicts (21 files): bundles + data/viewer kept from the branch (strict superset of session A's, identical values; no numbers changed). web code = session A's version with the branch's additions re-applied (Decision Lab link, arrival-slip/flip-forecast/hotspots blocks, data-source attributes, port-configurable Playwright).
- Derived NASA raster/mesh files for the 3D view (web/public/context/*.bin, globe GLB, NAC crop PNG, blender/output) are in the working tree but git-ignored (no NASA rasters in git); rebuild with tools/terrain/build_terrain_context.py.
- demo-decision-fixture.json is generated: run `python3 web/scripts/make_decision_fixture.py` before tests.
- Status: tsc + vite build OK; vitest 16 files / 101 tests pass. Playwright: 41 of 86 run before the time limit, 9 failed (branch specs expect the header/decision panels on first load, but session A's app opens on the Story route). NOT yet green: use codex/lab-integration for submission until this is fixed.
- Follow-up 83f6256 (Decision Lab link, coverage sidecar, branch specs navigate to their workspace) fixed the Story-route failures.
- Re-verified 2026-11-15 21:03 local (Claude): `npm ci` in web/ (node_modules was missing @fontsource, which broke `vite build`), `python3 web/scripts/make_decision_fixture.py`, then: vitest 99 pass / 2 skipped; Playwright **86/86 passed** (2.3 min); blender unittest 31 OK (1 skip); app `npm test` 25/25. submission/merged is now green on this Mac. Release status unchanged: `SOURCE_BASED_UNVALIDATED`.
**15 Nov 20:35 EST (Penumbra):** final Mac validation green; release ZIP `236c57cc…6ae` verified (extract + launch). SOURCE-BASED · UNVALIDATED. Recovery point before the 14islands creative pass: `tmp/web_before_14islands_2035.tgz` and the RC ZIP copy.

### Blender showcase, gallery, checkpoint push — 15 Nov 2026 20:20–21:30 EST (session A)
Release status unchanged: **SOURCE_BASED_UNVALIDATED**. No science value, bundle, sidecar or solver input changed.

- **Checkpoint pushed (Anish, Terminal, ~20:40):** `b-experience` = `2445253` = `origin/b-experience`, no force. `tmp/checkpoint_push.command`
  (stops if origin moved; excludes the rebuilt `app/dist/polaris-file.js`, 121 MB, and the 81 MB SVS 8K GLB; size check in a while-read loop after an
  xargs "too long" failure on the first try).
- **`blender/showcase.py` + `showcase_render.command`:** opens the built hero `.blend`; regolith v2 (albedo ~0.13, roughness 1, synthetic albedo noise and
  craterlet bump); synthetic boulder field (Geometry Nodes, Poisson, ≥2.5 m apart, denser on slopes, ≤0.9 m tall, 150 m kept clear around the observer,
  labelled VISUAL); Cycles on METAL; aerial, ground (1.7 m eye) and low-Sun renders at the bundle start sample; 1 m vs 10 m obstruction pair at the bundle
  transition hour (mast height and ray end from the bundle `baseline`/`mast10` ray states; no 1.75 m series exists, so it is not drawn); Draco web GLB
  (no boulders); manifest with hashes.
  - v1 on the Mac (Blender 5.3.0, METAL, 256 spp, 1920×1080): Site01 3 renders, 14,515 boulders, GLB 926,044 B; Site04 5 renders, 43,592 boulders,
    GLB 929,116 B. Site01 has no Sun transition in the window, so no obstruction pair.
  - Review: aerial and low-Sun good; ground views looked into the Sun (backlit black); Site04 sky grey (old hero file's world colour); obstruction views
    backlit with an oversized eye marker. **v2** fixes all three (ground camera on the Sun side looking down-Sun; world forced black; obstruction camera
    moved, eye marker ×0.4).
- **Gallery:** `tools/showcase/build_gallery.py` → `web/public/showcase/` (WebP q88 + `index.html` + `gallery.json`); every caption gives the bundle UTC,
  Sun az/el, bundle ray states and "boulders and micro-relief are synthetic". Linked from Evidence → Raw data ("Blender renders (presentation)").
  A Header link was tried and reverted (it pushed the data selectors under 150 px at 1440, failing `final-apex` P6 in the cloud).
- **Site01 +1.97 m:** analysed, nothing changed. See `docs/validation/SITE01_SFS_OFFSET.md`: a local ~2 m, ~100 m wide rise in SfS at the site point
  (crop bias +0.24 m, no tilt; a 10 m shift lowers the inner rms 0.96 → 0.73 m). Display-only consequence noted.
- **Verified:** Mac VM `tsc` clean. **Pending:** v2 renders, Mac `npm run build && npx playwright test`, second commit + push.

## 15 Nov 2026 20:40–22:10 EST — 14islands creative pass (Penumbra session)
Record: `docs/14ISLANDS_DESIGN_AUDIT.md` (observation → adaptation → implementation → screenshot → test).
Screenshots: `web/docs/screenshots/penumbra/14islands/{before,after}/`.
Recovery point: `tmp/web_before_14islands_2035.tgz` and the RC ZIP copy `dist/POLARIS-X5D-SourceBuild-Mac-RC-20261115-2012.zip`.

**Changed**
- `web/src/styles.css`: creative-pass block.
- `App.tsx`: heading tape, Focus mode, site-keyed title.
- `store/camera.ts`: cinematic entry `request(view, { from, ms })`.
- `store/ui.ts`: `focus`.
- `three/CameraRig.tsx`: lens (`fov`) with a dolly zoom.
- `three/Scene3D.tsx`: Overhead map lens; lens-aware markers; `GhostMast` grows; `HeadingProbe`.
- `components/Guide.tsx`: arrival from Regional; scene 3 in the ridge profile.
- `tests/e2e/guided-demo.spec.ts`: scene 3 view `ridge` (was `mast`), plus a ghost-mast check.

**New**
- `store/heading.ts`
- `components/HeadingTape.tsx`

**Unchanged**
- Science, bundles, sidecars, `TerrainSurface.tsx`, `Header.tsx`, `siteDefaults.ts`.

**Checks**
- Cloud: `tsc` clean; Vitest 98 + 1 skip (the Site01 bundle is not in the cloud). The cloud Playwright subset was too slow under software GL to finish and is not counted.
- Mac VM: `tsc` clean on the combined tree, including session A's later `TerrainSurface.tsx` / `Header.tsx` edits.
- Mac browser run: pending.


### Cloud cross-check of submission/merged (Claude, 15 Nov ~22:05 EST, at 83f6256 + later commits not included)
Cloud container (SwiftShader software WebGL): vitest 101/101; Playwright 69/86 in a 3-worker run, 15 of the 17 failures pass when re-run one at a time with a 150 s timeout; the last 2 are harness artefacts (cold-launch hit a stale server on 127.0.0.1:4173; terrain-context timed out on its final 3D screenshot after all assertions passed). The Mac run above (86/86) is the authoritative result.
### Final state, hosted copy v6, report — 15 Nov 2026 21:20–21:45 EST (session A)
- **Pushed and verified** (`git ls-remote` in Anish's Terminal): `2445253` checkpoint; `68621ac` + `ce03658` showcase v2 / gallery / offset analysis.
  Mac Playwright **79/79** (2.1 min) immediately before `ce03658`.
- **Render review (v2, 128 spp, METAL, ~7 s per render):** black sky on both sites; ground views lit; the 1 m / 10 m pair reads correctly (1 m Sun ray
  ends at the ridge 16 m out, 10 m clear). Remaining: the ray/eye markers are large in the ground views → ground camera moved to ~130 m from the mast.
- **Hosted copy v6** (private): https://claude.ai/artifact/PkR5bSAVdAZuUNK4xAPu8J, built from `ce03658` with `--base ./`, gallery included; headless check:
  Explore = Site01 ROI6 with relief on, Decision = Site04 ROI3, 0 failed requests.
- New: `docs/FINAL_REPORT_SESSION_A_2026-11-15.md` (final report), `docs/NEXT_WORK_PROMPT_CLAUDE_CODE.md` (prompt for the remaining limits:
  L1 diamond pattern, 1.75 m series, Site01 RDR check, streaming LOD + Blender ring, axe fixes, ground render polish).

### submission/merged ← b-experience 21d0f2a (Claude, 15 Nov 2026 ~21:45 EST)
- Merged 6cc00c3 (b-experience up to 68621ac) and then ce03658 + 21d0f2a: Blender showcase v2 outputs, gallery, final report and next-work prompt. Neither merge changed any web/src code. Screenshots were taken from b-experience.
- Isolated-worktree check of 6cc00c3 on the Mac (SwiftShader): vitest 101/101; Playwright 85/86 in the final full run. Each failure across runs was a different load or timing test (sight-sun, terrain-context, ux-regressions wheel scroll), and each passed when re-run alone (ux-regressions 9/9 with --repeat-each=3). `cold-launch.spec.ts` hard-codes port 4173, so it fails with POLARIS_PLAYWRIGHT_PORT set to anything else.
- Status unchanged: SOURCE_BASED_UNVALIDATED.

### 5D upgrades Phase 1 (scenario cube) + Phase 2 (slope, safe-and-lit) — Claude, 16 Nov 2026 ~00:15 EST, branch feature/5d-upgrades
- Worktree `../NSA-5d`, branched from `science/limits-2026-11-15` (e8b7b4b) before the submission deadline at Anish's request. No bundle, `data/viewer/` file or Decision Lab file changed.
- New: `schemas/scenario-cube-v1.schema.json`, `docs/SCENARIO_CUBE_CONTRACT.md`, `science/cube/` (12-month Horizons ephemeris, batched skyline solver bit-identical to `compute_skyline`, cube builder, slope + safety builder), `data/cubes/<site>/` (site04_roi3, site01_roi6; ~1.5 MB per site), `web/src/bundle/scenarioCube.ts`, `CubeSlicer` on the Decision page.
- Cubes: T(21) × D_mast(10) × S(8761 hourly starts) at the site; T(21) × D_pos(81) × S(366 daily starts) at 1 m; M(5) copied from research; terrain safety T(21) × D_pos(81). Derived: band over T, k of 20 per R preset, regret, decision-changes flags, safe-and-lit.
- Baseline round trip: Site04 RoI 3 cell = 94.362 % / 72.107 % / 19 h (bundle hourly samples identical), clones 87.537–97.329 %; Site01 RoI 6 = 100 % / 81.602 %. 10 m bundles equal the D_mast = 10 cells.
- Slope clone spread vs Barker (1.5–2.5°): 5 m baseline 1.26° (Site04) / 1.73° (Site01), same order; 25 m 0.46° / 0.69°; 100 m 0.08° / 0.11° (averaged out).
- Labels: geometry SOURCE-BASED · UNVALIDATED; landing/EVA thresholds ENGINEERING ASSUMPTION; k of N is not a probability.
- Checks (Mac, contended CPU): pytest science/tests 102 passed (test_cube 21, test_slope 19, none skipped); science/stretch 15 passed; vitest 106/106 (after regenerating the git-ignored `demo-decision-fixture.json`, byte-identical to the main checkout's); Playwright 86/88 on port 4187, both cube-slicer specs pass, traceability scan 543 scanned / 0 failed. The 2 failures are the known artefacts: `cold-launch` hard-codes port 4173; `final-apex` P6 sight-sun passed 6/6 when re-run alone.
- Not done: Phases 3–10 (see `docs/5D_UPGRADES_STATUS.md`); the safe-and-lit layer is in the cube but not yet drawn on the polar map or the Decision Card; no NetCDF/Zarr analysis copy.

### 5D upgrades Phase 3 (visibility rule R_vis) — Claude, 16 Nov 2026 ~00:30 EST, feature/5d-upgrades
- New `science/cube/build_visibility.py` → `data/cubes/<site>/visibility_rule.json.gz` (T × R_vis{any_limb, centre, half_disc, full_disc} × D_mast × daily S) and `disc_fraction_hourly.json.gz` (T × D_mast × 9097 hours, Sun and Earth, per-mille).
- `half_disc` equals `centre` by construction under the straight-line horizon (stated in the cube and tested). Disc fraction uses the local-flat-horizon assumption.
- Default stays `centre`: the centre slice equals the centre cube at every daily start (test). Reproduces science-limits L1 for the nominal and all 20 clones (Site04 RoI 3: any 97.033 %, centre 94.362 %, full 92.285 %).
- Tests: `science/tests/test_visibility_rule.py` 8 passed (orderings everywhere, analytic segment fractions, L1 identity). Slicer fixed to use the cube's schedule axis (the hourly cube has `H`, not `S`) and to remount per cube.

### 5D upgrades Phase 4 (link targets: DSN + LCRNS relays) — Claude, 16 Nov 2026 ~01:00 EST, feature/5d-upgrades
- New `science/cube/link_dsn.py`, `link_relay.py`, `build_link.py` → `data/cubes/<site>/link.json.gz`: T × D_mast × target(10) × R_margin{0,2,5°} × daily S; derived `year_summary`, `model_sensitivity`, `nasa_sanity_check`. Label ENGINEERING ASSUMPTION — reference constellation, not an operational schedule.
- DSN: Horizons resolves DSS-14/-25/-63/-56/-43/-35 by name (site name and geodetic coordinates recorded); Moon ≥ 10° at some complex 98.16 % of hours.
- LCRNS: states from the NASA LCRNS Reference Constellation 3.1 white paper (NTRS 20250002698, Table 2; 5 ELFO relays, epoch 2027-03-01 UTC). Propagated with Moon point mass + J2 + Earth + Sun (the prompt's fallback; NASA's GRGM-900c 25×25 model is not available offline). Removing J2 or the Sun changes 12-month relay availability by ≤ 0.1 pts.
- Site frame fitted hourly from Horizons (Sun, Earth, Mars, Jupiter; Wahba/SVD). Checks: leave-one-out < 0.0006°; LRO az/el vs our transform of the Horizons LRO vector max 0.0003° (requirement 0.05°); the paper's Table 2 mapped through our J2000 Moon frame reproduces Table 1 within 0.03° (ME vs PA).
- Results, nominal map, 1 m, 12 months (Site04 RoI 3 / Site01 RoI 6): DTE with DSN 50.5 % / 52.1 %; + best relay 91.4 % / 91.6 %; + best pair 98.14 % (capped by DSN coverage).
- NASA sanity (line of sight only): two relays 100 % (matches NASA); DTE 50.8/52.4 % at 0°, 41.4/43.7 % at 2°, 25.4/29.6 % at 5° (NASA 17–43 %); one relay 87.9/88.7 % at 5°, slightly above NASA's 80–86 % (best relay per site, ridge sites). Recorded in the cube.
- Tests: `science/tests/test_link.py` 8 passed. `window_metrics` gap computation vectorised (identical on random series).

### 5D upgrades Phase 9.4 (near field ±7 km at 5 m, tiled LOD display) — Claude, 16 Nov 2026 ~01:30 EST, branch 5d-phase9-lod (from feature/5d-upgrades dc8231a)
- New `tools/terrain/build_lod_tiles.py`: the PGDA 78 5 m tile (`science.sites.near_dem`, solver cache, URL + SHA-256 recorded) → 5-level quadtree (80/40/20/10/5 m; 341 tiles per site, 126 736 B each, 43 MB per site) for site04_roi3 and site01_roi6 in git-ignored `web/public/context/lod/<site>/` + `manifest.json` (`polaris-lod-tiles-v1`, status VISUAL, numericalAuthority false). 5 m nodes = source pixels unchanged; coarser = box means; NaN never filled (Site04 RoI 3: 4.8 % of the square is beyond the tile).
- New `web/src/bundle/lodTiles.ts` (validate, select by camera distance, draw set with ancestor fallback), `web/src/three/LodTerrain.tsx` + `lodMesh.ts` + `lodWorker.ts`, `LodPanel.tsx`, `store/lod.ts`. Scene3D: opt-in toggle (off by default; `?lod=1`), on-screen “display only”, `data-source`/`data-label` (SOURCE-BASED · UNVALIDATED · DISPLAY ONLY). The solver, bundles, `data/viewer/` and `web/public/lab/` are untouched.
- Performance: p95 ≤ 4.4 ms in every phase with the layer on (headless Chrome Metal, uncapped; `perf_mac.mjs --lod --headless --uncapped`). Budget 16 ms met. The full pane run is invalid (pane hidden); see `docs/PERFORMANCE_REPORT.md`.
- Tests (Mac, load average 33–39 on 18 cores from other sessions' batches): pytest science/tests 126 passed (new `test_lod_tiles.py` 8, incl. built tiles vs the solver DEM and vs the bundle's 5 m crop within 1 mm); vitest 115/115 (new `lodTiles.test.ts` 9; after regenerating the git-ignored `demo-decision-fixture.json`, byte-identical to the main checkout's); `npm run build` OK; Playwright on port 4191: 85 passed / 5 failed in the full run, including the new `lod-near-field.spec.ts` (2) passing, and the traceability scan at 545 scanned / 0 failed. The failures: `cold-launch` hard-codes port 4173 (known). `apex` (2) and `visual-final` sight-sun (2) are timing flakes under load: they wait 5 s for per-frame sight labels on software GL. Re-run alone, apex + visual-final passed 9/9. An earlier full run had a different set (guided-demo, penumbra, visual-final), and those passed 14/14 alone.
- Not done: a full frame-time run in the visible Claude pane (the session's pane was hidden); cast shadows on the LOD layer; the 80 m context beyond ±7 km while the layer is on.
