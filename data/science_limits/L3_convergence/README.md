# L3 (numerical part) — convergence of skyline settings

**Label:** PILOT · SOURCE-BASED · UNVALIDATED.

**Question.** Are the bundle settings (720 bins, 1 m near ray step, 280 km range) converged for Sun %?

**Method.** `python -m science.limits.l3_convergence`. Site04 RoI 3 and Site01 RoI 6, nominal + clones 1 and 11, 1 m mast,
337 hourly samples, 14–28 Nov 2026. Refinements: bins 1440 and 2880, near step 0.5 m, far range 289 km (the edge of the
loaded far-DEM window). Each is compared with the baseline: ΔSun %, and max/median |Δ horizon elevation| at the
baseline bin azimuths.

**Pass criterion.** Every refinement changes Sun % by < 0.1 pt. See `result.json` → `pass_lt_0p1pt` and `RESULT.md`.

**Not tested.** A 25/50 km near radius (the 5 m tile is ~16 km wide). The far DEM at 40/20 m (not cached on this Mac).
A 600 km range (outside the loaded far window; `L3_far_bound` shows no hour can change from terrain beyond 280 km).
