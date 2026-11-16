# Design: time-dependent traverse planner to a nearby PSR (Phase 10, design only — needs Sid's and Anish's go-ahead)

Status: **not implemented.** Any output would be labelled ENGINEERING ASSUMPTION (cost weights are choices).

## Question
From the landing cell, what is a route to a nearby permanently shadowed region (PSR) and back that keeps slope,
distance, solar power and Earth/relay link acceptable at every hour, and when should it start?

## Search
Spatio-temporal A* over nodes (x, y, t) on a grid (25 m cells, 1 h steps): edges move to one of 8 neighbours (or
wait in place) and advance time by the travel time at a chosen speed. Cost per edge:
  c = w_d·distance + w_s·g(slope) + w_p·(1 − f_sun(x, y, t)) + w_l·(1 − link(x, y, t)) + w_t·Δt
with hard constraints slope < S_max (from `science/cube/slope.py`, EVA 20°, rover limit configurable) and a battery
state of charge ≥ reserve (Phase 5 model, integrated along the path). Heuristic: straight-line distance / max speed
(admissible). Time-dependence makes the graph large; prune with a precomputed static slope mask and a coarse-to-fine
pass (100 m then 25 m).

## Data needs (the expensive part)
- Horizon masks on a GRID, not only at the site: f_sun(x, y, t) and link(x, y, t) need a skyline per cell. With the
  batched solver (`science/cube/compute.multi_skyline`) a ±1 km field at 25 m is 6561 skylines per map; at about
  30 s per position on an idle Mac with 8 workers that is ~7 h for the nominal map, ×21 for all clones. Plan: nominal
  map only at first, clones for the final route; store masks (720 bins, uint8 quantised) per cell, ≈ 5 MB per map.
- Slope/aspect field (already available), Phase 4 link geometry per cell (relay az/el transfer to each cell), Phase 5
  power model.
- A PSR polygon set (e.g. from the LROC/LOLA PSR products) with provenance, cached under `data/cache/`.

## Outputs
Route polyline with per-hour state (sun fraction, link, slope, SoC); start-time calendar for the traverse (S axis);
robustness as k of 20 maps on which the same route stays within constraints (not a probability).

## Tests to write with it
Optimality on a synthetic static grid (matches Dijkstra), waiting is chosen when a shadow passes, constraint
violations are never returned, determinism with fixed inputs.
