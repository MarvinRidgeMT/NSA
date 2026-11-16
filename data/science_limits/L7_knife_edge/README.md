# L7 — Knife-edge reporting

**Label:** PILOT · SOURCE-BASED · UNVALIDATED. Geometric visibility only.

**Question.** The Site04 RoI 3 result hinges on a rise 15–16 m from the lander. Turn "fragile" into numbers: how many
hours sit near the horizon, how much uniform horizon error flips the 70 % Sun verdict, and what height change at the
controlling DEM cell that corresponds to.

**Method.** `python -m science.limits.l7_knife_edge`. Hourly Sun-centre perpendicular margins (nominal map and the 20
clones, as in L1). Uniform horizon error: every skyline bin raised/lowered by δ, Sun % and Sun+Earth % recomputed on the
continuous timeline (L2). δ* = smallest raise that drops Sun % below 70 % (or Sun+Earth below 40 %; thresholds from the
bundle's `derived.flip_forecast`), by bisection. dE/dh = exact derivative of the Moon-fixed elevation angle of each hour's
controlling terrain sample (finite difference ±1 cm, float64). Height to flip hour i = m_i / (dE/dh)_i.

**Result.** `result.json` and `RESULT.md`.

**What it does not show.** A uniform error is a worst-case shape, not a modelled DEM error (L4 has the error model). The
single-cell height equivalent δ*/(dE/dh) is an equivalence at the dominant cell, not a proof that raising one cell alone
flips the verdict (one cell controls only some bins). Not power, not comms.
