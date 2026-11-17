# Phase 6 / round 3 · T3 — solver/world follow-ups, then Mars — results

Session T3, 16–17 Nov 2026 (~23:40–01:00 EST). Branch `claude/v2-t3-mars-134ecc`. Plan: `PHASE_6_T3_PLAN.md`.
Labels: geometry **SOURCE-BASED · UNVALIDATED**; energy and comms thresholds **ENGINEERING ASSUMPTION**; no MODEL shipped
(no Mars sky model; said so in the bundle).

## 1. SLDEM2015 per-product adapter bug (R1 open item) — fixed
- **Cause**: `LegacyStack._point`, `_read_eq` and `EqDEM.sample` indexed every equirectangular product as if row 0 were at
  +90°. SLDEM2015 512 ppd comes as **32** tiles of 30° × 45° (60° S–60° N). So every row fell outside its tile, and
  `covering()` never listed SLDEM2015.
- **Fix**: the tiles of one product (same family, ppd, directory) become one mosaic entry `sldem2015:sldem2015_512`
  (184 320 × 61 440 px, 60° S–60° N, 0–360° E). Row 0 sits at `lat_top`, and each tile's offset comes from its label
  (`MAXIMUM_LATITUDE`, `WESTERNMOST_LONGITUDE`). Windows paste the tiles they touch and points read the one tile that holds
  them, with no resampling or fill. Provenance lists one SHA-256 per tile read. `_footprint_reach` now treats a
  360°-wide product that stops at ±60° as ending at its latitude edge.
- **Regression test** `science/anysite/tests/test_sldem_tiles.py` (5 tests). The reference indexes the raw `.img` with numpy
  through the label's own `LINE/SAMPLE_PROJECTION_OFFSET`, independently of the adapter. Coverage: covering at 7
  equatorial points, 45 random points plus tile-edge points, a window across the 30° N / 45° E corner of four tiles, and
  a window across the 0/360 seam and the equator. **All 5 fail on the old code and pass now.**
- **Effect**: only the per-product path changes (`POLARIS_ANYSITE_STACK=legacy`, and PyramidStack members at equatorial
  sites). At equatorial sites the legacy near field is now SLDEM2015 59 m, where it used to be LOLA 128 ppd. Polar sites
  are unchanged. Site04 RoI 3 is unchanged: 94.36 % / 72.11 % / 19 h, clones 87.54–97.33 % on the per-product path. The
  pyramid path is unchanged. Precomputed equatorial caches keyed on the product list will recompute on demand.

## 2. `world=` hook — done
`science.anysite.solve.solve(..., world=None)`, also `--world` on the CLI:
- `None` or `'moon'` runs the existing Moon code unchanged. The guards are `science/worlds/tests/test_moon_world.py` and
  `science/anysite/tests`, both green.
- Any other world runs `science.worlds.anysite.solve` with the same method. The world supplies its sphere and relief
  bound (curvature limit, range extended to L_req where the data reach, cap 600 km). It also supplies a terrain provider
  (layers in priority order, each sampled in its own projection through `worlds/skyline.layered_skyline`). Horizons uses
  `world.horizons_params`, with the frame-tie longitude offset and the ellipsoid → sphere az/el tie. Then come
  `hourly_metrics` (unchanged), the flat-horizon control, product members, and DTE with the SEP rule. The bundle takes
  its `datum`/`frame` from the world.
- **Check**: Mercury Prokofiev through the hook equals R6's bundle exactly. The skyline max difference is 0, and the
  results are 41.42 % / 0 % / 1 516 h at height −1 314.19 m (`test_world_anysite.py`).

## 3. Mercury open items — done
**MLA prime-meridian tie** (`science/worlds/pck.py`, `frame_tie.py`, `test_frame_tie.py`):
- The MLA RDR SIS says the release uses `pck00010_msgr_v21.tpc`. In the archived MESSENGER PCK (v2.0–2.3; the later
  versions change commentary only), Mercury has W0 329.5988°, Ẇ 6.1385108°/d and pole 281.0103/61.4155, which are the
  IAU 2015 values.
- What Horizons uses was measured independently of any DEM. Geocentric quantity 14 (sub-observer point) was compared with
  light-time-corrected vectors, using 74 epochs from 2026-11-14 to 2027-11-14. **IAU 2015 (pck00011) reproduces Horizons to
  ≤ 1e-6° (lon and lat); IAU 2009 (pck00010) is off by 0.135°.**
- So the **MLA → Horizons longitude offset is 0**, and the 0.052° worry in R6's notes does not apply.
- Found on the way: Horizons' quantity 14 is light-time only, without stellar aberration (with LT+S the residual is
  0.0055°).

**South-polar site** (`science/worlds/mercury/south.py`, `terrain.py`;
bundle `data/worlds/mercury/mercury_south_pole_high_2026-11-14_176d_mast1m.json`):
- **PGDA 88 checks**: orientation r = 0.68 against USGS (mirrored grids 0.08–0.11; the file history records a FLIPUD).
  Datum: my PGDA 88 − USGS equals the producer's `minus_USGS` layer to a −0.7 m median. Heights are in m on 2 439.4 km.
- **Site rule** (fixed in the plan): the highest PGDA 88 pixel within 2° of the pole with slope < 15°. That is
  **88.0570177° S, 135.0° E, +1 486.18 m**, slope 1.7°, chosen from 355 638 candidates.
- **Terrain**: PGDA 88 250 m, then USGS 665 m beyond 75° S. The range was extended to L_req = 289.9 km. There are 0
  truncated bins and 0 range-limited bins.

| One solar day (176 d), 1 m mast | Terrain | Flat-horizon control |
|---|---|---|
| Sun centre visible | **65.42 %** (Mercury year 1: 78.04 %) | 50.39 % |
| Earth centre visible | **100 %** | 96.52 % |
| Sun and Earth | 65.42 % | — |
| Longest Sun gap | 1 461 h | — |
| DTE (Earth visible and no superior-conjunction outage) | **94.89 %** | — |

- Product members (not probabilities): USGS 665 m alone and PGDA 88 filled, Sun 48.07–65.42 %.
- Mast sweep for Sun: 1 m 65.4 %, 10 m 95.3 %, 50 m 96.2 %, 100 m 96.6 %. The Sun grazes this horizon (max elevation
  1.95°), so a few metres of mast matter a lot.
- PSR mask: the site is not in a PSR; the nearest PSR pixel is 13.6 km away.
- Requirements (Moon values, ENGINEERING ASSUMPTION): Sun ≥ 70 % fails; Sun+Earth ≥ 40 % passes.
- R6's 0.014–0.017° sub-solar residual for Mercury is **Sun–Mercury light time** (Ẇ × τ ≈ 6.14°/d × 3.2 min), not
  aberration. Corrected in the Mars check below; R6's Mercury code is unchanged.

## 4. Mars (§3.3) — done for one site; parts not available, listed below
**World** (`science/worlds/mars/world.py`):
- **Geometry**: NAIF 499, `coord@499` CYLINDRICAL with east longitude entered negative (IAU_MARS is west-positive),
  confirmed by the header. Horizons radii are 3396.19/3396.19/3376.20 km. Heights and rays use the **MOLA sphere
  3 396 000 m**.
- **Rotation and frame tie**: IAU 2015 rotation with periodic terms from pck00011. MOLA ("IAU2000" = pck00010) → Horizons
  (IAU 2015) longitude offset **−0.00352°** at the window midpoint (~180 m), applied to the Horizons site longitude and
  recorded. The 0.0006° pole difference is not applied.
- **Relief bound**: +21.5 / −23.4 km, measured on MOLA (16 ppd max +21 280 m at Olympus Mons). The bound is world-wide and
  conservative.
- **Atmosphere**: estimated refraction ~0.007° is not applied (AIRLESS). Tau is an explicit energy input, and no sky
  model is shipped.
- **Comms**: DTE + SEP rule. Relays MRO, MAVEN, TGO and MEX are **not available for this world** (no ephemerides wired).

**Data** (public, no login, `python -m science.worlds.mars.fetch`): **0.533 GB, 28 files**, every file SHA-256 in the
manifest.
- MOLA MEGDR 4 ppd (radius/topography/areoid/counts), 16 ppd (radius/topography/areoid) and the 128 ppd tile 44n000
  (radius/topography/counts).
- Mars 2020 science CTX DEM 20 m (whole crater) and Mars 2020 TRN CTX DTM 20 m.
- NAIF pck00010, pck00011 and MESSENGER pck00010_msgr_v23.
- HiRISE 1 m TRN tiles are catalogued, not downloaded: 7 × 72–132 MB, covering the landing ellipse rather than the rim.

**Datum trap, settled by data** (`test_mars.py`):
- The CTX file names say "MOLAtopography_DeltaGeoid", while the XML says values "refer to the Mars 2020 IAU Sphere
  3396190 m".
- CTX − MOLA topography gives median **−0.6 m** (science mosaic) and **+1.7 m** (TRN), MAD 8–10 m. CTX − (radius −
  3 396 190 m) gives median **+1 691 m**. So **the heights are areoid heights**.
- They are converted with the MOLA 16 ppd areoid product. After conversion, CTX − MOLA radius has median −1.2 m and
  r = 0.995.
- The areoid is not taken as megr − megt at 128 ppd. Those layers are a mean radius and a median topography, which differ
  by up to 1.5 km in rough bins.

**Seasons via Ls** (`seasons.py`):
- Allison & McEwen (2000) / Mars24 reproduces the published worked example (2000-01-06 → Ls 277.18758°).
- Against Horizons' sub-solar latitude: **max 0.0052°** over 2 749 six-hourly epochs.

**Jezero rim** (`site.py`; bundle `data/worlds/mars/mars_jezero_rim_2026-11-14_687d_mast1m.json.gz`, 10.3 MB JSON / 1.6 MB gzip since 17 Nov):
- **Crater**: Gazetteer feature 14300 (MDIM 2.1) puts the centre at 18.41° N, 77.69° E, D 47.52 km.
- **Site rule**: the highest CTX radius height in the 0.85–1.15 R annulus with slope < 15°. That gives
  **18.1758836° N, 78.1081993° E, −2 722.94 m**, slope 0.39°, 27.32 km from the centre.
  - This sits on the outer edge of the annulus (1.15 R). The terrain keeps rising east of the rim, so this is the rule's
    answer rather than a rim crest. The rule was left as fixed.
- **Terrain**: CTX 20 m to 12.5 km at 4 m steps, then CTX and MOLA 128 ppd at 100 m steps to L_req = 500.6 km, with MOLA
  16 ppd as fill. There are 0 truncated bins; 1 bin is flagged range-limited against the world-wide (Olympus) bound.
- **Window**: one Mars year, 2026-11-14 → 2028-10-01, hourly, 16 489 samples; Ls 21.6° → 21.0°.

| One Mars year, 1 m mast | Terrain | Flat-horizon control |
|---|---|---|
| Sun centre visible | **45.55 %** | 50.43 % |
| Earth centre visible | **46.06 %** | 51.38 % |
| Sun and Earth | 39.86 % | — |
| Longest Sun gap | 15 h | — |
| DTE (Earth visible, no superior-conjunction outage) | **44.83 %** | — |

- **Superior conjunction** 2028-03-11 → 2028-03-31 (SEP min 0.81°, 20 days below 2.3°, 203 Earth-visible hours lost).
- **Members**: MOLA only 47.12 %; TRN CTX does not hold the rim site, recorded as "not available".
- **Mast sweep (Sun)**: 1 m 45.6 %, 10 m 47.1 %, 50 m 48.5 %.
- **Seasons**: Sun 47.3 / 47.3 / 43.5 / 43.3 % for northern spring / summer / autumn / winter.
- **Direct-beam horizontal energy per sol** (terrain-gated; ENGINEERING ASSUMPTION, diffuse omitted) is below. The terrain
  costs ≤ 1.2 % of the direct energy, because the hours it hides are low-Sun hours.

| Season | TOA | τ 0.3 | τ 0.5 | τ 1 | τ 2 | τ 5 |
|---|---|---|---|---|---|---|
| N spring (Ls 0–90) | 5 066 | 3 532 | 2 801 | 1 578 | 508 | 18 |
| N summer (Ls 90–180) | 4 499 | 2 899 | 2 242 | 1 209 | 374 | 14 |
| N autumn (Ls 180–270) | 4 219 | 2 542 | 1 872 | 904 | 230 | 5 |
| N winter (Ls 270–360) | 3 909 | 2 352 | 1 733 | 837 | 213 | 5 |

(Wh/m²/sol)

**Checks** (all in `validation_status`):

| Check | Result |
|---|---|
| Frame tie, Horizons model | IAU 2015 reproduces quantity 14 to 5e-5°; IAU 2009 off by 0.0024° |
| CTX datum | areoid (see above) |
| Ls vs Horizons sub-solar latitude | max 0.0052° |
| Longitude sign / azimuth, via the sub-solar point | max **9e-5°**, after advancing the sub-solar longitude by Ẇ × Sun–Mars light time (3.1°); wrong-sign hypothesis 84.5° |
| Sun angular size vs 2 asin(R☉/r) | difference 0.0°; range 0.3199–0.3858° |
| Mean solar day from local noons (668 noons) | 88 775.5 s vs 88 775.244 s |
| MOLA data density | 0 shots in the site's 128 ppd bin; 12 / 32 / 31 % of bins with shots within 2 / 5 / 20 km |
| Independent illumination comparison | not run |

- **Sections**: Decision Card, cube and sensitivity are **not available for this world** (no clone DEMs, no arrival-slip
  run). The sky model is **not available** either. A requirements check is given instead: Sun ≥ 70 % fails; Sun+Earth
  ≥ 40 % fails at 39.86 %.

## 5. Not done
- Mars relay comms: no orbiter ephemerides wired (MRO/MAVEN/TGO/MEX are SPK-only in Horizons; access windows need orbit
  propagation and antenna geometry).
- Mars sky / diffuse model; dust deposition; panel orientation.
- HiRISE 1 m at a floor site. HRSC DTMs as a separate member: the CTX DEMs are aligned to HRSC; HRSC itself is not
  downloaded.
- Clone/realization members for Mercury and Mars, so no cube or Decision Card there.
- Independent illumination comparison for either world.
- A world-aware results schema. `science-results-v1` pins `datum.radius_m` to the Moon, so the Mercury and Mars bundles
  fail only that key.
- Mars Blender scene and render twins.
- Rerunning the Moon precompute: equatorial legacy caches now include SLDEM2015.
