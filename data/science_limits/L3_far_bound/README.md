# L3 (analytic part) — terrain ignored beyond 280 km

**Label:** PILOT · SOURCE-BASED · UNVALIDATED.

**Question.** The far field stops at 280 km. Could anything farther away rise above the local horizon in the azimuths the
Sun or Earth cross in the demo window?

**Method.** `python -m science.limits.l3_far_bound`. Exact spherical geometry (no small-angle approximation):
H(d, e) = r0·cos e / cos(d/R + e) − R is the height a point d away must have to appear at elevation e. Threshold e = the
lowest skyline elevation in the bins the body crosses, minus its apparent radius (so even "any part of the disc" is
covered). Compared with the tallest height in the loaded far DEM and with 10.8 km, an upper bound on all lunar relief
(LOLA global maximum ≈ 10.79 km).

**Result.** See `RESULT.md`. A coarse test (lowest skyline anywhere in the crossed azimuths) leaves only 0.08° at Site04
and fails at Site01, so it proves nothing. The per-hour test (the bound must rise above both the horizon at that hour's
azimuth and the disc's lower edge) shows that no hour in the demo window can change at either site: the minimum
per-hour slack is given in the table. Physically, 10.8 km terrain at 280 km would sit at ≈ −2.8°, below every horizon
and every lower limb actually reached in the window.

**What it does not show.** It bounds what is *outside* 280 km only; refinement of the DEM *inside* the range is the
numerical part of L3 (bins, steps, far DEM resolution), which is held until the submission is pushed.
