# POLARIS X — BUILD_STATUS (branch `a-science`)

> **Provenance of this checkout.** The live repo was not reachable from the cloud session
> (no git checkout, no Mac folder connected, invalid GitHub token). At Sid's instruction this
> branch was built on the archived `POLARIS-X5D-Blender-Codex-Mac.zip` from the Claude project,
> imported as commit `cc1d7f0` on `main`; `a-science` branches from it. Port these commits onto
> the live `a-science` (e.g. `git am` from the delivered patch series). `CLAUDE.md` was read from
> the project docs; the archive has no `CLAUDE.md` or `docs/SCIENCE_BUILD_STATUS.md` (this file is new).

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
- Docs: `docs/SCIENCE_RESULTS_CONTRACT.md`; schema `schemas/science-results-v1.schema.json`.
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

## 5. T5 — Site04, G5 scenarios, recomputed repair ✅

```
python3 -m science.bundle --site site01 --start "2026-11-14 00:00" --days 14 --step-h 1 --mast 2 --scenarios \
  --out data/bundles/site01_2026-11-14_14d.json --fixture data/bundles/fixtures/site01_ui_fixture_50.json   # ~17 min
python3 -m science.bundle --site site04 --start "2026-11-14 00:00" --days 14 --step-h 1 --mast 2 --scenarios \
  --out data/bundles/site04_2026-11-14_14d.json                                                               # ~16 min
```
Every scenario recomputes in full: new skyline, a new Horizons fetch, and fresh bisection. That gives 2337 archived raw
Horizons files (24 MB), each with its SHA-256 in `MANIFEST.json` and `scenarios[].horizons_raw`. DEM uncertainty uses
both the ±1σ `toterr` shift (fully correlated, a bounding case, observer height held fixed, far field unchanged) and
product-78 clones 1–5. The repair takes the best 3×3 offset and adds a 10 m mast, then recomputes the combination from
scratch. All values are SOURCE-BASED UNVALIDATED.

**⚠ Site coordinates:** both archived site coordinates fall within 1 m of the centre of their product-78 tile, so the
app seems to have used tile centres as sites. At Site04 that point is on a **31.6° slope** inside the Shackleton rim:
the horizon reaches 32° and Earth (az 165–176°, behind a 6–9° wall) is never visible. The bundle marks
`site-coordinate-source` as `fail` for Site04. Site01's slope is 5.6° and its check stays `not-run`. The site
coordinates need a sourced replacement; none was invented here.

Observations: Site01 is very sensitive at the 100 m / few-metre scale. The horizon there is set by terrain 135–330 m
away (5 m DEM), so +100 m east or a 5 m mast gives 100 % Sun-centre visibility. Under arrival ±12 h the both-visible %
stays at 47.398 because the overlap (Earth rise 11-18 → Sun set 11-25) lies inside every shifted window. At Site04 the
±1σ shift and the clones barely move anything, because the Sun's set is controlled by far-field (80 m) terrain, which
has no error raster.

**site01** (Connecting Ridge (Site01), eye 1946.772 m, slope 5.635°)

| scenario | Sun ctr % | Earth ctr % | both % | longest Sun hidden h | longest Earth hidden h |
|---|---|---|---|---|---|
| position-offset east_m=-100,north_m=-100 | 38.609 | 60.568 | 0.0 | 206.2724 | 132.491 |
| position-offset east_m=-100,north_m=0 | 38.733 | 55.684 | 0.0 | 205.8578 | 148.902 |
| position-offset east_m=-100,north_m=100 | 50.37 | 57.615 | 7.985 | 166.7581 | 142.412 |
| position-offset east_m=0,north_m=-100 | 89.687 | 72.649 | 62.336 | 25.4879 | 91.9008 |
| position-offset east_m=0,north_m=0 | 81.17 | 66.228 | 47.398 | 63.2696 | 113.4743 |
| position-offset east_m=0,north_m=100 | 57.362 | 59.674 | 17.036 | 141.0473 | 135.4958 |
| position-offset east_m=100,north_m=-100 | 100.0 | 81.796 | 81.796 | 0.0 | 61.1651 |
| position-offset east_m=100,north_m=0 | 100.0 | 81.812 | 81.812 | 0.0 | 61.1105 |
| position-offset east_m=100,north_m=100 | 100.0 | 81.829 | 81.829 | 0.0 | 61.0555 |
| mast-height mast_m=2.0 | 81.17 | 66.228 | 47.398 | 63.2696 | 113.4743 |
| mast-height mast_m=5.0 | 100.0 | 74.164 | 74.164 | 0.0 | 86.8074 |
| mast-height mast_m=10.0 | 100.0 | 81.803 | 81.803 | 0.0 | 61.1406 |
| arrival-shift shift_h=-12 | 84.741 | 62.656 | 47.398 | 51.2696 | 125.4743 |
| arrival-shift shift_h=12 | 77.598 | 69.799 | 47.398 | 75.2696 | 101.4743 |
| dem-uncertainty kind=toterr-shift,sigma=-1 | 82.578 | 66.718 | 49.296 | 58.5389 | 111.8271 |
| dem-uncertainty kind=toterr-shift,sigma=1 | 74.868 | 65.733 | 40.602 | 77.783 | 115.1369 |
| dem-uncertainty kind=product-78-clone,clone=1 | 81.727 | 66.758 | 48.485 | 61.3987 | 111.6921 |
| dem-uncertainty kind=product-78-clone,clone=2 | 81.79 | 66.524 | 48.314 | 61.1856 | 112.4794 |
| dem-uncertainty kind=product-78-clone,clone=3 | 78.723 | 66.043 | 44.766 | 71.4905 | 114.0953 |
| dem-uncertainty kind=product-78-clone,clone=4 | 72.008 | 65.609 | 37.618 | 94.0517 | 115.5523 |
| dem-uncertainty kind=product-78-clone,clone=5 | 69.287 | 64.76 | 34.047 | 103.195 | 118.4056 |
| repair east_m=100,north_m=100,mast_m=10.0 | 100.0 | 81.844 | 81.844 | 0.0 | 61.0026 |

**site04** (Shackleton Rim (Site04), eye 771.676 m, slope 31.564°)

| scenario | Sun ctr % | Earth ctr % | both % | longest Sun hidden h | longest Earth hidden h |
|---|---|---|---|---|---|
| position-offset east_m=-100,north_m=-100 | 48.038 | 0.0 | 0.0 | 174.5936 | 336.0 |
| position-offset east_m=-100,north_m=0 | 48.32 | 0.0 | 0.0 | 173.6462 | 336.0 |
| position-offset east_m=-100,north_m=100 | 48.513 | 0.0 | 0.0 | 172.9964 | 336.0 |
| position-offset east_m=0,north_m=-100 | 48.703 | 0.0 | 0.0 | 172.3575 | 336.0 |
| position-offset east_m=0,north_m=0 | 48.879 | 0.0 | 0.0 | 171.768 | 336.0 |
| position-offset east_m=0,north_m=100 | 49.114 | 0.0 | 0.0 | 170.977 | 336.0 |
| position-offset east_m=100,north_m=-100 | 49.423 | 0.0 | 0.0 | 169.94 | 336.0 |
| position-offset east_m=100,north_m=0 | 49.645 | 0.0 | 0.0 | 169.1938 | 336.0 |
| position-offset east_m=100,north_m=100 | 49.88 | 0.0 | 0.0 | 168.4046 | 336.0 |
| mast-height mast_m=2.0 | 48.879 | 0.0 | 0.0 | 171.768 | 336.0 |
| mast-height mast_m=5.0 | 48.925 | 0.0 | 0.0 | 171.6125 | 336.0 |
| mast-height mast_m=10.0 | 49.002 | 0.0 | 0.0 | 171.3532 | 336.0 |
| arrival-shift shift_h=-12 | 52.45 | 0.0 | 0.0 | 159.768 | 336.0 |
| arrival-shift shift_h=12 | 45.307 | 0.0 | 0.0 | 183.768 | 336.0 |
| dem-uncertainty kind=toterr-shift,sigma=-1 | 48.879 | 0.0 | 0.0 | 171.768 | 336.0 |
| dem-uncertainty kind=toterr-shift,sigma=1 | 48.879 | 0.0 | 0.0 | 171.768 | 336.0 |
| dem-uncertainty kind=product-78-clone,clone=1 | 48.879 | 0.0 | 0.0 | 171.768 | 336.0 |
| dem-uncertainty kind=product-78-clone,clone=2 | 48.879 | 0.0 | 0.0 | 171.7663 | 336.0 |
| dem-uncertainty kind=product-78-clone,clone=3 | 48.879 | 0.0 | 0.0 | 171.7665 | 336.0 |
| dem-uncertainty kind=product-78-clone,clone=4 | 48.878 | 0.0 | 0.0 | 171.7714 | 336.0 |
| dem-uncertainty kind=product-78-clone,clone=5 | 48.877 | 0.0 | 0.0 | 171.7737 | 336.0 |
| repair east_m=100,north_m=100,mast_m=10.0 | 49.991 | 0.0 | 0.0 | 168.0309 | 336.0 |

## 6. Final verification (after T5)

| Command | Exit | Result |
|---|---|---|
| `python3 -m unittest discover -s science/tests -t . -v` | 0 | `Ran 25 tests ... OK` (0 skipped) |
| `python3 -m unittest discover -s blender -p 'test_*.py' -v` | 0 | `Ran 6 tests ... OK` |
| `(cd app && npm test)` | 0 | 13 tests, 13 pass, 0 fail |
| `git diff --stat cc1d7f0 -- app web blender` | 0 | empty — no app/web/blender edits |

## Open items (not done)
- Independent validation (`not-run`): compare against published Site01/Site04 illumination; DE421-ME vs MEAN_ME frame tie;
  sourced site coordinates.
- Legacy `app/src/science.js` and `blender/polaris_geometry.py` still have the grid-azimuth bug (out of scope here). The
  viewer and Blender should read the bundle instead.
- Range-read transport: `/vsicurl` is flaky through this sandbox's proxy (empty tiles; corrupted strips). The far field
  was verified bit-identical. The near field is downloaded whole.

## 7. ROI bundles ported onto the rebased branch (14 Nov, ~12:00 ET)

- The ROI work (`d0990c2` on Sid's Windows PC, built on the old pre-rebase branch) was replayed onto the rebased
  `a-science` with `git am -3`. There was one conflict, in `science/bundle.py` (schema name), resolved to
  `polaris-science-results-v1`. `requirements.txt` was dropped because main's `requirements-science.txt` covers it.
- All 6 ROI bundles and `data/viewer/polaris-x5d-roi-2026-11-14-v2.json` were regenerated with fresh Horizons pulls, so they
  carry the new schema name and generator commit. Every metric is identical to the PC's run (e.g. Site01 ROI6 1 m:
  Sun 100 %, Sun+Earth 81.772 % interval / 81.602 % hourly; Site04 ROI3 1 m: Sun 94.213 % / 94.362 %, longest Sun gap 19.44 h).
- `python3 -m unittest discover -s science/tests -t .` → exit 0, 34 tests OK.
- Note: `generator.git_commit` in these bundles names the commit the regeneration ran on in Claude's workspace. After
  `git am` on another machine, that commit has a different hash but the same tree.

## 8. A1 Ridge of Record (14 Nov, 13:10–13:20 ET)

SOURCE-BASED UNVALIDATED. Spec: `claude/IMPLEMENTATION_PROMPT_DECISION_EVIDENCE_2026-11-14.md` A1.

- `science/skyline.py`: new opt-in `with_gap=True` adds per bin `runner_up_gap_deg` (controlling elevation minus the best
  elevation among ray samples ≥ 2 DEM cells away, cell of the DEM that supplied the controlling sample),
  `critical_source` (`near_5m` / `far_80m`) and `critical_index`. Default output is unchanged (all bundles reproduce).
- `science/attribution.py` (new): clusters bins into ridges (adjacent bins whose controlling points are within 2 far-field
  cells = 160 m, **plus the ray spacing D·Δθ** — without that allowance every ridge beyond ~18 km split into single bins),
  attributes each hourly Sun/Earth sample to the nearest bin, and counts `ctrl_h` / `*_loss_h` per ridge.
  `of_record` = the ridge cost at least one Sun or Earth sample. `python3 -m science.attribution --write <bundle>` recomputes
  the skyline, **refuses to write unless it reproduces the stored skyline exactly**, and writes `derived.attribution`.
- Schema: optional `derived.attribution` block (one added line). Viewer export: each scenario carries its own
  `attribution`; `derived.attribution` = the baseline (first mast) scenario's.
- Tests 34 → **40** (`science/tests/test_attribution.py`): planted plateau (SYNTHETIC) is the only ridge of record and its
  span is 80–100° within one bin; +50 m raises its Sun loss hours; loss hours = blocked samples; per-bin shapes; circular
  wrap of clusters; the real Site04 ROI3 bundle lists ridges and its Sun loss hours equal its blocked samples.
- Real results (14-day window, hourly samples):

| Bundle | Ridges of record | Sun loss | Earth loss | Main Sun blocker |
|---|---|---|---|---|
| Site04 ROI3, 1 m | 3 | 19 h | 75 h | R3: near_5m, 12–169 m away (mean 16 m), az 78–144°, +1.6 m above the site ground, all 19 Sun-loss hours |
| Site04 ROI3, 10 m | 3 | 0 h | 72 h | none (Earth: far_80m ridges ~128–132 km, az ~151–158°) |
| Site04 ROI4, 1 m / 10 m | 2 / 2 | 0 h | 72 h | none |
| Site01 ROI6, 1 m / 10 m | 3 / 3 | 0 h | 62 h | none (Earth: far_80m ridges ~137–141 km, az ~131–137°) |

- Reading: at Site04 ROI3 the 1 m mast's Sun loss comes from a ~1.6 m rise right next to the lander, not distant
  terrain; at 10 m it vanishes. The runner-up gap at that rise is tiny (0.0003°), so its exact position along the ray is
  not sharp (broad low rise), and it lies inside the 5 m tile (it is what the clones perturb). Earth loss is from far
  80 m-LDEM terrain >120 km away at every site, outside the clone tiles (relevant to A3 coverage).
- Some docs say "the ~16 m rise". The solver says the blocker is ~16 m **away** and ~1.6 m **high**.

## 9. A3 Coverage Gauge + A4 margin series (14 Nov, 13:20–13:37 ET)

SOURCE-BASED UNVALIDATED. Spec: IMPLEMENTATION_PROMPT A3, A4. A1 is on GitHub as `13d23d4`.

- `science/coverage.py` → `derived.coverage`: critical hours = hourly samples with |margin| < 1.0°; `covered_frac` = share of
  them whose controlling skyline sample (A1 `per_bin.source` at the body's azimuth) is `near_5m`, i.e. inside the clone tile;
  `uncovered_ridges` = A1 ridge ids behind uncovered critical hours. Top level = Sun (spec shape), `earth` alongside, plus
  `all_hours_covered_frac` (same test over every hour, comparable to the batch gauge). `covered_frac` is null when there are
  no critical hours.
- `science/margins.py` → `derived.margin_series`: per hourly sample the nominal Sun/Earth margin (copied from `samples`) and
  min/max over **PGDA 78 clones 1–20** (near field = clone, ground height from the clone, same far DEM / 1 m ray step /
  280 km). Nominal Horizons az/el reused for every clone (observer-height parallax < 1e-8°). Also per clone: hourly Sun and
  Sun+Earth visible %, and per sample the number of clones with the centre visible.
- Schema: `derived.coverage`, `derived.margin_series` added (same one-line `derived` entry). Viewer export: each scenario
  carries `coverage` and `margin_series`; `derived.coverage` = baseline scenario.
- Tests 40 → **47** (`test_coverage.py`: ridge outside the tile → 0, inside → 1, threshold, bundles reproducible;
  `test_margins.py`: margin sign = visibility flag at every sample, clone min/max consistent with clone counts, clone 1
  recomputed).

| Bundle | Sun critical h / covered | Sun all-hours covered | Earth critical h / covered | Sun % over 20 clones | Sun+Earth % over 20 clones |
|---|---|---|---|---|---|
| Site04 ROI3, 1 m | 39 h / **100 %** | 34.4 % | 35 h / 100 % | **87.5–97.3** | 64.4–74.5 |
| Site04 ROI3, 10 m | 0 / — | 0 % | 30 h / **0 %** | 100 | 78.6 (all clones) |
| Site04 ROI4, 1 m and 10 m | 0 / — | 0 % | 30 h / 0 % | 100 | 78.6 (all clones) |
| Site01 ROI6, 1 m | 0 / — | 9.5 % | 33 h / 0 % | 100 | 81.6 (all clones) |
| Site01 ROI6, 10 m | 0 / — | 0 % | 33 h / 0 % | 100 | 81.6 (all clones) |

- Reading: at Site04 ROI3 with a 1 m mast every near-critical Sun hour is controlled by terrain inside the clone tile, so
  the 20-clone spread is meaningful there. Every near-critical **Earth** hour at a 10 m mast (and at Site01 ROI6 / Site04 ROI4)
  is controlled by far terrain the clones do not change: "every clone agrees" on Earth says nothing about terrain
  uncertainty (wording rule: show `covered_frac` next to any such claim).
- Cross-check with the batch (BATCH_RESULTS_CLOUD / THIRD, 20 clones, 1 m step):
  - Site04 ROI3 1 m Sun range: repo 87.5–97.3 % vs batch 87.2–97.0 %, i.e. **1 hourly sample higher at each end** (same
    direction and size as the nominal gap explained in A_SCIENCE_STATUS 13:06: bin-centre placement).
  - Sun+Earth: repo 64.4–74.5 % vs batch 62.6–74.8 %; the minimum differs by 6 samples (Earth side). Not investigated.
  - Batch coverage gauge (inscribed-radius test, all hours): Site04 ROI3 Sun 34.1 / Earth 58.5 %, Site01 ROI6 Sun 11.0 /
    Earth 0 %; repo 34.4 / 61.1 % and 9.5 / 0 %. Same picture, different tie-breaking.

## 10. A2 Certainty Height (14 Nov, 13:40–14:10 ET)

SOURCE-BASED UNVALIDATED. Spec: IMPLEMENTATION_PROMPT A2. A3 + A4 were committed as `d14af8d` (patch to Sid).

- `science/certainty.py` → `derived.certainty` (same block in both mast bundles of a site): for masts
  1, 1.25, 1.5, 1.75, 2, 3, 5, 7, 10, 15 m (the polaris_batch v2 `certainty` set) × nominal DEM + PGDA 78 clones 1–20, a
  skyline per DEM and mast (repo solver, 1 m near step, 280 km), then hourly Sun-centre and Sun+Earth visible %.
  `certainty_curve` rows = {mast_m, metric, nominal, min, p10, median, p90, max, n_clones, pass{req: "k/N"}, by_clone}.
  `certainty_height_m` = smallest tested mast where the nominal DEM **and** every clone have 100 % Sun centre (the batch
  definition); `certainty_height_by_requirement_m` also gives Sun ≥ 70 % and Sun+Earth ≥ 40 % (team requirements, Anish 13:50 ET; flat aliases
  `derived.certainty_curve` / `derived.certainty_height_m` are also written). `batch_reference` quotes the batch values from the project docs (not recomputed).
- Viewer export: `derived.certainty_curve`, `derived.certainty_height_m`, `derived.certainty` per dataset.
- Tests 47 → **50** (`test_certainty.py`): monotonic in mast on every DEM; the bundle's own mast row equals the bundle metric
  and the A4 per-clone values; certainty-height definition.
- Run: `python3 -m science.certainty --bundle data/bundles/<site>_2026-11-14_14d_mast1m.json --out data/cache/certainty/<site>.json`
  (~13 min per site, 2 cores), then `python3 -m science.certainty --write data/cache/certainty/<site>.json`.

| Site | Certainty Height (100 % Sun, every DEM) | Sun ≥ 70 % (team) | Sun+Earth ≥ 40 % (team) | Batch |
|---|---|---|---|---|
| Site04 ROI3 | **1.75 m** | 1 m | 1 m | 1.75 m (identical) |
| Site01 ROI6 | **1 m** (lowest tested) | 1 m | 1 m | ≤ 1 m (identical) |
| Site04 ROI4 | **1 m** (lowest tested) | 1 m | 1 m | not run in the batch |

Site04 ROI3 Sun-centre % over 20 clones: 1 m 87.5–97.3 (0/20 at 100 %), 1.25 m 91.4–100 (6/20), 1.5 m 96.4–100
(16/20), 1.75 m 100 (20/20). Batch: 1.25 m 91.1–100, 1.5 m 96.1–100. The repo again reads one hourly sample higher at the low
end (bin placement); the Certainty Height is the same.
- Per-clone check against the batch CSV now in the repo (`data/batch/2026-11-14/clone_sweep/clone_sweep_runs.csv`, Site04 ROI3,
  1 m, Sun samples of 337): exact on 6/20 clones, otherwise −3 to +5 samples, both signs (mean +0.4). Not a systematic offset:
  each clone has its own knife-edge hours. Quote ranges, not single clones.
