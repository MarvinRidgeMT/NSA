# Phase 6 (prompt §3.1–3.2) — worlds abstraction + Mercury — results

Session R6, 16 Nov 2026 (~11:45–13:00 EST). Branch `claude/v2-r6-worlds-064d79`. Plan: `PHASE_6_WORLDS_PLAN.md`.
Labels: geometry **SOURCE-BASED · UNVALIDATED**; comms threshold and requirements **ENGINEERING ASSUMPTION**.

## 1. Worlds abstraction (§3.1) — done
`science/worlds/`: `World` (radius/shape, IAU rotation model, body-fixed frame + kernel note, Horizons centre and site
syntax, ellipsoid→sphere az/el frame tie, DEM stack, atmosphere, default requirements, comms assets, orbit, relief
bounds, availability), `get_world('moon' | 'mercury' | 'mars')`; Mars is declared with `available=False` and the reason.
The world is a context selector, not a scenario axis.

| Check | Result |
|---|---|
| Site04 RoI 3 through `science.worlds.moon.solve` (= `science.anysite.solve.solve`, unchanged) | **94.36 % / 72.11 % / 19 h; 20 clones 87.54–97.33 %**; skyline = committed bundle (≤ 1e-5°) |
| Moon Horizons query built by the world | identical to `science.horizons.build_params` and to the committed raw archive params |
| Generic layered skyline (`worlds/skyline.py`) with the Moon's radius | equals `science.skyline.compute_skyline` (elevations, status, reach, critical points, truncation) on a synthetic near/far pair with a no-data patch |
| Sphere geometry with R_Moon | bit-identical to `science.frames` |
| North polar stereographic vs PROJ | < 1 mm, both poles |
| Geodetic latitude on Horizons' Mercury ellipsoid | 85.8057964° and 1.72065 km = the Horizons header echo |

## 2. Mercury data (§3.2) — downloaded, public, no login
`python -m science.worlds.mercury.fetch` (the S2 fetcher, same manifest `$POLARIS_DATA/v2/manifest.jsonl`). **9.02 GB**,
49 files, every file SHA-256 in the manifest (5 USGS rasters also archive-MD5 verified); the PGDA 85 ZIP is extracted to
`mercury_pgda85_prokofiev/raw/` (derived, not in the manifest; the ZIP's SHA-256 is). Inventory and sizes:
`science/worlds/mercury/products.py`; credits in `docs/DATA_PROVENANCE.md` § Mercury.

Findings from the labels and cross-checks (each has a test in `science/worlds/tests/test_mercury_data.py`):
- **Datums differ by product.** MLA GDR v2 `hdem_75n_250m` heights are relative to **2 440.0 km** but its projection
  sphere is 2 439.4 km; MLA GDR v1 is relative to 2 439.4 km; PGDA 85 (km) is relative to 2 440 km; the USGS DEM is on
  2 439.4 km. After radius → height above 2 439.4 km: v2 − v1 median −3.3 m; PGDA 85 − MLA v2 median +1.9 m
  (r = 0.9992); USGS − MLA v2 median +18 m (r = 0.956). A wrong 600 m datum would show in every one.
- **Orientation**: PGDA 85 vs MLA correlate at r = 0.9992 only with the documented north-polar convention
  (x = ρ sin λ, y = −ρ cos λ); flipping the MLA y axis gives r = 0.23.
- **Co-registration residual** PGDA 85 vs MLA v2: best grid shift ≈ (−200, −100) m (std 41 → 34 m). Not corrected; used
  as a product member.
- **The posted PGDA 85 `.cub` is truncated at the source** (55.5 MB of the 95.3 MB its own label requires; bands 12–20
  incomplete). The per-layer ZIP from the same page is complete and is what is read.
- **Ice layer**: the ZIP contains `radar3b.map2.4rms.cub`, a georeferenced north-polar Arecibo radar map (2904² px,
  287.6 m, poleward of ~80° N; Harmon et al. 2011 data as resampled by PGDA 85). No public georeferenced *global* or
  south-polar radar-bright map was found (only figures such as PIA16514); not digitised.
- **MLA coverage is sparse at the site**: 0 laser shots in the site's 250 m pixel; 22 % / 16 % / 14 % of pixels within
  1 / 5 / 20 km have shots (v1 count grid). The GDR is interpolated between tracks.
- Relief bound for the curvature limit, measured: USGS −5 382 / +4 497 m, MLA −5 651 / +2 692 m (above 2 439.4 km) →
  +5.1 / −5.7 km.

## 3. Horizons for a Mercury surface site
- `CENTER='coord@199'`. Horizons' Mercury frame is IAU_MERCURY, **west-positive**: an east longitude is entered
  **negative** (it says so when given a positive one); verified by the header echo (W-lon = 360 − E-lon).
- Horizons uses an ellipsoid 2440.53/2440.53/2438.26 km. The site is passed **CYLINDRICAL** (Dxy, Dz from the
  planetocentric latitude and R + h on the 2 439.4 km sphere) so its position is exact; Horizons az/el (ellipsoid normal)
  are rotated about local east to the sphere normal used by the skyline: **0.00856°** at the site.
- **Independent check of longitude sign and azimuth**: the Sun direction recomputed from the Sun-centred sub-solar point
  (quantity 14) matches the topocentric table to **max 0.017°, median 0.014°** over 705 epochs (residual ≈ Mercury's
  orbital aberration, which only the topocentric value contains); the wrong-sign hypothesis is off by a median 43.6°.

## 4. Physics tests (§3.2) — pass
| Test | Analytic | From Horizons |
|---|---|---|
| Sun angular diameter over one Mercury year | 1.1419° (aphelion 0.4667 AU) – 1.7331° (perihelion 0.3075 AU), ratio 1.5178 = (1+e)/(1−e) | 1.14188° – 1.73310°, ratio 1.51776 |
| 3:2 resonance | P_orb / P_rot = 87.9691 / 58.6461 = 1.49999 | 87.9702 / 58.6466 = 1.5000 |
| Solar day | 1/(1/P_rot − 1/P_orb) = 175.939 d | 175.939 d (Sun azimuth advance over exactly 2 orbits = 360.003°) |
| Conjunctions (SEP < 2.3°) | synodic 115.88 d | superior 2027-01-01 (1.75°), inferior 2027-02-18 (3.71°), superior 2027-04-28 (0.30°); superior→superior 117.5 d |

A trap found and tested: the first time the Sun's azimuth advances 360° is **not** the solar day (164 d here) because
the equation of centre (±23.6°) modulates the Sun's motion; over exactly two orbital periods it cancels.

Outage rule: **SEP < 2.3° at superior conjunction** — DSN 810-005 module 106 Rev. B §2.3 (X-band BPSK data return "down
to at least 2.3 degrees"; Ka-band to 1°, kept as the alternative). Inferior conjunctions below the threshold are flagged
(Sun near the ground beam, module 105), not counted as outage. Direct-to-Earth only (no Mercury relay exists).

## 5. Mercury polar site end to end — Prokofiev rim
Bundle: `data/worlds/mercury/mercury_prokofiev_rim_2026-11-14_176d_mast1m.json` (`polaris-science-results-v1` core keys +
`world` block). Rebuild: `python -m science.worlds.mercury.site` (`--offline` uses the cached Horizons responses).

- **Site (rule fixed before the run)**: 85.3763943° N, 46.6196914° E, height −1 314.2 m above 2 439.4 km; on the rim
  annulus 55.9 km from Prokofiev's centre (85.77° N, 62.92° E, D 112 km), slope 14.5°, PGDA 85 max incident flux
  4 927 W/m² (the highest among 316 864 candidates).
- **Terrain**: near PGDA 85 hybrid MLA+SfS 125 m (25 m ray steps to 9.6 km), far MLA GDR v2 250 m, 125 m steps, range
  extended to the curvature requirement 219 km (relief ≤ +5.1 km); 720 bins, 0 truncated, 0 range-limited.
  Skyline −0.90° to +22.75° (median 3.68°).
- **Window**: 2026-11-14 00:00 → 2027-05-09 00:00 UTC, hourly, 4 225 samples = one solar day (2 Mercury years).

| Metric (1 m mast) | Mercury year 1 (88 d) | Solar day (176 d) | Flat-horizon control (solar day) |
|---|---|---|---|
| Sun centre visible | **54.61 %** | **41.42 %** | 49.94 % |
| Earth centre visible | **0 %** | **0 %** | 7.81 % (Earth peaks at +0.67° elevation) |
| Sun and Earth | 0 % | 0 % | — |
| Longest Sun gap | 959 h | 1 516 h | — |
| Direct-to-Earth available (Earth visible and no superior-conjunction outage) | 0 % | 0 % | — |

- **Why no Earth**: from 85.4° N, Earth never rises more than 0.67° above the mathematical horizon in this window, toward
  azimuth 139–201°, where the skyline is 1.1–1.4°. Mast sweep (same method): Earth first appears at **50 m** (0.26 % of
  the solar day) and reaches 3.05 % (DTE 2.37 %) at 100 m.
- **Product disagreement (3 members, not a probability)**: Sun % solar day 17.1–41.8 % (MLA v2 alone 17.1 %, PGDA 85
  shifted by the co-registration offset 41.6 %, MLA v1 41.8 %); Mercury year 1 34.3–56.2 %; Sun+Earth 0–1.1 % (only the
  MLA-v2-only member sees Earth). The 250 m MLA alone moves the answer by 24 points at this steep rim pixel.
- **Ice**: the site is not radar-bright (value 0.0); nearest radar-bright pixel (≥ 0.1, threshold ASSUMPTION from Eke
  et al. 2017) is 26.7 km away inside Prokofiev (85.761° N, 40.220° E). The site is the sunniest rim point, not a PSR
  (PGDA 85 max flux 4 927 W/m²).
- **Requirements** (Moon team values copied, ENGINEERING ASSUMPTION): Sun ≥ 70 % fails (41.4 % / 54.6 %), Sun+Earth
  ≥ 40 % fails (0 %).
- **Sections**: Decision Card (`polaris-decision-card-v1`) **not available for this world** (it needs
  `derived.arrival_slip` with clone members; Mercury has no clone DEMs) — a sourced requirements check is given instead;
  cube and sensitivity **not available for this world** (no T members, no mast/schedule grid); validation partial
  (`validation_status`: 7 checks pass, 2 not run).
- **Schema**: the bundle validates against `science-results-v1.schema.json` except `datum.radius_m`, which that schema
  pins to the Moon (const 1 737 400). A world-aware schema is an open item for the schema owner.

## 6. Hook for R1 / the coordinator (not done here — `science/anysite/**` is R1's)
Add `world=None` to `science.anysite.solve.solve()`: `curvature` with `R=world.radius_m, H=world.relief_max_m`;
`frames.destination/unit/moon_fixed` → `world.sphere`; `frames.stereo_forward` → each stack layer's own projection (as
`worlds/skyline.layered_skyline` does); `H.build_params` → `world.horizons_params` + `world.horizons_azel_to_sphere`;
bundle `datum`/`frame` from the world. With `world=None` or the Moon the path must stay byte-identical
(`science/worlds/tests/test_moon_world.py` is the guard). Until then Mercury runs through `science/worlds/mercury/site.py`.

## 7. Not done / open
- MLA/MESSENGER prime-meridian tie to Horizons IAU_MERCURY (labels do not state W0; an IAU 2009 W0 would move longitudes
  by 0.052° ≈ 160 m at the site) — **not run**.
- Independent illumination comparison (PGDA 85 publishes max flux and temperatures, not a Sun-visibility series) — not run.
- South-polar site (PGDA 88 DEM downloaded; reader works the same way) — not run. Any-site Mercury queries in the API/web — not done.
- Mercury Blender scene (R3), MDIS render twins (R4), MDIS mosaics used only as downloads so far.
- Mars (§3.3) not started (declared unavailable in the registry, by instruction).
