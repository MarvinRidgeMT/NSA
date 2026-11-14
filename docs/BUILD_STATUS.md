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
