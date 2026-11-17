# POLARIS X v2 — solver API and exports (T1, prompt §7)

All numbers here are **SOURCE-BASED · UNVALIDATED**: local geometric visibility from NASA DEMs and JPL Horizons, not
certified illumination, power or DSN link availability. Energy and link values are **ENGINEERING ASSUMPTION**.
**k of N maps is not a probability.** Nothing in this layer computes science except `POST /v1/solve` with
`"compute": true`, which calls the existing any-site solver unchanged.

## 1. Exports — `python -m science.exports`

| Command | Writes (under `data/exports/`, git-ignored) |
|---|---|
| `python -m science.exports site site04_roi3` | `site04_roi3_decision_card.pdf` + `.json`, `site04_roi3_terrain_safety.tif`, time series (CSV + JSON) of the committed 1 m / 10 m bundles and of the cached any-site bundle at the same point, `numbers.json`, `provenance.json`, `site04_roi3_provenance.zip` |
| `python -m science.exports bundle <results-bundle.json>` | CSV + JSON time series, `numbers.json`, provenance (any world: Moon committed or any-site, Mercury) |
| `python -m science.exports anysite --lat -89.78012 --lon -156.32023` | the same for a precomputed any-site point (cache lookup only; never solves) |
| `python -m science.exports grid` | `moon_global_10deg_precompute.tif` (4 bands: Sun %, Earth %, Sun+Earth %, longest Sun gap h) + `moon_polar_1deg_precompute.csv` |
| `python -m science.exports value <file> '<json-path>'` | prints one number from its source file (the per-number **read** command) |

**Per-number reproduce.** Every exported number is a record in `numbers.json` (and inline in the time-series JSON and
the card JSON): `value, unit, label, source_file, source_sha256, json_path, read, recompute`. `read` is the one-line
command above; `recompute` is the command that rebuilt the source file, taken from that file's own provenance
(`generator.command` for results bundles, `provenance.command` for cubes, `python -m science.cube.build_summary <site>`
for Decision Card rows, `python -m science.anysite.precompute` for the grid).

**Time series.** One row per Horizons sample in the bundle (no resampling, interpolation or extrapolation). Columns:
`utc, t_unix`, then per body (`sun_`, `earth_`) `az_deg, el_deg, [el_horizons_deg], radius_deg, range_au, horizon_deg,
margin_deg, center_visible, disk_fraction, horizon_flag`. Floats are written with the shortest round-trip repr: CSV →
float gives the bundle value exactly (tested on every cell). Azimuth 0° N, 90° E, local ENU.

**GeoTIFF.** `*_terrain_safety.tif`: the 9 × 9, 25 m position grid of `terrain_safety.json` in `IAU_2015:30135` (Moon
2015 sphere, south polar stereographic; its proj4 equals the bundles' `+proj=stere +lat_0=-90 … +R=1737400`). Pixel
(row, col) centre = site grid xy + the cube's (dx, dy); bands: `landing_slope_100m_nominal`, then per slope limit
(10°, 8°: ENGINEERING ASSUMPTION) `safe_all_20`, `k_lit`, `k_safe_and_lit`, `nominal_lit`. Values are copied (float64);
tags carry the source file, SHA-256, cube id and recompute command. The global grid uses `IAU_2015:30100` lon/lat
(pixel centre = grid point; one point solve per pixel, not a cell average). The 1° polar grids are rings, not a lon/lat
raster, so they are exported as CSV points.

**Decision Card PDF.** Built from `data/cubes/<site>/decision_summary.json` (rows precomputed by
`science.cube.build_summary`) and the cube `index.json`; each row shows value, answer, label, source cube + SHA-256
(checked against the index), the read command and the cube's rebuild command; then the committed 1 m bundle headline and
the limits. Written by a 200-line stdlib PDF writer (`science/exports/pdf.py`: no PDF library is installed); text-only,
Helvetica/Courier, uncompressed so tests read it back.

**Provenance bundle.** `provenance.json` = inputs (path, SHA-256, bytes) + outputs (same) + command + git commit (+ whether
`science/` had uncommitted changes); `<name>_provenance.zip` holds every output plus `provenance.json`, deterministic
(sorted, fixed timestamps): the same inputs into the same directory give the same bytes.

## 2. Solver API — `python -m science.api.server [--port 8767]`

stdlib `http.server`, **127.0.0.1 only**, no keys, no paid services. Spec: [`openapi.yaml`](openapi.yaml) (OpenAPI 3.1,
generated from `science/api/spec.py`: `python -m science.api.spec --write`; `--check` fails on drift). Also served at
`GET /v1/openapi.yaml` and `/v1/openapi.json`.

| Route | What |
|---|---|
| `GET /v1/health` | status, git commit, number of precomputed sites |
| `GET /v1/worlds`, `/v1/worlds/{world}` | world summaries (`science.worlds`) + what the API supports per world |
| `GET /v1/sites?world=&group=&lat_min=&lat_max=&limit=&offset=` | 1,251 precomputed Moon points (`data/anysite/precompute_summary.json`) + world bundles (Mercury Prokofiev rim) |
| `GET /v1/sites/{site_hash}[?full=1]` | result of one site (metrics with JSON path + read command; `full` adds the whole bundle) |
| `GET /v1/sites/{site_hash}/timeseries.{json,csv}` | the exports time series |
| `POST /v1/solve` | one point (below) |
| `POST /v1/batch` | `{"requests": [SolveRequest, …]}` → `{"results": [{"status", "body"}, …]}` in order; result *i* = `POST /v1/solve` with request *i* (tested) |
| `GET /v1/cubes/{site_id}/decision_summary`, `/decision_card.pdf` | precomputed Decision Card rows / PDF |
| `GET /v1/tools` | AI-planner tool spec ([`tool_spec.json`](tool_spec.json)) |

**Solve request** (`SolveRequest`): `world` (moon · mercury · mars), `lat`, `lon` (east; any convention, normalised to
−180…180), `mast_m` (1), `start` ('2026-11-14 00:00' UTC), `days` (Moon 14), `step_h` (1), `members` (clones · assumed ·
products; omitted = whatever was precomputed, all three when computing), `n_members` (20), `compute` (false),
`allow_network` (false: Horizons only from the raw-response cache), `full` (false). Unknown fields → 400.

**Cache by site hash.** The request is normalised and hashed (`request_key`), and mapped to the solver's own
`site_hash` (which includes window, members and terrain products). Order: request index
(`data/cache/api/request_index.json`, git-ignored) → precompute summary (exact point, mast 1 m, default window, member
kinds the precompute requested) → world bundles → `compute: true` (`science.worlds.moon.solve` = `science.anysite.solve.solve`,
which also caches bundles by site hash in `data/cache/anysite/bundles/`). `cache.source` in the response says which.

**Worlds.** Moon: any point. Mercury: precomputed world bundles only (the exact Prokofiev rim point and window); any other
point → 422 (the any-site `world=` hook is session T3's). Mars → 501 with the registry's availability note.

**Errors.** 400 invalid request (schema), 404 unknown hash / not precomputed (`compute: true` to run) / no cubes,
405 wrong method, 422 world or point not available (incl. "Horizons not cached and `allow_network` false"), 500 solver
error, 501 Mars. Body: `{"error", "status", "detail"}`.

**Solve result** (`SolveResult`) also carries `terrain` (`near_product`, `far_product`, `n_truncated_bins` of the
any-site bundle; null for world bundles), added 17 Nov 2026 for the viewer.

**Viewer ("query any point → compute now").** The web viewer talks to this server: `npm run dev` / `npm run preview`
proxy `solver-api/` to `http://127.0.0.1:8767` (override with `POLARIS_SOLVER_API`); the panel probes `GET /v1/health`
and sends `POST /v1/solve` with the precomputed rows' window and mast, `compute: true`, `allow_network: true`
(`web/src/globe/anysite.ts`). The response is shown field by field, never recomputed. A captured real answer is the web
test fixture `web/tests/fixtures/v1-solve-result.site01_roi6.json`; `science/api/tests/test_web_fixture.py` checks it
against the schema and, when the bundle cache is present, against the live API. The older single-route stub
`python -m science.anysite.api` (:8766) is no longer used by the viewer.

**Git provenance without fork.** Health, exports and solver bundles record the git commit through `science/gitinfo.py`
(posix_spawn). Forking from the threaded server while a solve held PROJ/SQLite crashed the child on macOS and the
commit came back `unknown`; regression test `science/tests/test_gitinfo.py`.

**Offline batch:** `python -m science.api.server --batch requests.json`.

Example (measured 16 Nov 2026): `POST /v1/solve {"lat": -89.5, "lon": 12.345, "members": [], "compute": true,
"allow_network": true}` → 200 in ~10 s (Sun 67.656 % of hourly samples, SOURCE-BASED · UNVALIDATED); the same request
again → `cache.source = request-index` in < 0.1 s.

## 3. AI-planner tool spec (`docs/v2/tool_spec.json`)

Seven tools (`polaris_solve_site`, `polaris_batch_solve`, `polaris_list_sites`, `polaris_get_site`,
`polaris_get_timeseries`, `polaris_decision_summary`, `polaris_list_worlds`), each `{name, description, input_schema}`
(self-contained JSON Schema 2020-12) plus `x-polaris-route` (method, path, operationId). The descriptions carry the
grounding rule: quote only numbers in that turn's tool results, with their labels; output is AI-GENERATED.
**There is no AI planner and no API key in this repository** (prompt §7 makes the planner optional; not built here).

## 4. Validation and what is not checked

Tests: `science/exports/tests/test_exports.py` (16), `science/api/tests/test_api.py` (17).
- Exports: every CSV/JSON cell equals the bundle value; every `read` command returns the exported value; GeoTIFF pixel
  values equal the cube values and pixel centres equal site xy + offsets (and the site lat/lon transformed through the
  GeoTIFF CRS lands on the centre pixel); `k_safe_and_lit == 20` pixel count equals the Decision Card 'safety' row; the
  PDF contains every row value, label and read command, its xref table is valid, and `build_summary.rows(site)` still
  equals the committed `decision_summary.json`; provenance SHA-256s match the files; a changed input changes the hash.
- API: committed `openapi.yaml`/`tool_spec.json` equal the generator; the YAML parsed by an independent parser (Ruby
  Psych) equals the spec; every component schema passes `Draft202012Validator.check_schema`; every `$ref` resolves; path
  parameters match templates; server routes == spec paths; live HTTP responses validate against the declared response
  schema for their status; values equal the source files; batch == single; cache hits; all error codes.
- **Not available offline:** the official OpenAPI 3.1 meta-schema validator (`openapi-spec-validator` is not installed);
  the structural checks above stand in for it.
