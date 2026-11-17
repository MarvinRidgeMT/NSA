# Phase 7 · T1 — NASA-user features and gates (backend side)

Session T1 of v2 round 3 (`docs/v2/SPLIT_ROUND3.md`), prompt §7. Branch `claude/v2-t1-nasa-features-ceef5e`
(already contains 13551d0, so no new branch was cut). Written 16 Nov 2026 before any code.

Owns: `science/exports/**`, `science/api/**`, `docs/v2/API.md`, `docs/v2/GATES.md`, `docs/v2/openapi.yaml`,
`docs/v2/tool_spec.json`, `web/scripts/gates/**`. Does not edit web UI (T2) or worlds/anysite (T3).

## 0. Rules this work keeps
- **No new science.** Exports and the API only read precomputed files (results bundles, scenario cubes,
  `decision_summary.json`, `precompute_summary.json`). The only path that computes is `POST /v1/solve` with
  `compute: true`, which calls the existing `science.worlds.moon.solve` (= `science.anysite.solve.solve`) unchanged.
- Every exported number carries its source file, a JSON path in that file, the file's SHA-256 and two one-line commands:
  `read` (prints the number from the file: `python -m science.exports value <file> <path>`) and `recompute` (the
  command that rebuilds the file, from its own provenance).
- Labels go with the numbers: geometry SOURCE-BASED · UNVALIDATED; energy/link ENGINEERING ASSUMPTION; "k of N maps is not
  a probability". Nothing becomes "validated" by being exported.
- NASA-derived rasters (GeoTIFF masks/maps) are written under `data/exports/` which is git-ignored; small JSON/CSV/PDF
  outputs for the two committed sites are reproducible from the command and are not committed either (one directory,
  one rule).
- No new dependencies. Available: numpy, scipy, rasterio, jsonschema, pytest (venv); Playwright + Chrome (web). Not
  available: reportlab/fpdf (PDF), PyYAML, openapi-spec-validator, axe-core in `web/node_modules`. Consequences below.

## 1. Exports (`science/exports/`)
| Export | From | Format | Notes |
|---|---|---|---|
| Time series | any `polaris-science-results-v1` bundle (committed `data/bundles/*`, any-site cache `data/cache/anysite/bundles/<hash>.json`, Mercury `data/worlds/mercury/*`) | CSV + JSON | one row per Horizons sample: UTC, Sun/Earth az, el, skyline, margin, centre visible, disc fraction, horizon flag. JSON carries per-column source paths. No resampling or interpolation. |
| GeoTIFF masks | `data/cubes/<site>/terrain_safety.json` (9 × 9 positions, 25 m) | GeoTIFF, south-polar stereographic (`+R=1737400`) | bands: landing slope 100 m (nominal), safe on all 20, k lit, k safe-and-lit (per slope limit). Pixel centres = cube positions; values copied, never resampled. |
| GeoTIFF maps | `data/anysite/precompute_summary.json` global 10° grid | GeoTIFF, Moon sphere lon/lat | Sun %, Earth %, Sun+Earth %, longest Sun gap. Pixel centre = grid point; cells without a site are nodata. Polar 1° grids are not on a regular lon/lat raster -> exported as CSV points, not GeoTIFF. |
| Decision Card PDF | `decision_summary.json` + cube `index.json` (+ committed bundle headline if one exists) | PDF 1.4, text only | Minimal stdlib PDF writer (no reportlab). Uncompressed content stream so the test can read the text back. Every row: value, label, source cube + SHA-256, reproduce commands. |
| Provenance bundle | all of the above | directory + deterministic ZIP | `provenance.json`: inputs (path, SHA-256, bytes), outputs (path, SHA-256), command, git commit, dirty flag, generator version. |
| Reproduce commands | per number | in every JSON/PDF/CSV sidecar | `python -m science.exports value <file> <json-path>` and the file's own recompute command. |

CLI: `python -m science.exports site site04_roi3 --out data/exports/site04_roi3`,
`python -m science.exports anysite --lat .. --lon .. [--mast 1]` (cache lookup only), `python -m science.exports bundle <file>`.

Tests (`science/exports/tests/`): CSV and JSON time series equal the bundle samples value by value; GeoTIFF band values
and georeferencing equal the cube values and positions (rasterio read-back); the PDF's text contains every
`decision_summary` value exactly and `science.cube.build_summary.rows(site)` still equals the committed file; every
`value` command returns the exported number; the provenance SHA-256s match the files on disk; a changed input changes
the hash.

## 2. Solver API (`science/api/`)
- `science/api/spec.py`: one Python source of truth -> `docs/v2/openapi.yaml` (OpenAPI 3.1; written by a small YAML
  emitter because PyYAML is not installed; a test regenerates and compares) and `docs/v2/tool_spec.json` (JSON Schema
  tool definitions an AI planner could call; **no planner, no key**).
- `science/api/server.py`: stdlib `http.server`, binds 127.0.0.1. Routes under `/v1`: `health`, `worlds`,
  `worlds/{world}`, `sites` (precomputed list, filters), `sites/{site_hash}` (summary / full), `sites/{site_hash}/timeseries.{csv,json}`,
  `solve` (POST), `batch` (POST), `cubes/{site_id}/decision_summary`, `cubes/{site_id}/decision_card.pdf`, `openapi.yaml`, `tools`.
- Worlds: Moon = any site (cache lookup; `compute: true` runs the solver). Mercury = the precomputed Prokofiev rim
  bundle only (the any-site `world=` hook is T3's); other Mercury points return 422 with that reason. Mars = 501 with the
  registry's availability note.
- Cache by site hash: request -> normalised request key (SHA-256) -> `site_hash` -> bundle file. Index in
  `data/cache/api/request_index.json` (git-ignored with `data/cache/`), seeded from `precompute_summary.json`.
- Batch: list of solve requests, results in order, each identical to the single call (test).
- Tests: every route in the server is in the spec and vice versa; all spec schemas pass `Draft202012Validator.check_schema`;
  all `$ref`s resolve; live responses validate against the declared response schemas; batch == single; cache hit == file;
  error codes (400 bad lat, 404 unknown hash, 422 Mercury elsewhere, 501 Mars).
  Not available offline: the official OpenAPI 3.1 meta-schema validator; the structural checks above replace it (stated in API.md).

## 3. Gates (`docs/v2/GATES.md`, `web/scripts/gates/`)
| Gate | How | Pass rule |
|---|---|---|
| p95 frame globe / region / 5 m | `web/scripts/gates/perf_gates.mjs` (from `perf_mac.mjs`): headed Chrome, Metal, vite preview; globe = `GlobalMoon` layer, region = 3D context scene, 5 m = `?lod=1` near field | p95 ≤ 16 ms (recorded with vsync on: at 60 Hz a perfect run is 16.7 ms, which is stated; an uncapped run is also recorded) |
| Cold start | same script, fresh browser context, `goto` -> first globe frame drawn (rAF after `data-loaded=true`) | ≤ 5 s |
| Traceability | existing `tests/e2e/traceability.spec.ts` on port 4221 + Python scan of every export number (source path + reproduce) | 0 failed |
| Label audit | `web/scripts/gates/label_audit.py`: the label rules of `docs/SCIENCE_LABEL_AUDIT.md` applied to exports, API responses, `decision_summary.json`; existing label e2e specs | 0 violations |
| Accessibility | axe-core if found in `web/node_modules` (it is not); else a documented lite scan (names, alt, lang, ids, landmarks) via Playwright | 0 serious |
| Mobile 390 px | Playwright at 390 × 844: no horizontal scroll, main controls in viewport, screenshot | pass/fail per check |
Failures go to T2 as a list in GATES.md (no UI fixes here). The browser-pane-hidden case is recorded when it applies.

## 4. Done
`python -m pytest science tools -q`, `cd web && npm run build && npx vitest run`, gates with `POLARIS_PLAYWRIGHT_PORT=4221`,
T1 row in `docs/v2/STATUS.md`, `docs/BUILD_STATUS.md` appended, small commits on this branch only.
