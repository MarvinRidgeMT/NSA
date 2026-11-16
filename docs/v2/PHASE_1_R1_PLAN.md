# v2 round 2 · R1 — the whole-Moon pyramid as the any-site solver's default terrain (plan, 16 Nov 2026)

Owner: R1 (`science/anysite/**`, API additions to `science/terrain/stack.py`, `data/anysite/**`). Branch
`claude/v2-r1-pyramid-solver-e4bb91` (already contains 72e3430; kept the worktree's branch name). Labels unchanged:
geometry **SOURCE-BASED · UNVALIDATED**; members "k of N maps is not a probability"; error-model members **assumed error
model**.

## 1. Problem (from the round-1 integration, `SESSION_REPORT_2026-11-16.md`)
With S3's merged `TerrainStack` as the default the any-site path (a) lost the PGDA 78 clones and product-disagreement
members (the pyramid exposes one merged surface), (b) changed its near field (12.5 km window instead of the 5 m tile's
6.317 km inscribed radius, so Site04 RoI 3 no longer equalled the committed bundle bit for bit), (c) could not use eq-zone
`local-stere` windows (`SPView` expects a CRS WKT, not an oblique stereographic grid).

## 2. Design
**One question per source.** The pyramid answers "what is the best merged terrain here?" and supplies the nominal near
and far fields. The per-product adapter (`LegacyStack`) answers "what if the terrain were product X / clone k?" and
supplies every uncertainty member. `get_stack()` returns `PyramidStack`, which holds both:

| | nominal | members |
|---|---|---|
| near field | pyramid window at the finest level with data at the site (`ZoneDEM`, proj `sp`/`np`/`local-stere`) | clone tiles / other products from `LegacyStack`, raw, unchanged |
| far field | pyramid, lazily sampled at the far level (polar L4 = 80 m, eq L3 = 118 m) across zones | the nominal (pyramid) far field |
| ray step near | level pixel / 5 (1 m on L8 = 5 m) | member's native resolution / 5 |

Fallback: `POLARIS_ANYSITE_STACK=legacy` (or no pyramid index on disk) gives the per-product adapter, as before.

**Near-field rule (documented, replaces "inscribed radius of the 5 m tile").** Let `L*` be the finest pyramid level with
data at the site and `p` its pixel (m). Read a window of half-width `min(25 km, 3000 p)` at `L*`. A pixel is *fine* if its
height is finite and its `native_res_m ≤ 1.05 p` (i.e. it is native at `L*`, not the feather band of a coarser
contributor and not NaN). `d_fine` = Euclidean grid distance from the site to the nearest non-fine pixel centre (or to the
window edge). The fine ray step is used to

    near_cut = min(d_fine − √2·p, cap),   cap = 12.5 km if L* is finer than the far level else 25 km

(`√2·p`: a bilinear sample uses the four surrounding pixel centres, which lie within √2·p of the sample point, so every
fine-step sample inside `near_cut` is interpolated from fine pixels only). Beyond `near_cut` the near window is still
preferred wherever it has data, sampled at the far step (compute_skyline's rule, unchanged). Members use
`min(nominal near_cut, the same rule applied to the member's own window)`.

At Site04 RoI 3 the rule gives ≈ 6.62 km (disc to the edge of the 5 m data minus the 8-pixel feather band), not
6.317 km (square inscribed radius of the raw tile). The two are different definitions; the any-site pyramid path cannot
be bit-identical to the committed bundle because (i) the pyramid feathers the outer 8 px (40 m) of the PGDA 78 tile into
PGDA 90, (ii) its far field is the merged 80 m level (PGDA 78 block-averaged inside the tile, PGDA 90 / LOLA outside) not
raw PGDA 90, and (iii) the near cut differs. Therefore:
- the **identity** test (skyline ≤ 1e-5°, near cut 6317.166 m, far array SHA-256) stays on the per-product path
  (`stack=LegacyStack()` explicitly);
- a **pyramid-path** test asserts the same hourly metrics (94.36 % / 72.11 % / 19 h, clones 87.54–97.33 %) and a skyline
  tolerance measured once and set with margin (documented in the test).

**Eq-zone windows.** A generic `LatLonView` wraps any `ZoneDEM` whose `proj` is not `sp`: compute_skyline's south-polar
(x, y) → lat/lon (exact closed-form inverse) → the window's own `forward` (`np` stereographic or oblique stereographic) →
bilinear. `sp` windows go straight in (bit-identical to before).

**Far field, lazily.** A dense ±290 km window is 7250² px (≈ 0.9 GB with its bands, 6.6 s at RoI 3) and in the eq zone
needs 52 M point queries; it also cannot cross a zone boundary (a 58° site's polar grid has no data equatorward of 55°).
`PyramidField` samples the pyramid at the ray points through a new `TerrainStack.sample_height(lat, lon, max_level)`
(API addition: the same bilinear + zone-blend rule as `sample`, restricted to levels ≤ `max_level`, coarser levels fill
gaps; one tile gather per level). Its `Z` (used only for the beyond-range bound and `H_regional_max_m`) is the maximum of
a coarse grid over the window (an *estimate*, not a bound; the world bound +10,786 m is recorded separately as before).
Provenance: the pyramid `index.json` SHA-256 and the tiles each field read (zone/level/ix/iy + SHA-256 from the index).

**Members.** Product family of the pyramid's source at the site (`source_id` → `pgda78`, `pgda90`, `sldem2015`, …):
- clones: where that family has clones cached for the covering legacy entry (PGDA 78 Site01/Site04);
- assumed error model: applied to the pyramid near window, with the error model of that family;
- products (M): every other product family covering the site in `LegacyStack`, one member each (finest).

**Cache key.** `SOLVER_VERSION = 'anysite-3'`; the product list carries `pyramid@<index sha256[:12]>`, so a rebuilt pyramid
invalidates cached bundles.

## 3. Tests (`science/anysite/tests/`)
1. Per-product identity at Site04 RoI 3 (unchanged numbers, explicit `LegacyStack`).
2. Pyramid default at Site04 RoI 3: metrics, clones, product members, near-cut rule value, skyline tolerance.
3. `sample_height` equals `sample` (heights) where `max_level` ≥ the finest level; respects `max_level`.
4. Flat sphere through the pyramid machinery: a synthetic pyramid (constant height, eq and np tiles, written to a temp
   dir) → `PyramidStack` → solver terrain stage → every bin equals the closed-form dip (≤ 1e-4°) at an equatorial, a
   mid-latitude and a north-polar site.
5. Real data, end to end: Apollo 11 (equatorial, flat mare) and Chang'e 3 (44° N) on the pyramid: 0 truncated bins,
   horizon plausible for a mare (|el| small), Earth always up at Apollo 11; skyline vs the per-product path agrees within a
   stated tolerance.
6. North-pole sanity on the north-polar pyramid (89.5° N, `np` zone): 0 truncated, Sun ≤ 2.2°.
7. `get_stack()` default is the pyramid; `POLARIS_ANYSITE_STACK=legacy` gives the adapter.

## 4. Precompute
`python -m science.anysite.precompute --workers 4` on the pyramid: 4 current sites, landing sites, ≈1° grids poleward of
80° at both poles, plus a new coarse global 10° grid. Record per-site wall time (target ≤ 60 s per new site) in
`data/anysite/precompute_summary.json` and the BUILD_STATUS entry.

## 5. Not in scope
Pyramid building/QA (R2), Blender (R3), anything outside `science/anysite/**` except the `sample_height` API addition and
an appended contract amendment.
