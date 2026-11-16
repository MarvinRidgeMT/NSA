# L2 — Event timing below one hour

**Label:** PILOT · SOURCE-BASED · UNVALIDATED. Geometric visibility only.

**Question.** Visibility was sampled hourly. How much do visible %, Sun+Earth % and the longest gap move when every
visible/blocked transition is timed to the minute or better — for the nominal map **and all 20 clones**?

**What already existed.** The bundles refine the nominal map's 9 (Site04 RoI 3) / 3 (Site01 RoI 6) events by bisection on
real Horizons evaluations to ±0.22 s (`data/raw/horizons/*bisect*`), and carry continuous `sun_center_visible_pct`
(94.213 % vs 94.362 % hourly). Clones had no sub-hour timing.

**Method.** `python -m science.limits.l2_timing`. Cubic-spline interpolation of the bundle's hourly Horizons az/el/radius
(inside the samples only; the code refuses to extrapolate). Margin g(t) = m⊥ + k·r (k = +1 any part, 0 centre, −1 full
disc) scanned on a 1-minute grid over 14–28 Nov 2026, each sign change refined by Brent's method to ≤ 1 s. The spline
crossing times are checked against the bundle's real-Horizons bisection events (`validation_vs_horizons_bisection`):
agreement is within seconds, which validates the interpolant at this site and window (not elsewhere). Sun+Earth % is
the share of 1-minute grid points with both visible.

**Result.** `result.json` → `sites.<site>.summary` and `RESULT.md`. Every refined transition lies inside its hourly
bracket; sub-hour "blinks" (a set and a rise inside one hour, missed by hourly samples) are counted separately.

**What it does not show.** The spline is validated against real Horizons evaluations only at the nominal events; clones use
the same ephemeris (observer-height parallax < 1e-8°). The skyline itself is still 720-bin, linearly interpolated in
azimuth (see L3). Not power, not comms; k of N clones is not a probability.
