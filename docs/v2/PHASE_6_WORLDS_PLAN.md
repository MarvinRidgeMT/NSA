# Phase 6 (prompt §3.1–3.2) — worlds abstraction, then Mercury — plan

Session R6, round 2 (16 Nov 2026). Branch `claude/v2-r6-worlds-064d79` (cut from `feature/v2-whole-moon` at 72e3430).
Owns `science/worlds/**` and Mercury data under `$POLARIS_DATA/v2/products/mercury_*` (`$POLARIS_DATA` = `data/cache`).
Labels: geometry **SOURCE-BASED · UNVALIDATED**; anything assumed (comms thresholds, requirements) **ENGINEERING ASSUMPTION**.

## 0. Ground rules for this phase
- The world is a **context selector**, never a scenario axis: a bundle belongs to one world; the 6D cube axes are unchanged.
- **Moon numbers must not move.** The Moon world *wraps* the existing code (`science.frames`, `science.horizons`,
  `science.skyline`, `science.anysite.solve`) and adds nothing to its path. A test re-derives Site04 RoI 3
  (94.36 % / 72.11 % / 19 h, 20 clones 87.54–97.33 %) through the world API.
- `science/anysite/**` is being changed by R1 in parallel: R6 does **not** edit it. The world layer calls its public
  `solve()` for the Moon, and for other worlds runs its own small pipeline that reuses the generic pieces
  (`science.crossings`, `science.horizons.parse_text`, `science.anysite.ephem.fetch_cached`, `science.dem.ArrayDEM`).
  §6 below is the hook R1/the coordinator should add so the any-site solver can take a `world=` argument later.
- Never invent heights; never fill an absent product. Every downloaded file: public, no login, SHA-256 in the manifest.

## 1. `science/worlds/` layout
| File | Contents |
|---|---|
| `base.py` | `World` dataclass + `RotationModel`, `CommsAsset`, `DemProduct`; `horizons_params()`; frame-tie helper |
| `geometry.py` | sphere geometry parameterised by radius (destination, unit, body-fixed point, elevation), polar stereographic (N/S) |
| `skyline.py` | `compute_skyline(world, …)`: Moon → `science.skyline.compute_skyline` unchanged; other worlds → generic single-DEM ray caster (same algorithm, radius and projection from the world). Test: generic with Moon parameters equals the Moon code bit for bit |
| `moon.py` | `MOON`: R 1 737 400 m, IAU 2015 rotation, MOON_ME/MEAN_ME note, `coord@301` GEODETIC (sphere radii), DEM stack = S2/S3 products, DSN direct-to-Earth, `solve()` = `science.anysite.solve.solve` |
| `mercury/world.py` | `MERCURY`: datum sphere 2 439.4 km, Horizons ellipsoid 2440.53/2440.53/2438.26 km, IAU_MERCURY (west-positive in Horizons), DSN direct-to-Earth with conjunction flagging |
| `mercury/products.py` | catalogue (same `Product`/`FileSpec` as `tools/globe/products.py`), product ids `mercury_*` |
| `mercury/fetch.py` | runs `tools.globe.fetch.fetch_product` on that catalogue (same manifest file, same line format) |
| `mercury/dem.py` | PDS3 IMG (MLA GDR) and ISIS3 cube readers → `ArrayDEM` in the product's own polar-stereographic grid, heights re-referenced to the world datum |
| `mercury/physics.py` | Sun angular size vs heliocentric distance, 3:2 resonance / solar day, Sun–Earth–probe (SEP) conjunction flags |
| `mercury/site.py` | end-to-end polar site → bundle (`polaris-science-results-v1` shape + `world` block) |
| `registry.py` | `get_world('moon' | 'mercury' | 'mars')`; Mars = declared, `available=False` with the reason |
| `tests/` | Moon regression, geometry/skyline equality, Horizons parameter identity, Mercury physics, DEM conventions, site bundle |

## 2. `World` fields (§3.1)
name, NAIF id, Horizons `CENTER` (`coord@301`, `coord@199`), Horizons longitude convention (Moon east-positive; Mercury
IAU **west-positive**: Horizons asks for east longitude entered **negative**, verified 16 Nov 2026 — the header then
echoes W-lon = 360 − E-lon), Horizons site coordinate type (Moon `GEODETIC` on its sphere = the existing query, byte for
byte; Mercury `CYLINDRICAL` so that the site radius is exact on the DEM datum sphere instead of Horizons' ellipsoid),
reference sphere radius for heights, the Horizons body radii, IAU rotation model (α0, δ0, W0, Ẇ and source),
body-fixed frame name and SPICE kernel note, sidereal rotation and orbital period, perihelion/aphelion, relief bounds
(curvature limit), atmosphere (`none` | `mars`), default requirements (copied from the Moon defaults, marked
ENGINEERING ASSUMPTION where not world-specific), comms assets (DSN direct-to-Earth; relays only where ephemerides are
wired — none for Mercury, none yet for the Moon), DEM stack (ordered product descriptors), and `available` + reason.

## 3. Mercury data (§3.2) — inventory 16 Nov 2026, all public, no login
| product_id | What | Size | Use |
|---|---|---|---|
| `mercury_mla_gdr_v2` | MLA GDR v2 `hdem_75n_250m` (75–90° N, 250 m, PDS Geosciences messmla_2101) | 0.05 GB | north-polar terrain (primary) |
| `mercury_mla_gdr_v1` | MLA GDR v1: `hdem_45n_{250,500,1000}m`, `hdem_64`, `hdem_16`, `msgr_dem_mla_np_v01`, shot counts `hdec_45n_250m`, `hdec_64` | 2.0 GB | far field, data-density honesty layer |
| `mercury_usgs_dem_665m_v2` | USGS MESSENGER global DEM 665 m v2 (Becker et al. 2016), int16 GeoTIFF | 0.53 GB | global terrain, independent geometry check |
| `mercury_mdis_bdr_166m` | MDIS BDR global mosaic 166 m (latest USGS release) | 4.25 GB | albedo for Blender (R3, later); VISUAL |
| `mercury_mdis_polar_250m` | MDIS north/south polar mosaics 250 m (2013) | 0.15 GB | VISUAL polar context |
| `mercury_mdis_color_665m` | MDIS enhanced-colour global mosaic 665 m | 0.80 GB | VISUAL |
| `mercury_pgda85_prokofiev` | PGDA 85 Prokofiev hybrid MLA+SfS stack 125 m (DEM, slope, illumination, temperatures, ice depth, **radar** layer) | 0.10 GB | site DEM, **ice layer (radar-bright)** |
| `mercury_pgda88_south_pole` | PGDA 88 / Zenodo 10.5281/zenodo.19740142 south-polar SfS DEM 250 m (v1.1.0) | 0.56 GB | south-polar terrain |
| `mercury_mla_radr_v4` | PGDA 64 recalibrated MLA reflectance (RADR v4) | 0.60 GB | ice reflectance context |
Total ≈ 9 GB (cap 30 GB). Not available as public data (searched): a georeferenced global radar-bright map (Harmon et al.
2011 Arecibo images exist only as figures, e.g. PIA16514) → the ice layer is the Prokofiev radar layer only, and the
global layer is recorded as "not available". MDIS LOI 166 m mosaic (4.2 GB) catalogued, not downloaded (duplicate of BDR
use). Datum traps found in the labels: `hdem_75n_250m` heights are relative to **2 440.0 km** but its projection sphere is
**2 439.4 km**; `msgr_dem_mla_np_v01` heights are relative to 2 439.4 km; the PGDA 88 DEM is relative to 2 439.4 km.
Every reader converts to radius first, then to height above the world datum (2 439.4 km), with a test.

## 4. Physics tests (§3.2)
1. **Sun angular size**: Horizons `Ang-diam` of the Sun from the site over a full Mercury year lies within the analytic
   range 2·asin(R☉/r), r ∈ [a(1−e), a(1+e)] (a = 0.387098 AU, e = 0.205630, R☉ = 695 700 km), and its extremes match
   the analytic perihelion/aphelion values (≈ 1.73° / 1.14°, ratio ≈ (1+e)/(1−e) ≈ 1.52) within the hourly sampling error.
2. **3:2 resonance / solar day**: from the IAU rotation rate (Ẇ = 6.1385108°/d → 58.646 d) and the orbital period
   (87.969 d): ratio 1.500 ± 0.001; solar day 1/(1/P_rot − 1/P_orb) ≈ 175.94 d; and **empirically** from the Horizons
   series at the site: the Sun's unwrapped azimuth completes 360° in 176 ± 1 d.
3. **Direct-to-Earth only, solar conjunctions**: SEP angle (Sun–Earth–Mercury, Horizons geocentric quantity 23) on the
   same time grid. Outage flag: **SEP < 2.3°** at superior conjunction — DSN Telecommunications Link Design Handbook
   810-005, module 106 Rev. B (30 Sep 2010) §2.3: standard X-band BPSK data return "down to at least 2.3 degrees"
   (Ka-band to 1°, offered as an alternative threshold). Inferior conjunctions below the threshold are flagged
   separately (Sun near the ground antenna beam, module 105 noise — not assessed here). Labelled ENGINEERING ASSUMPTION.
   Check: consecutive conjunctions alternate superior/inferior and recur with the 115.88 d synodic period.

## 5. One Mercury polar site end to end
Prokofiev (north-polar crater; radar-bright, PSR, PGDA 85). Site: a point on its sunlit rim chosen
from the PGDA 85 maximum-incident-flux layer. **Rule (amended before any run, 16 Nov ~12:20 EST):** centre 85.77° N,
62.92° E and diameter 112 km (USGS Gazetteer alternate solution = MESSENGER image captions; the Gazetteer's other
solution 86.00° N, 63.70° E is recorded); candidate pixels in the rim annulus 0.85–1.15 × 56 km from the centre with
PGDA 85 slope < 15°; site = the candidate with the highest PGDA 85 maximum incident flux (ties → nearest the centre).
(The first draft said "within 15 km of the centre", which is the crater floor — a mistake, not a choice.)
The PGDA 85 `.cub` stack as posted is truncated at the source (55.5 MB of the 95.3 MB its label needs: bands 12–20
incomplete); the per-layer ZIP from the same page is complete and is what is read. It also contains
`radar3b.map2.4rms.cub`, a north-polar radar map (2904² px, 287.6 m, ≥ ~80° N): the north-polar ice layer. Terrain: near field PGDA 85 hybrid DEM 125 m where it has data,
far field MLA `hdem_75n_250m` to the curvature limit (Mercury relief bounds). 720-bin skyline with the generic world
ray caster; flat-horizon control. Horizons Sun and Earth from `coord@199` (cylindrical site, exact datum radius) hourly
for one solar day (2 Mercury years, so every azimuth is seen) — metrics reported for the first Mercury year and for the
full solar day. Frame tie: Horizons az/el are about its ellipsoid normal; converted to the radial (sphere) normal used by
the skyline, max correction recorded (zero for the Moon). Independent check of the longitude sign and azimuth convention:
Sun az/el recomputed from the sub-solar point (Horizons quantity 14, observer = Sun) against the topocentric table.
Bundle: provenance (file SHA-256, Horizons raw SHA-256), labels, ice layer (radar value and PSR flag at the site, distance
to the nearest radar-bright pixel), comms block (Earth visible ∧ SEP ≥ 2.3°), and Decision Card / cube / sensitivity /
validation sections, each either computed or an explicit `"not available for this world"` with the reason.

## 6. Hook for R1 / the coordinator (not done here; R1 owns `science/anysite/**`)
Add `world=None` to `science.anysite.solve.solve()` and thread it through: `R = world.radius_m` in `curvature`,
`frames.destination/unit/moon_fixed` → `world.geometry`, `frames.stereo_forward` → the stack's own projection,
`H.build_params` → `world.horizons_params`, and the bundle's `datum`/`frame` blocks from the world. With `world=None` or
the Moon the code path must stay byte-identical (the R6 test `science/worlds/tests/test_moon_world.py` is the guard).
Until then `science.worlds.get_world('mercury').solve(...)` runs the R6 pipeline (`science/worlds/mercury/site.py`).

## 7. Not in scope / later
Mars (§3.3) only after everything above is tested. Blender Mercury scenes (R3), MDIS render twins (R4), any-site queries
for Mercury in the web app.
