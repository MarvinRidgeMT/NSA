# POLARIS X — Science Results Contract (polaris-science-results-v1)

> **How this relates to `main`.** `docs/SCIENTIFIC_CONTRACT.md` and `schemas/science-bundle-v2.schema.json` on `main`
> describe the Codex *source* bundles (raw DEM crops + Horizons samples, `datasets[]`). This file describes the
> *results* produced by `science/` (720-bin skyline to 280 km, bisected events, metrics, G5 scenarios). It was renamed
> from "science-bundle-v2" to avoid a name clash. Next step: export these results into the viewer's proposed
> `datasets[i].derived` block (`web/docs/VIEWER_BUNDLE_CONTRACT.md`) so `web/` can show them.

Status of every number in a bundle: **SOURCE-BASED UNVALIDATED** until the `not-run` checks in
`validation_status.checks` pass. Schema: `schemas/science-results-v1.schema.json` (JSON Schema 2020-12).
Producer: `python3 -m science.bundle` (Python is the only numeric authority). Consumers (React/TS viewer,
Blender) are **read-only**: they must not recompute, interpolate past sample times, or fill missing values.

## 1. Body, datum, frames

| Item | Definition |
|---|---|
| Body | Moon (NAIF 301), sphere R = 1 737 400 m |
| Heights | metres above the 1737.4 km sphere (LOLA LDEM convention; Horizons uses the same radii for coord@301) |
| Lat / lon | planetocentric latitude; east-positive longitude, −180…180 |
| Moon-fixed 3D | P = (R + h)·[cos φ cos λ, cos φ sin λ, sin φ] |
| Local ENU | e = ∂/∂λ, n = ∂/∂φ, u = radial unit vector at the site |
| Azimuth | degrees clockwise from **local** north (0 N, 90 E) — the JPL Horizons surface-observer convention |
| Elevation | asin((P − P_obs)·u / ‖P − P_obs‖), airless (no refraction) |
| Grid | `+proj=stere +lat_0=-90 +lon_0=0 +k=1 +R=1737400`, read from the LDEM COG header; x = ρ sin λ, y = ρ cos λ |
| Grid ↔ local | at longitude L: local north = (sin L, cos L), local east = (cos L, −sin L) in grid; **grid_az = local_az + L** |
| Body-fixed frame | DEMs: MOON_ME (DE421) per PGDA README. Horizons: MEAN_ME. Frame tie not applied → unvalidated |

The legacy bug (rays stepped along grid az, with east = sin az and north = cos az) was off by exactly L:
−137.49° at Site01 and −171.87° at Site04. `app/src/science.js` and `blender/polaris_geometry.py` still have this bug
and must not be used as numeric sources.

## 2. Skyline

- 720 bins of 0.5°; bin *i* has one ray at azimuth *i*·0.5°. Rays follow great circles on the sphere,
  so they cross the pole correctly. They are projected with the closed-form stereographic formula
  (tested equal to pyproj with the COG CRS, < 1 mm) and sampled bilinearly.
- Near field: product-78 5 m site tile, out to its inscribed radius (`near_cut_m`). Far field: LDEM 80 m, out to
  `max_range_m` (≥ 150 km; currently 280 km). Near is used wherever it has data.
- `critical[i]`: the sample that sets the horizon (distance, lat/lon, grid x/y, height, which DEM).
- `status[i] = "truncated"` if any sample ≤ `max_range_m` has no data (outside the raster, NaN, or failing the ±20 km
  physical-range check). The angle then comes only from samples before the gap, so it is a **lower bound**.
  It is `null` when there are no samples at all. Nothing is ever filled in.
- `range_limited[i] = true` when the bin's angle is below `beyond_range_max_possible_elev_deg`, the highest angle any
  terrain beyond `max_range_m` could reach (from the window's maximum height on a smooth sphere).
- `flat_baseline`: the flat-horizon control (0° in every bin), plus the bare-sphere dip at the eye height.

## 3. Samples and events

- Sun = Horizons `10`, Earth = `399`, `CENTER='coord@301'`, `SITE_COORD='E-lon,lat,alt_km'`, using the real DEM height
  without the mast. `QUANTITIES='4,13,20'`, `APPARENT=AIRLESS`. Columns are found by header name.
- Each raw response is stored byte-for-byte under `data/raw/horizons/`. `MANIFEST.json` holds its SHA-256, the query
  parameters, and when it was retrieved. `provenance.horizons_raw` lists every file a bundle used.
- Each sample gives az/el of the target **centre**, the angular radius r (from Horizons Ang-diam/2; the documented
  fallback is 0.2666°), the skyline height H(az) interpolated linearly between bins, margin = el − H, `center_visible`,
  and `disk_fraction`.
- Disk fraction: the share of a disk of radius r that lies above the skyline. Within the disk the skyline is treated as a
  straight line whose slope comes from the neighbouring bins. Perpendicular distance m⊥ = m/√(1+s²).
  f = 1 − [r² acos(m⊥/r) − m⊥√(r² − m⊥²)]/(πr²). No limb darkening.
- Events: brackets where the sign changes between hourly samples are bisected. Each step queries Horizons again (TLIST)
  at the midpoints; ephemerides are never interpolated. Three event pairs are found: centre (`center_rise/set`),
  upper limb (`first_light/last_light`) and lower limb (`fully_visible/begins_occultation`). Each is bisected to ≤ 0.5 s.

## 4. Metrics

Centre-visible percentages and the longest hidden spells come from intervals bounded by the refined events. Mean disk
fractions are a trapezoid over the hourly samples. All of them describe local geometric visibility only, **not**
certified illumination, power or DSN link availability.

## 5. Scenarios (G5)

These are deterministic alternatives, not calibrated probabilities. Each scenario's metrics are fully recomputed:
new skyline, new Horizons samples where position or time changes, and new events. Families: `position-offset` (3×3
grid, ±100 m), `mast-height` (2/5/10 m), `arrival-shift` (±12 h), `dem-uncertainty` (product-78 clones, or a ±1σ
shift from the toterr raster) and `repair`.

## 6. UI rules

1. Show `validation_status.overall` and each `label` next to the numbers.
2. Draw truncated bins visibly differently (lower bound). Never smooth over a `null`.
3. The time slider snaps to `samples[].utc` or `events[].utc` only.
4. Azimuths are local; do not rotate by longitude in the viewer.
5. The fixture `data/bundles/fixtures/site01_ui_fixture_50.json` is an exact 50-sample subset of the Site01 bundle,
   with an irregular step. Its skyline, events and metrics are identical to the full bundle.
