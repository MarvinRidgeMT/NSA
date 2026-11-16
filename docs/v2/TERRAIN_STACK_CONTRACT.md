# Terrain stack contract (v2 Phase 1) — interface between data (S2), pyramid (S3) and any-site solver (S4)

Amend only by appending a dated section at the end. Science numbers stay float64 in the solver.

## 1. Cache root and layout
`$POLARIS_DATA` (env var; default `data/cache/`, git-ignored). Nothing under it is committed.
```
$POLARIS_DATA/v2/products/<product_id>/<files as published>      raw downloads (S2)
$POLARIS_DATA/v2/manifest.jsonl                                   one JSON object per downloaded file (S2)
$POLARIS_DATA/v2/pyramid/<zone>/<level>/<ix>_<iy>.tif             science tiles (S3), Cloud-Optimized GeoTIFF
$POLARIS_DATA/v2/pyramid_visual/<zone>/<level>/<ix>_<iy>.tif      VISUAL sub-resolution relief (S3), display only
$POLARIS_DATA/v2/pyramid/index.json                               tile index: zone, level, bounds, CRS, bands, sha256
```
Committed mirror of the manifest (no data): `docs/v2/DATA_MANIFEST.json` — per file: `product_id`, `url`, `sha256`,
`bytes`, `licence`, `acknowledgement`, `retrieved_utc`, `product_version`, `local_path` (relative to `$POLARIS_DATA`).

## 2. Frame and datum
Heights in metres above the 1,737,400 m reference sphere, MOON_ME body-fixed, east-positive longitude. Products in other
datums/frames are converted at ingest (each conversion has a test). Azimuth convention unchanged: 0° north, 90° east.

## 3. Zones
- `eq`: equirectangular (simple cylindrical on the sphere), latitudes −60°…+60° (SLDEM2015 native grid).
- `sp`, `np`: polar stereographic on the 1,737,400 m sphere, true scale at the pole (same closed form as
  `science/frames.stereo_forward`), covering |lat| ≥ 55° (5° overlap with `eq` for seam QA/feathering).
Levels: level 0 ≈ 1 km/pixel; each level halves the pixel size; a tile is never upsampled beyond its source's native
resolution (finer levels exist only where a finer product exists).

## 4. Tile bands (science pyramid)
| band | dtype | meaning |
|---|---|---|
| `height` | float32 (solver casts to float64) | metres above the reference sphere; NaN = no data (never filled) |
| `source_id` | uint8 | product that supplied the pixel (`docs/v2/SOURCE_IDS.json`) |
| `native_res_m` | float32 | native horizontal resolution of that product at that pixel |
| `quality` | uint8 | 0 = no data, 1 = interpolated within a product gap ≤ 2 px, 2 = native, 3 = native + co-registered |

The VISUAL tree has only `height_visual` and is never read by science code (S3 adds a test that fails if
`science/` opens anything under `pyramid_visual`).

## 5. Python API (`science/terrain/stack.py`, owned by S3)
```python
stack = TerrainStack.open(root=None)           # root defaults to $POLARIS_DATA/v2/pyramid
h, src, res = stack.sample(lat, lon)           # vectorised; bilinear on the finest available level; NaN outside
dem = stack.window(lat0, lon0, half_m, res_m)  # science.dem.ArrayDEM in the polar-stereographic grid of the zone
                                               # (eq zone: a local polar-stereographic reprojection is allowed only
                                               #  if documented; otherwise return a local equirectangular ArrayDEM
                                               #  with its own sampler)
stack.coverage(lat, lon) -> dict               # source_id, native_res_m, quality, level
```
Until S3 lands, S4 uses an adapter with the same methods backed by the existing DEMs (`science.sites.near_dem`,
`science.sites.far_dem`, PGDA 90 LDEM_80S) so the solver and its tests do not wait on the pyramid.

## 6. Merge priority (per location, §2.2 of the prompt)
NAC DTM > SfS (polar, where validated) > PGDA 78 5 m > Kaguya TC DTM (quality good) > PGDA 90 > SLDEM2015 > LOLA polar
LDEM > LOLA global LDEM. Co-registration shifts (horizontal and vertical) are estimated against LOLA and logged per product.

## Amendment 2026-11-16 (S3, pyramid implementation) — clarifications, no change to the API
1. **Band storage.** GeoTIFF cannot mix sample types in one file, so a tile stores all four bands as float32 (band
   descriptions `height, source_id, native_res_m, quality`; `source_id` and `quality` hold exact integers). `stack.py`
   casts them to uint8. Tiles are COG (DEFLATE, predictor 3, 256 px blocks; 240 px in `eq`), nodata = NaN.
2. **Grids.** Polar zones: closed-form stereographic (`sp` = `science.frames.stereo_forward`; `np`: x = ρ sin λ,
   y = −ρ cos λ, ρ = 2R tan(π/4 − φ/2)), extent ±1,310,720 m, level L pixel = 1280 m / 2^L (L4 = 80 m, L8 = 5 m),
   512 px tiles; pixels with |lat| < 55° are NaN. `eq`: lon/lat degrees, level L = 32·2^L px/deg (L4 = 512 ppd),
   480 px tiles (15° at L0). Tile (ix, iy) counts from the zone's top-left corner. Geometry lives in
   `science/terrain/stack.py` (`ZONES`), shared by the builder.
3. **Zone choice in `sample`/`coverage`:** polar for |lat| ≥ 57.5°, `eq` below. Each zone is a complete merge on its own
   grid; the 55–60° overlap is used for the eq↔polar seam check.
4. **Priority is per location, across levels.** Where a higher-priority product exists, a finer lower-priority product
   does not show at finer levels either (e.g. LOLA LDEM_875S_5M under PGDA 90 80 m: the location is PGDA 90 at 80 m).
   Finer levels therefore exist only where the highest-priority product at that location is that fine.
5. **Feathering:** 8 level pixels from the higher-priority product's own data edge; pixels in the band carry
   `native_res_m` of the coarser contributor. No stored pixel is a pure upsample.
6. **`window`:** returns `science.terrain.stack.ZoneDEM` (an `ArrayDEM` subclass) with `proj` ∈ {`sp`, `np`,
   `local-stere`} and `forward/inverse/sample_latlon`; `res_m=None` → native step at the centre; pixels without data at
   the chosen level stay NaN unless `fill_coarser=True` (counted in `meta['filled_from_coarser_px']`); `layers` holds
   per-pixel `source_id`, `native_res_m`, `quality`, `filled`. Only `proj == 'sp'` windows can go straight into
   `science.skyline.compute_skyline` (it hard-codes the south-polar formula).
7. **Quality 3** = co-registration vs a LOLA reference was estimated (shift applied or found below threshold);
   LOLA-family products (PGDA 78/90, LOLA LDEMs) are logged and never shifted (`$POLARIS_DATA/v2/pyramid/coreg.json`).

## Amendment 2026-11-16 (2) (S3) — zone blend and product edge trim
1. **Zone blend.** `sample` and `coverage` no longer switch abruptly between `eq` and the polar zone at |lat| = 57.5°:
   across 56.5–58.5° the height is a linear blend of both zones (polar weight (|lat| − 56.5)/2); `source_id`,
   `quality`, `level`, `zone` come from the zone with the larger weight and `native_res_m` is the coarser of the two.
   Reason: at 55–60° both zones show SLDEM2015, eq at its 59 m posting and polar resampled onto 80 m pixels; the raw
   difference is p99 13.9 m (south) / 21.8 m (north), median 0.5 m, which the blend spreads over ~60 km (≤ 0.021°
   added slope). `window` still returns a single zone's grid.
2. **Edge trim.** The outer 40 native pixels of each LOLA polar LDEM (PDS `LDEM_*{S,N}_*M_FLOAT`) are no data:
   a gridding boundary effect was measured there (p99 |Δ| vs the neighbouring product 52 m at the edge, interior level
   only 800 m in for the 20/30 m grids). Footprints and coverage reflect the trimmed rectangle.
