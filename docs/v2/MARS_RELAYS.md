# Mars relay-orbiter geometry at the Jezero rim site (17 Nov 2026)

**SOURCE-BASED · UNVALIDATED. This is geometry, not relay availability.**
- Code: `science/worlds/mars/relays.py`.
- Output: `data/worlds/mars/mars_jezero_rim_relays_2026-11-14_16d.json`.
- Tests: `science/worlds/tests/test_mars_relays.py`.
- It closes the "relays not available" open item of `PHASE_6_T3_RESULTS.md` §4 for the 16 days where JPL Horizons has
  trajectories. The Mars site bundle itself is unchanged: it still reports DTE only, and its relay text predates this file.

## Method
- **Orbiter position:** for each relay orbiter, JPL Horizons gives the apparent (airless) azimuth and elevation at the site.
  - Site point: the bundle's planetocentric site at radius 3,396,000 m + ground height + 1 m mast.
  - Longitude: the same MOLA → Horizons longitude tie as the bundle (−0.00352°).
  - Sampling: one sample per minute, 2026-11-14 00:00 → 2026-11-30 00:00 UTC (23,041 samples).
  - Frame: rotated from Horizons' ellipsoid normal to the sphere normal, like the Sun and Earth in the bundle.
- **"Visible":** the orbiter centre is above the terrain skyline stored in the site bundle (720 bins, linear in azimuth),
  with a flat 0° horizon as the control. A pass is a run of visible minutes, and its edges are good to ±1 minute.
- **Window:** fixed before any query, and inside every trajectory used.
  - MRO's Horizons trajectory ends 2026-11-30 12:48.
  - MAVEN has no trajectory after 2026-03-01, so it is reported **not available**. It is never extrapolated.
- **Independent check** (per orbiter, 385 hourly times):
  - Route: Mars as seen from the orbiter (Horizons `CENTER 500@<orbiter>`: sub-spacecraft point, IAU_MARS west-positive
    longitude, planetodetic latitude, plus range). From that, the orbiter's body-fixed position, then the elevation from the
    site, computed in our own code.
  - Agreement with the site-topocentric route: MRO 0.083°, TGO 0.073°, Mars Express 0.27° (max |Δel|).
  - Control: flipping the longitude sign gives median errors of 22–28°, so the site convention is confirmed.
  - The 0.1–0.3° residual is not explained; a different light-time or aberration treatment between the two routes is a
    candidate. At these orbiters' angular rates it moves pass edges by much less than the 1-minute step.

## Results (16 days)
| orbiter | Horizons trajectory over the window | visible % of minutes (flat control) | passes (per day) | pass length median (min–max) min | min/day | longest gap |
|---|---|---|---|---|---|---|
| MRO | JPL planning prediction after 2026-11-01 | 2.12 % (2.58 %) | 50 (3.1) | 11 (2–14) | 30.6 | 12.1 h |
| TGO | ESA long-term reference trajectory; last data fit 2025-06-21 | 3.15 % (3.74 %) | 61 (3.8) | 14 (1–18) | 45.3 | 12.7 h |
| Mars Express | ESA prediction after 2026-10-21 | 11.74 % (13.92 %) | 34 (2.1) | 65 (2–186) | 169.1 | 19.8 h |
| MAVEN | none after 2026-03-01 | not available | — | — | — | — |

- **Any of the three:** visible 16.6 % of minutes; the longest gap with none visible is 10.3 h.
- **Terrain effect:** the rim's skyline hides 133 (MRO), 172 (TGO) and 541 (Mars Express) minutes in which the orbiter is
  above a flat horizon.
- **TGO pass times are the least certain:** the trajectory is a reference trajectory fitted 17 months before the window, and
  its error is not quantified here. Treat TGO's pass counts and durations as indicative only.

## Not modelled
Relay scheduling and orbiter operations, the UHF link budget and antenna patterns, minimum-elevation masks, atmosphere.
Nothing here says a relay session would be granted or would close.
