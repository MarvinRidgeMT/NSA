# Phase 1 · S3 — global terrain pyramid, seams, coverage, VISUAL roughness (plan)

Session S3, 16 Nov 2026 ~02:30 EST, branch `claude/v2-s3-pyramid-b01622` (cut from `feature/v2-whole-moon` eda168c).
Scope: prompt §2.2, §2.3 and the map part of §2.5. Interface: `docs/v2/TERRAIN_STACK_CONTRACT.md` (implemented as written;
changes only as dated amendments at its end). Written before coding (§0.5). Decisions taken while the user was asleep are
marked **[decision]** with the reason.

## 1. Inputs
| Product | source_id | Native | Where | Status at start |
|---|---|---|---|---|
| PGDA 78 LOLA 5 m site tiles (Barker et al. 2021) | 3 | 5 m | 16 × 16 km tiles near the south pole (Sites 01, 04, 07, 11 cached) | have (`data/external/pgda78`, `data/cache/p78`) |
| PGDA 90 LDEM_80S_80MPP_ADJ | 5 | 80 m | south polar stereographic ±304 km (lat ≤ ~−80°) | have (`data/external/pgda90`) |
| SLDEM2015, LOLA polar and global LDEMs, PGDA 70 roughness, others | 6, 7, 8 | 59 m, 20–240 m, 118 m+ | ±60°, poles, global | S2 is downloading into `$POLARIS_DATA/v2/products/`; picked up from `$POLARIS_DATA/v2/manifest.jsonl` |

Every product is described by a `ProductSpec` in `tools/globe/pyramid_products.py` (S3's reader-side description: grid kind,
units, scale/offset, radius-or-height, frame, nodata, native resolution). S2's `tools/globe/products.py` owns what is downloaded;
S3 never downloads.

## 2. Grids and levels **[decision]**
- **Polar zones `sp`/`np`:** closed-form polar stereographic on the 1,737,400 m sphere, true scale at the pole
  (`sp`: x = ρ sin λ, y = ρ cos λ, ρ = 2R tan(π/4 + φ/2) — identical to `science.frames.stereo_forward`;
  `np`: x = ρ sin λ, y = −ρ cos λ, ρ = 2R tan(π/4 − φ/2), i.e. `+proj=stere +lat_0=90 +lon_0=0 +R=1737400`).
  Square extent ±1,310,720 m (covers |lat| ≥ 48.7°); pixels with |lat| < 55° are set to NaN so each polar zone covers exactly
  |lat| ≥ 55°. Level L pixel = 1280 m / 2^L (L0 1280 m … L4 80 m … L8 5 m, L9 2.5 m). Reason: 1280·2^−L hits the native posts
  of PGDA 90 (80/40/20 m) and PGDA 78 (5 m) exactly, and the extent is a multiple of every level's pixel, so those products are
  pixel-aligned (no resampling at native level). Tiles 512 × 512 px.
- **Equatorial zone `eq`:** simple cylindrical (lat/lon degrees on the sphere), lat −60…+60, lon −180…+180, level L = 32·2^L
  pixels per degree (L0 32 ppd ≈ 948 m at the equator … L4 512 ppd = SLDEM2015 native). Tiles 480 × 480 px (15° at L0) so the
  360° × 120° zone divides into whole tiles at every level.
- **Never upsampled:** a product of native resolution r (metres, its coarser posting axis) contributes to a level only if the
  level pixel ≥ r/1.01 (polar: pixel size in metres; eq: the latitude-direction pixel R·π/180/ppd, which is the larger axis).
  Finer levels exist only as tiles that hold at least one pixel of a product that fine.
- **Zone overlap:** each zone is a complete priority merge of every product that overlaps it, in its own grid. `sample` and
  `coverage` use `sp`/`np` for |lat| ≥ 57.5° and `eq` below. The eq↔polar difference over 55°–60° is a pure reprojection
  check and is reported as its own seam pair.

## 3. Ingest: datum and frame conversions (one test each)
Target: metres above the 1,737,400 m sphere, MOON_ME, east-positive longitude −180…180.
1. **int16 DN with scale/offset** (PDS LOLA LDEM IMG: `value = DN·SCALING_FACTOR + OFFSET`).
2. **km → m** (SLDEM2015 and LOLA FLOAT IMG are in km).
3. **radius → height** (subtract 1,737,400 m) and **radius on another sphere** (e.g. a product referenced to a different
   radius: h = h' + R' − 1,737,400).
4. **longitude 0…360 → −180…180** (wrap, applied by sampling with lon mod 360, never by shifting pixels).
5. **PA → ME frame** (DE421 PA→ME rotation, Williams et al. 2008 / JPL DE421 lunar frame memo: angles 67.92″, 78.56″, 0.30″);
   applied only if a product declares PA. All products listed so far are ME, so it is tested but expected unused.
6. **polar stereographic north vs south** closed forms checked against pyproj for the CRS strings.
Every product read passes the existing physical-range screen (|h| > 20 km → NaN).

## 4. Co-registration vs LOLA
For each product P and a LOLA reference G (LOLA global/polar LDEM when S2 delivers it; until then PGDA 90 80 m, itself a LOLA
product, for polar products): block-average P onto G's grid over their overlap, estimate the horizontal shift (dx, dy) by
minimising the RMS of (P_shifted − G) over a ±2-pixel sub-pixel search (coarse 0.5 px then 0.1 px), then the vertical shift dz =
median(P_shifted − G). Logged per product to `$POLARIS_DATA/v2/pyramid/coreg.json` and committed as numbers in
`docs/v2/PYRAMID_QA.json`. **[decision]** Shifts are applied only when |dz| > 1 m or |dxy| > 0.25 reference pixel (otherwise
logged, not applied); pixels of a product whose co-registration was estimated get quality 3, else 2. A synthetic test recovers a
known (dx, dy, dz).

## 5. Merge and feathering
Per zone, level and tile: products sorted by contract priority (NAC > SfS > PGDA 78 > Kaguya TC > PGDA 90 > SLDEM2015 > LOLA polar
> LOLA global). Lowest priority first; each higher-priority product is laid over with weight w = clip(d / F, 0, 1), where d is the
distance (pixels of the level) from the product's own valid-data edge (computed on a padded window, so tile edges are not seams)
and **F = 8 pixels of the level [decision]** (e.g. 40 m at 5 m, 640 m at 80 m: wide enough to hide a few-metre offset as
< 1° of extra slope, narrow enough not to blur the fine product's footprint). Inside the band the coarser partner may be a product
that is too coarse for the level (bilinear of its native grid); such pixels carry `native_res_m` = the coarser contributor
(conservative) and pixels with no fine contributor at all stay NaN, so no stored pixel is purely upsampled. `source_id` = the
dominant-weight product. Gaps ≤ 2 px inside a product are filled at native resolution by neighbour mean (quality 1); larger
gaps stay NaN. Downsampling to coarser levels is area-average on the native grid then sampling (no aliasing).

## 6. Outputs
- `$POLARIS_DATA/v2/pyramid/<zone>/<level>/<ix>_<iy>.tif`: COG, 4 bands `height, source_id, native_res_m, quality`.
  **[decision]** GeoTIFF cannot mix sample types in one file, so all four bands are float32; `source_id`/`quality` hold exact
  integers and `stack.py` casts them to uint8 (amendment appended to the contract).
- `index.json`: zones (CRS, extent, tile px, level pixel sizes), tiles (zone, level, ix, iy, bounds, sha256, sources present).
- `science/terrain/stack.py`: `TerrainStack.open/sample/window/coverage` exactly as the contract. Bilinear on the finest level
  with a finite value; NaN outside. `window` returns a `science.dem.ArrayDEM` subclass in the zone's stereographic grid
  (sp/np) or a documented local oblique stereographic grid centred on the site for `eq` (scale error < 6·10⁻⁵ at 25 km,
  < 0.7 % at 290 km); each carries `forward/inverse/sample_latlon` because `science.skyline` hard-codes the south formula.
- **Science never reads VISUAL:** `TerrainStack.open` refuses any root under `pyramid_visual`, plus a static test over
  `science/**` and a runtime spy test.

## 7. Seam QA (`tools/globe/seams.py`)
For each product pair (hi, lo) adjacent in the merge: in the feather band of hi, compare hi block-averaged to lo's native grid
with lo (removes the resolution effect, leaves real disagreement). Report N, signed median, median |Δ|, p99 |Δ| and the extra
slope the feather adds (p99|Δ| / F). Map: per-cell (10 km polar, 0.5° eq) p99 |Δ| PNG (git-ignored) + JSON. Tolerances per pair,
documented in `tools/globe/seams.py` with reasons; the test fails if any pair exceeds them. Initial tolerances **[decision]**:
LOLA-family pairs (PGDA 78/90, LOLA LDEMs) median ≤ 2 m, p99 ≤ 20 m; SLDEM2015 vs LOLA median ≤ 5 m, p99 ≤ 40 m; eq↔polar
reprojection median ≤ 0.5 m, p99 ≤ 10 m. If a pair fails, the cause is investigated before any tolerance changes.

## 8. Coverage (`tools/globe/coverage.py`)
Area on the sphere per native-resolution class (≤ 5 m, ≤ 20 m, ≤ 40 m, ≤ 80 m, ≤ 160 m, ≤ 320 m, coarser, none), counting each
point once (zone rule above), from the finest-level masks block-reduced onto the L0 grids. Outputs: a global equirectangular
PNG + two polar PNGs + legend JSON under `web/public/globe/coverage/` (git-ignored: derived from NASA rasters) and a committed
`docs/v2/COVERAGE_SUMMARY.json` / `.md` with % of the Moon per class and per product.

## 9. VISUAL sub-resolution relief (`tools/globe/roughness.py`)
- `pyramid_visual/<zone>/<level>/<ix>_<iy>.tif`, one band `height_visual` = bilinear of the finest real level + fractal
  micro-relief that only adds wavelengths below 2× the native post.
- Spectrum: fBm with Hurst exponent H and RMS slope s(Δ) = s₀ (Δ/Δ₀)^(H−1). Parameters per 10 km cell from PGDA 70 (LOLA Hurst
  exponent and median/RMS slope maps) once S2 delivers it; **until then [decision]** fitted from the real DEM's own resolved
  relief at 2–8-pixel baselines and extrapolated, labelled `params_source: "self-fit"`.
- Noise: octave value noise on a global lattice hashed with a fixed seed → each tile is a pure function of its tile id
  (deterministic) and adjacent tiles match at their edges.
- Craters/boulders: only with cited published statistics; not added tonight (no citation checked) — listed as not done.
- **Roughness check:** RMS slope of the displayed surface at baselines 20 m … 2.56 km (powers of two; 17 m is not a multiple
  of the 5 m post) vs (a) the real PGDA 78 5 m surface at the same place, with VISUAL built from the 80 m PGDA 90 alone (a real
  ground-truth test of the statistical model), and (b) PGDA 70 per tile when available. Pass if displayed/reference is within
  [0.67, 1.5] at every baseline **[decision: provisional band; replace with PGDA 70's published spread when read]**.

## 10. Global analytics maps (§2.5, display-only, if time)
Slope (from the pyramid at L0–L2), roughness (PGDA 70 or self-fit RMS slope), Earth-visibility fraction (libration-aware; needs
horizon masks — likely not done tonight). PNGs git-ignored, summaries committed.

## 11. Tests
`tools/globe/tests/test_*.py` (pytest): each datum/frame conversion; grid/level/tile arithmetic; co-registration recovery;
feathering continuity; never-upsampled rule; stack sample/window/coverage on a synthetic mini-pyramid and on the real south
pyramid when present (skips cleanly otherwise); seam tolerance; roughness band; VISUAL guard. Plus `science/tests` stays green.

## 12. Acceptance
South polar zone built from PGDA 90 + PGDA 78 with seam QA within tolerance, coverage summary committed, VISUAL tiles for the
PGDA 78 sites with the roughness check reported, `TerrainStack` usable by S4. Products from S2 merged as they appear; anything
not merged by the end is listed as not done.
