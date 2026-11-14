# POLARIS X — BUILD_STATUS (branch `a-science`)

> **Provenance of this checkout.** The live repo was not reachable from the cloud session
> (no git checkout, no Mac folder connected, invalid GitHub token). At Sid's instruction this
> branch was built on the archived `POLARIS-X5D-Blender-Codex-Mac.zip` from the Claude project,
> imported as commit `cc1d7f0` on `main`; `a-science` branches from it. Port these commits onto
> the live `a-science` (e.g. `git am` from the delivered patch series). `CLAUDE.md` was read from
> the project docs; the archive has no `CLAUDE.md` or `docs/BUILD_STATUS.md` (this file is new).

## 0. Baseline (before any edits) — 2026-11-14 ~13:05 UTC

| Command | Exit | Result |
|---|---|---|
| `git status` | 0 | `On branch a-science, nothing to commit, working tree clean` |
| `python3 -m unittest discover -s blender -p 'test_*.py' -v` | 0 | `Ran 6 tests ... OK` |
| `(cd app && npm test)` | 0 | node --test, 13 pass / 0 fail (Node v22.23.4) |

Env: Python 3.13.18, numpy 2.5.3, rasterio 1.5.2 (GDAL 3.12.2), pyproj 3.8.0.
Scope rule honoured: no edits to `web/` or `app/src/`.

## 1. T1 — frames + Moon-fixed 3D model ✅ (red → green)

Files: `science/frames.py`, `science/dem.py`, `science/skyline.py`, `science/tests/test_frames.py`.

- Red: `python3 -m unittest discover -s science/tests -t . -v` → exit 1 (`ModuleNotFoundError: science.dem`), then one
  test failure from a forward-difference bias in the test itself (fixed to central differences).
- Green: same command → exit 0, `Ran 9 tests ... OK`.
- Covered: grid↔ENU (local north = (sin L, cos L), east = (cos L, −sin L)); grid_az = local_az + L, so the legacy error is
  exactly L (Site01 −137.49°, Site04 −171.87°); synthetic ridge 2 km due local east of Site01 gives el(az 90) > 5°,
  el(az 270) < 0°; pyproj round-trip from the LDEM COG's own CRS (WKT cached at `data/raw/LDEM_80S_80MPP_ADJ.crs.wkt`)
  < 1 mm, and the closed form agrees with that CRS < 1 mm at both sites.
- Model: P = (R+h)·u(lat,lon), R = 1 737 400 m; elevation = asin((P−P_obs)·up/|P−P_obs|); rays are great circles.
- Not changed: `app/src/science.js` (out of scope) and `blender/polaris_geometry.py` still contain the grid-direction bug;
  they are superseded as numeric authorities by `science/` + the bundle.

## 2. T3 — Horizons ingest + crossings ✅ (red → green)

- Red: `python3 -m unittest science.tests.test_horizons` → exit 1 (ImportError). Green after `science/horizons.py`,
  `science/crossings.py`: 6 tests OK (1 skipped until the archive existed; it now runs).
- Query: Sun `10`, Earth `399`, `CENTER='coord@301'`, `SITE_COORD='222.5100000,-89.4632000,1.944772'` (east-lon, lat,
  km; height = 5 m DEM at site), 2026-11-14 00:00 → 2026-11-28 00:00 UTC, 1 h → 337 rows per body. Columns found by
  header name. Raw text + SHA-256 in `data/raw/horizons/` + `MANIFEST.json`.
- Cross-check: the first Site01 Sun row (az 264.093209304, el 1.501428252) matches the audit's earlier independent query.
- Bisection queries Horizons again through TLIST at each midpoint (13 iterations → bracket 0.439 s). Every iteration's raw
  file is archived. Angular radius = Horizons Ang-diam/2: Sun 0.2697°, Earth 0.9008° on 2026-11-14.

## 3. T2 — 720-bin skyline ✅ (Site01)

- Far field: LDEM_80S_80MPP_ADJ.TIF via `/vsicurl` range reads in 1024² chunks. Single reads larger than about 2048² px
  failed through the proxy (`TIFFFillTile ... got 0 bytes`), so reads retry. The whole file was also downloaded once
  (189 158 392 B, SHA-256 `82030dcb…beee5a`). A 4125×4125 `/vsicurl` window was **bit-identical** to it
  (max |diff| = 0.0 m, 0 NaN mismatches). Window ±290 km, `max_range_m` = 280 km, 80 m step.
- Near field: product 78 `Site01_final_adj_5mpp_surf.tif` (16×16 km, 5 m), from `https://pgda.gsfc.nasa.gov/data/LOLA_5mpp/Site01/`.
  **`/vsicurl` strip reads of this uncompressed TIFF returned corrupted rows (707 px with |z| ≈ 1e34) that produced a
  bogus 89.8° horizon at az 264.** Fix: download the whole tile (Content-Length checked; two downloads give the same
  SHA-256 `3ba7b97c…7e747e`; z range −523.18…1959.50 matches the header) and add a ±20 km physical-range screen
  that turns bad pixels into NaN, which then shows up as 'truncated'.
- Result (Site01, eye = 1944.772 + 2 m): 720/720 bins complete, 0 truncated, 0 range-limited; horizon −3.216°…+2.292°.
  559 bins are set by the 5 m tile, 161 by the 80 m mosaic. The most any terrain beyond 280 km could reach is −3.58°.
  Flat baseline = 0°; bare-sphere dip −0.0835°.
- Tests: `CoverageGaps` (gap → truncated, no fabricated angle; a NaN hole truncates only the bins it affects). These
  passed on first run because T1's skyline already handled gaps, so they guard against regressions rather than
  showing a red→green change.

## 4. T4 — contract, schema, Site01 bundle, UI fixture ✅

```
python3 -m science.bundle --site site01 --start "2026-11-14 00:00" --days 14 --step-h 1 --mast 2 \
  --out data/bundles/site01_2026-11-14_14d.json --fixture data/bundles/fixtures/site01_ui_fixture_50.json
```
- Docs: `docs/SCIENTIFIC_CONTRACT.md`; schema `schemas/science-bundle-v2.schema.json`.
- Site01 metrics (SOURCE-BASED UNVALIDATED), 2026-11-14 → 11-28: Sun centre visible 81.170 %, Earth centre 66.228 %,
  both 47.398 %; longest Sun-centre hidden spell 63.27 h (runs to the end of the window), longest Earth-centre hidden
  spell 113.47 h; mean visible disk Sun 0.8022, Earth 0.6620. Hourly-sample fractions (0.8101 / 0.6617) agree with the
  event-based values.
- Events (±0.22 s): Earth first light 11-18 01:40:25.6, centre rise 11-18 17:28:27.5, fully visible 11-19 09:56:24.4;
  Sun begins occultation 11-24 03:23:52.8, centre set 11-25 08:43:49.5, last light 11-25 20:49:08.5 UTC.
- Tests: `test_bundle.py`: schema validity, invariants (an angle only where there is a critical cell, margin = el − H, no events
  outside the window, bracket ≤ 1 s), the fixture is an exact subset, and negative cases (a fabricated status, a 15 km
  range, or an unlabelled metric is rejected). These are contract tests written after the bundle existed.
- `python3 -m unittest discover -s science/tests -t .` → exit 0, 24 tests OK.
