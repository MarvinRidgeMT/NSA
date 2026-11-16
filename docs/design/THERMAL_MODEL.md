# Design: 1-D regolith thermal model (Phase 10, design only — needs Sid's and Anish's go-ahead)

Status: **not implemented.** Label on any future output: **MODEL** (thermal), never SOURCE-BASED.

## Purpose
Turn the illumination series POLARIS X already computes into surface and shallow-subsurface temperature at a
site × mast × terrain map × start, so the Decision Card can answer "does the hardware/regolith stay within limits?".

## Inputs (all already in the cube pipeline)
- Hourly visible Sun disc fraction f(t) per T × D_mast (`data/cubes/<site>/disc_fraction_hourly.json.gz`).
- Sun elevation and distance per hour (Horizons, `science/cube/ephem_year.py`), local surface normal from the
  plane-fit slope/aspect (`science/cube/slope.py`, 25 m baseline).
- Earth visibility per hour (Earthshine term, small) and the terrain skyline (for the sky-view factor).

## Model
- 1-D heat conduction in depth z: ρ c(T) ∂T/∂t = ∂/∂z (k(T, z) ∂T/∂z), finite volume, 0–2 m, geometric grid
  (mm at the top), implicit time step ≤ 1 h with sub-stepping near the terminator.
- Surface balance: (1 − A(θ)) S f(t) cos i + ε σ T_sky⁴·F_sky + Q_scatter + Q_IR,terrain = ε σ T_s⁴ − k ∂T/∂z|₀.
- Regolith properties: the Hayne et al. (2017) density/conductivity profile (H-parameter) and temperature-
  dependent heat capacity; albedo with incidence dependence. Parameters in a YAML file, shown on screen.
- Terrain IR and scattered sunlight from surrounding slopes: first version uses the sky-view factor from the skyline
  only (one bounce); documented as a lower bound on PSR temperatures.
- Spin-up: cycle the first lunation until the deep temperature changes < 0.1 K per cycle.

## Outputs
Per site × D_mast (for elevated hardware use a lumped-node variant) × T: min/max surface temperature, hours below a
threshold, depth of the 110 K isotherm; range band over T.

## Validation plan (Diviner)
1. Reproduce published equatorial and polar temperature curves for flat ground before any south-pole site.
2. Compare with LRO Diviner polar products (PDS Geosciences node, Diviner Lunar Radiometer gridded polar
   temperatures) at the RoI cells: seasonal max/min and the diurnal curve at matched local time. Record the PDS file
   names and SHA-256 in a manifest; rasters under `data/cache/` only.
3. Acceptance: report bias and RMS vs Diviner per site; the label stays MODEL even when they agree.

## Tests to write with it
Energy conservation of the conduction scheme (closed boundaries), analytic semi-infinite step response,
grid/time-step convergence, a zero-illumination case relaxing to the geothermal floor.

## Out of scope
Volatile stability, hardware thermal design, anything labelled certified.
