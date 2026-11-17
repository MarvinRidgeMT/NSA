# Phase 6 / round 3 · T3 — solver/world follow-ups, then Mars (prompt §3.3) — plan

Session T3, 16–17 Nov 2026. Branch `claude/v2-t3-mars-134ecc` (already contains 13551d0, the round-3 split, so no new
branch was cut). Owns `science/worlds/**`, `science/anysite/**`, Mars/Mercury data under
`$POLARIS_DATA/v2/products/{mars,mercury}_*` (`$POLARIS_DATA` = `data/cache`, symlinked, never committed).
Labels: geometry **SOURCE-BASED · UNVALIDATED**; energy **ENGINEERING ASSUMPTION**; any sky/atmosphere model **MODEL**.
Order: one small validated step per commit; Moon numbers must not move.

## 1. SLDEM2015 per-product adapter bug (R1 open item)
**Cause.** `LegacyStack._point`, `_read_eq` and `EqDEM.sample` turn a latitude into a row with `(90 − lat) · ppd`, which
holds for a global grid (row 0 at +90°). SLDEM2015 512 ppd comes as 32 tiles of 30° × 45°, so every row index lands outside
the tile and `covering()` never lists SLDEM2015.
**Fix.** `_pds_products` reads `MAXIMUM_LATITUDE` / `WESTERNMOST_LONGITUDE` from each label and groups the tiles of one
product (same family, ppd, tag prefix) into ONE mosaic entry (`sldem2015:sldem2015_512`, 60° S–60° N, 0–360° E, 61 440 ×
184 320 px) with the tile list. Row index = `(lat_top − lat) · ppd`; a window reads from every tile it touches (no
resampling, no fill); a point reads from the one tile that holds it. Global products keep `lat_top = 90` (unchanged).
**Regression tests** (`science/anysite/tests/test_sldem_tiles.py`): (a) `covering()` lists SLDEM2015 at three equatorial
points; (b) `_point` equals a raw read of the PDS `.img` at the computed row/column (independent indexing from the label's
`LINE_PROJECTION_OFFSET`/`SAMPLE_PROJECTION_OFFSET`); (c) a window spanning a tile corner equals the four raw tile reads
pasted together; (d) the polar/global entries are unchanged (Site04 RoI 3 per-product path still identical to the bundle).

## 2. `world=` hook in the any-site solver
`science.anysite.solve.solve(lat, lon, …, world=None)`: `None` or `'moon'` → the existing code path, untouched (the Moon
guard tests stay byte-identical: Site04 RoI 3 94.36 % / 72.11 % / 19 h, clones 87.54–97.33 % on the per-product path; the
pyramid path within its documented tolerance). Any other world → `science.worlds.anysite.solve(world, lat, lon, …)`: the
same method with the world's sphere, relief bound (curvature limit), per-layer projections (`worlds/skyline.layered_skyline`,
already proven equal to the Moon code), Horizons syntax (`world.horizons_params`, ellipsoid→sphere tie), and a world DEM
stack (`world.terrain(lat, lon, range)` → near/far layers with provenance). Bundle `datum`/`frame` from the world. Mercury
and Mars plug in through that interface.

## 3. Mercury open items (R6)
- **MLA prime-meridian tie.** The MLA RDR SIS names `pck00010_msgr_v21.tpc`; the archived MESSENGER PCK (v2.0–2.3, same
  Mercury block) gives W0 = 329.5988°, Ẇ = 6.1385108°/d (Stark et al. 2015, Mazarico et al. 2014) = the IAU 2015 values.
  The open question is what Horizons' IAU_MERCURY uses. Test: geocentric Horizons quantity 14 (sub-observer longitude)
  vs the sub-observer longitude computed from each candidate PCK model (IAU 2009 `pck00010`, MESSENGER/IAU 2015) with
  TDB time and light time. The model that matches to ≲ 0.01° is Horizons'. The resulting MLA↔Horizons longitude offset
  at the window epoch is applied as a sensitivity (site re-run with the shifted Horizons longitude), not silently.
- **South-polar site end to end.** PGDA 88 SfS DEM 250 m (75–90° S) near and far, USGS 665 m as far fill only if the
  curvature range leaves PGDA 88. Site rule fixed before the run: the 250 m pixel within 88–90° S with the highest
  Sun-visibility fraction from a first coarse skyline screen is NOT used (that would be choosing by the answer); instead
  the rule is **the highest-elevation pixel with slope < 15° within 2° of the pole** (a rim/ridge proxy, as for Prokofiev),
  ties → nearest the pole. Same window (one solar day), same metrics, flat-horizon control, mast sweep, members
  (PGDA 88 filled vs unfilled, USGS 665 m).

## 4. Mars (§3.3)
- **World.** NAIF 499, `coord@499`; Horizons IAU_MARS is west-positive (E-lon entered negative, verified from the header
  echo); radii from the Horizons header; heights and rays on the **MOLA reference sphere 3 396 000 m** (MEGDR radius
  files: radius − 3 396 000 m). IAU 2015 rotation (Archinal et al. 2018, with periodic terms) evaluated from NAIF
  `pck00011.tpc`; MOLA frame tie by the same quantity-14 test (MOLA uses the IAU 2000 model, Seidelmann et al. 2002).
  Atmosphere `mars`; refraction estimated (≈ 0.01° at the horizon for 6 mbar) and **not applied** (`APPARENT=AIRLESS`),
  stated in limitations.
- **Data (public, no login, ≤ 30 GB; plan ≈ 0.6 GB).** MOLA MEGDR (PDS Geosciences `mgsl_300x`): 4 ppd radius /
  topography / areoid / counts; 16 ppd radius / topography / areoid; 128 ppd tiles `megr|megt|megc44n000hb` (0–44° N,
  0–90° E: Jezero). Jezero CTX DEM 20 m (JPL/USGS Mars 2020 science-investigation mosaic, 90 MB) and the Mars 2020 TRN CTX
  DTM 20 m (10 MB). HiRISE 1 m tiles are 72–132 MB each but cover the landing ellipse, not the rim: one is catalogued, not
  needed for the rim site.
- **Datum trap to settle by data, not by label prose.** The CTX files are named `MOLAtopography_DeltaGeoid` while their
  XML says "refer to the Mars 2020 IAU sphere 3 396 190 m". Test: CTX − MOLA topography (areoid heights) vs CTX − (MOLA
  radius − 3 396 190 m) over the overlap; the hypothesis with |median| ≲ tens of m wins and is converted to radius
  (areoid at 128 ppd = megr − megt + 3 396 000 m).
- **Seasons via Ls.** Allison & McEwen (2000) / Mars24 algorithm from UTC (TT), checked independently against the
  sub-solar latitude from Horizons (sin φ_ss = sin ε sin Ls, ε from the IAU pole and Mars' orbit) — tolerance 0.1°.
  Metrics per Ls quarter (0–90 spring … 270–360 winter, northern hemisphere).
- **Window.** One Mars year from 2026-11-14, hourly (≈ 16 488 samples per body), Horizons only, no extrapolation.
- **Energy (ENGINEERING ASSUMPTION).** Tau is an explicit input (default sweep 0.3, 0.5, 1, 2, 5); horizontal direct
  irradiance = S_mars(r) · μ · exp(−τ/μ) while the Sun centre is above the terrain skyline (Beer–Lambert, direct beam only).
  The diffuse sky term is **omitted** (so the number is a lower bound on the direct component, not total insolation); no
  Mars sky model is shipped (said so in the bundle).
- **Comms.** Direct-to-Earth geometry (Earth above the terrain skyline) + the SEP < 2.3° outage rule (same DSN 810-005
  source as Mercury). Relay orbiters (MRO, MAVEN, TGO, Mars Express): **not available for this world** — no relay
  ephemerides wired.
- **Site rule (fixed before the run).** Jezero crater: highest point of the CTX DEM inside the rim annulus 0.85–1.15 R
  with slope < 15° (CTX 20 m, slope over 3×3), ties → nearest the centre. Crater centre and diameter read from the USGS
  Gazetteer before the run (feature 14300, MDIM 2.1): 18.41° N, 77.69° E, D 47.52 km (encyclopaedia values 18.38° N,
  77.58° E, 45 km were not used).
- **Bundle.** `data/worlds/mars/mars_jezero_rim_<start>_<days>d_mast1m.json`, `polaris-science-results-v1` core keys + a
  `world` block, with Decision Card / cube / sensitivity marked "not available for this world" with reasons (no clone
  members), product members CTX-science / CTX-TRN / MOLA 128 ppd, flat-horizon control, mast sweep, Ls seasons, tau sweep.
- **Checks.** Sun angular size vs heliocentric distance (analytic); sidereal rotation from the Sun azimuth over many sols
  (sol 88 775.244 s); longitude sign via the sub-solar point (as Mercury); Ls vs sub-solar latitude; frame tie; CTX/MOLA
  datum; MOLA radius − topography = areoid (16 ppd product) consistency.

## 5. Not planned here
Web, exports/API (T1/T2); render-vs-real (R4); Mars Blender scene; ground imagery; relay ephemerides.

## As built (17 Nov 2026)
See `PHASE_6_T3_RESULTS.md`. Deviations from this plan: the areoid for the CTX conversion is the MOLA 16 ppd areoid
product, not megr − megt at 128 ppd (mean-radius vs median-topography bins differ by up to 1.5 km); the sub-solar longitude
check needs the Sun–planet light-time rotation (3.1° for Mars); HiRISE not downloaded (it does not cover the rim site).
