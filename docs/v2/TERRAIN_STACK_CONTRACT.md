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
