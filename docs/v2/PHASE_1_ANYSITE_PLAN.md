# v2 Phase 1 · §2.4 any-site solver — plan (session S4, 16 Nov 2026)

Owner: S4 (`science/anysite/**` and its tests). Labels: geometry **SOURCE-BASED · UNVALIDATED**; uncertainty members
without PGDA clones are labelled **assumed error model**. Nothing in an existing bundle changes; outputs go to new files.

## 1. Inputs
| Input | Meaning |
|---|---|
| `lat`, `lon` | planetocentric degrees, east-positive longitude (MOON_ME, 1 737 400 m sphere) |
| `mast_m` | observer height above the local DEM ground (default 1 m, as the ROI bundles) |
| `start`, `days`, `step_h` | UTC window (default 2026-11-14 00:00, 14 d, 1 h: the demo window of the existing bundles) |
| `members` | uncertainty members to run: `clones` (PGDA 78), `assumed` (error-model members), `products` (M) |

## 2. Method
1. **Terrain stack.** `science.anysite.stack.get_stack()` returns S3's `science.terrain.stack.TerrainStack` when it is
   importable and its index exists, otherwise `LegacyStack`: an adapter with the same three methods (`sample`,
   `window`, `coverage`) over the DEMs on disk tonight:
   - PGDA 78 5 m site tiles (Site01, Site04, Site07, Site11 nominal; Site01/Site04 clones 1–20),
   - PGDA 90 `LDEM_80S_80MPP_ADJ.TIF` (80 m, ±304 km around the south pole, SHA-256 pinned in `science/sites.py`),
   - any further GeoTIFF registered in `science/anysite/products.py` (north-polar or equirectangular products from S2,
     when they land). Products are ordered by the contract's merge priority (§6 of `TERRAIN_STACK_CONTRACT.md`).
   Windows are read with the existing `science.dem.read_window` (no resampling, nodata → NaN, |h| > 20 km → NaN).
2. **Near field** (≥ 25 km). The finest product covering the site, window ±25 km clipped to that product's footprint, at
   native resolution. Ray step = native / 5 (1 m on the 5 m PGDA 78 tiles, the converged ROI-bundle step; 16 m on 80 m
   data) to the inscribed radius of the finest product, or to 25 km when the finest product is the far-field product.
   Beyond the finest product the next product supplies samples at its own native step (compute_skyline's near/far rule:
   near preferred wherever it has data).
3. **Far field to the curvature limit.** Terrain no higher than `H` can reach elevation `e` above an observer at radius
   `r0 = R + h_eye` only within central angle `θ(e) = acos(r0 cos e / (R + H)) − e` (exact on the sphere; derivation in
   `science/anysite/curvature.py`). With `H` = the Moon's highest point, +10 786 m (Selenean summit, LOLA; Smith et al.
   2010 GRL 37 L18204 — conservative: the largest published value), the required range is
   `L_req = R · max_bins θ(e_bin)`. Policy: `max_range = max(280 km, L(e = 0))` (280 km = the existing bundles), clipped to
   the far product's coverage; after the skyline is computed, `L_req` is evaluated from the skyline itself and bins whose
   skyline is below the world-relief bound at `max_range` are flagged `range_limited_world`. If `L_req > max_range` and
   data reach further, the skyline is recomputed once at `L_req` (≤ 600 km). The limit, `H`, the formula and the
   flags are recorded in the bundle (`skyline.curvature_limit`).
4. **Horizon mask.** `science.skyline.compute_skyline`, unchanged: 720 bins, great-circle rays, float64 heights,
   Moon-fixed 3D elevation, truncated/range-limited flags. Members (clones etc.) use `science.cube.compute.multi_skyline`
   when the settings match its fixed ones (1 m step, 280 km, 720 bins); otherwise compute_skyline per member.
   Products in a non-south-polar grid are wrapped so that compute_skyline's south-polar-stereographic sample points are
   converted back to lat/lon and sampled in the product's own CRS (exact inverse; no reprojection of the raster).
5. **Sun and Earth.** JPL Horizons, the identical query of `science/horizons.build_params` (coord@301, GEODETIC,
   QUANTITIES 4,13,20, AIRLESS, site altitude = DEM ground height). Raw responses are cached byte-for-byte under
   `data/cache/anysite/horizons/<sha256(params)[:20]>.txt` with a JSON sidecar (SHA-256, bytes, retrieved UTC, params).
   Before any network call the existing archive `data/raw/horizons/MANIFEST.json` is searched for an entry with
   identical params (read-only reuse, SHA-256 re-verified). Never written into the committed archive.
6. **Bundle.** `polaris-science-results-v1` (the schema of every existing bundle; validated in tests), with full
   provenance (DEM layers with file and array SHA-256, Horizons raw files with SHA-256, git commit, command,
   curvature limit, coverage of the site). Metrics are on hourly samples (no bisection refinement by default: one
   Horizons query per body keeps a new site within the time target; `refine=True` reuses `science.bundle.refine_events`).
   The method text states which. Output: `data/cache/anysite/bundles/<site_hash>.json` (git-ignored, reproducible);
   committed: only `data/anysite/precompute_summary.json` (metrics, timings, hashes; no rasters).
7. **Cache by site hash.** `site_hash = sha256(json{lat (1e-7 deg), lon, mast, window, products+SHA-256, solver
   version})[:16]`. A second request for the same site returns the cached bundle.

## 3. Uncertainty (axis 5, X)
- **T, PGDA 78 clones** where the site lies in a Site01/Site04 tile (20 clones cached; 100 published).
- **T, assumed error model** elsewhere: per product, smooth Gaussian height-error fields (σ, correlation length from the
  product's documented accuracy, deterministic seeds), added to the near field only (a 1 m error at 25 km moves the
  horizon by ≤ 0.0023°; the far field is not perturbed and the bundle says so). Label exactly "assumed error model".
  PGDA 90's page distributes an `_ERR.TIF` layer that is not cached tonight; until it is, σ = 1 m is an assumption
  recorded as such (LOLA radial orbit accuracy class), not a product statement.
- **M, product disagreement** wherever ≥ 2 products cover the site: the skyline and metrics with each product as the
  near field. Tonight that is PGDA 78 vs PGDA 90 at the four PGDA 78 sites; elsewhere "only one product cached".
- "k of N maps is not a probability": members are reported as ranges, never as a probability.

## 4. Tests (`science/anysite/tests/`, run with `python -m pytest -q science/anysite science/tests`)
1. **Site04 RoI 3 through the any-site path** (lat/lon only, no site id): hourly Sun 94.36 %, Sun+Earth 72.11 %,
   longest hourly Sun gap 19 h; 20 clones 87.54–97.33 %. Also: far window array SHA-256 equals the committed bundle's.
2. **Flat sphere analytic**: constant-height DEM → every bin equals the closed-form dip
   `−acos((R+h)/(R+h+mast))` (≤ 1e-4°) where the ray reaches the geometric horizon, plus the curvature-limit formula
   against a brute-force search.
3. **North-pole sanity run**: only if a north-polar DEM is registered/cached; otherwise `skip` with the reason.
4. **Pyramid agreement**: once `science.terrain.stack` exists and has tiles at Site04 RoI 3, the mask from the pyramid
   agrees with the PGDA 78 mask (median |Δ| ≤ 0.05°, 95th pct ≤ 0.3°, tolerance justified in the test); skip otherwise.
5. Adapter: `sample`, `window`, `coverage` match direct reads; lat/lon CRS wrapper exact on a south-polar product;
   site hash stability; Horizons cache SHA-256 check fails on a tampered file.

## 5. Precompute list (`science/anysite/precompute_sites.json`, cited)
- 4 current sites: Site01 RoI 6, Site04 RoI 3, Site07 RoI 1, Site11 RoI 4 (PGDA 78 RoI centroids).
- Artemis III candidate regions, NASA's latest list (28 Oct 2024 release; George et al., LPSC 2026 abstract 1901):
  Peak near Cabeus B, Haworth, Malapert Massif, Mons Mouton Plateau, Mons Mouton, Nobile Rim 1, Nobile Rim 2,
  de Gerlache Rim 2, Slater Plain. NASA publishes no region coordinates (map only), so they are listed without
  coordinates and not run; all lie poleward of 84° S, inside the 1° grid below.
- 1° grid poleward of 80° at the south pole (every integer latitude −80…−89 × longitude step giving ≈ 1° of arc at
  80° S, plus the pole); the north-pole grid is listed but needs a north-polar DEM.
- Landing sites (NSSDC lunar artifact table, updated 13 Aug 2025, DE421 frame): Apollo 11, 12, 14, 15, 16, 17;
  Chang'e 3, 4, 5, 6; Chandrayaan-3; IM-1; IM-2; Blue Ghost 1 (and SLIM). Only IM-2 (84.79° S) is inside cached data
  (IM-1 at 80.13° S is inside PGDA 90 but its far field leaves the product); the rest need SLDEM2015 / LOLA global.

## 6. Acceptance
Tests above green; `science/tests` green; new-site wall time measured and reported (target ≤ 60 s on this Mac, 4 workers
max); Site04 RoI 3 numbers reproduced; precompute run for everything the cache supports, with the remainder listed
as "needs data"; `docs/BUILD_STATUS.md` appended; S4 row in `docs/v2/STATUS.md` filled.
