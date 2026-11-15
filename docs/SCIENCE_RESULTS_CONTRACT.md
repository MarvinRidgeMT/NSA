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

## 5b. derived.attribution (A1 Ridge of Record, optional)
- `ridges[]`: `id` (R1…, sorted by Sun+Earth loss hours, then Sun control hours), `centroid_lat`/`centroid_lon` (mean grid
  position of the ridge's controlling points), `dist_km` (mean range) and `dist_range_km`, `az_span_deg` [a, b] (bin
  centres, clockwise from a to b; may wrap through 0°), `n_bins`, `height_m` (max DEM height, 1737.4 km sphere datum),
  `relief_m` (vs the site ground), `max_elev_deg`, `min_gap_deg`, `source` (`near_5m` / `far_80m` / `mixed`),
  `sun_loss_h`, `earth_loss_h`, `ctrl_h` (= `sun_ctrl_h`), `earth_ctrl_h`, `of_record`.
  Only clusters that held the Sun or Earth azimuth at least once are listed; `n_clusters_total` counts all.
- `per_bin` (720 each): `ridge_idx` (index into `ridges`, or null), `ctrl_idx` (controlling sample index on the ray),
  `ctrl_dist_m`, `gap_deg` (runner-up gap), `source`.
- Hours are hourly samples × step (both window endpoints included), body azimuth → nearest bin; loss = centre not visible.
  Interval metrics (§4) remain the numbers to quote for visibility %.

## 5c. derived.coverage (A3, optional)
- `critical_threshold_deg` (1.0), `n_critical_h`, `covered_frac` (0–1 or null if no critical hours), `uncovered_ridges`
  (A1 ids), `all_hours_covered_frac`, `n_hours` — for the Sun; the same keys under `earth`. `wording_rule`, `method`, `label`.
- Covered = the controlling skyline sample at the body's azimuth (nearest bin) is from the 5 m clone tile.

## 5d. derived.margin_series (A4, optional)
- `t_unix` (= samples), `n_clones`, `clone_ids`; for `sun` and `earth`: `*_margin_deg` (nominal), `*_margin_clone_min_deg`,
  `*_margin_clone_max_deg`, `*_n_clones_visible` (per sample), `*_center_visible_pct_hourly_by_clone`;
  `sun_and_earth_center_visible_pct_hourly_by_clone`; `clones[]` (ground height, tile SHA-256); `method`; `label`.
- Margin = body centre elevation − skyline (deg); visible = perpendicular margin > 0 (§3). Clone spread = N of N terrain
  models tested, not a probability.

## 5e. derived.arrival_slip (stretch PILOT, optional)

- Produced by `python -m science.stretch.arrival_slip`; the established `science/` solver remains read-only.
- `slip_hours` is the exact tested grid. `points[]` has a stable `result_id`, `label: PILOT`, shifted UTC window,
  hourly `sample_count`, nominal Sun-centre and Sun+Earth percentages, clone min/max for both metrics, and the number
  of clones passing the bundle-carried thresholds. A clone passes jointly only when both requirements pass.
- Nominal plus PGDA 78 clones 1–20 use the input bundle's observer, 1 m near-ray step, 280 km finite horizon reach and
  LDEM 80 m far field. One extended JPL Horizons hourly series per body/site is evaluated without browser computation,
  interpolation or extrapolation.
- Percentages are shares of hourly samples including both window endpoints. This MVP does not bisect shifted-window
  crossings. Clone min/max and k/N are deterministic terrain alternatives, not calibrated probabilities.
- Every block and point is labelled `PILOT`; underlying inputs remain `SOURCE-BASED UNVALIDATED`. Results are local
  geometric visibility only, not certified illumination/power or DSN telecommunications availability.

## 6. UI rules

1. Show `validation_status.overall` and each `label` next to the numbers.
2. Draw truncated bins visibly differently (lower bound). Never smooth over a `null`.
3. The time slider snaps to `samples[].utc` or `events[].utc` only.
4. Azimuths are local; do not rotate by longitude in the viewer.
5. The fixture `data/bundles/fixtures/site01_ui_fixture_50.json` is an exact 50-sample subset of the Site01 bundle,
   with an irregular step. Its skyline, events and metrics are identical to the full bundle.
