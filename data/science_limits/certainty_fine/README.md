# Certainty Height, fine mast series (L10 part 2)

**Label:** PILOT · SOURCE-BASED · UNVALIDATED. Geometric visibility only.

**Question.** At Site04 RoI 3, how does visibility grow between 1.0 and 3.0 m masts in 0.25 m steps, and does the fine
grid reproduce the published Certainty Height of 1.75 m?

**Method.** `python -m science.limits.l10_certainty_fine`. Masts 1.00–2.00 m in 0.25 m steps (2.25–3.00 m not run: time box) × 21 maps (nominal + PGDA 78
clones 1–20). The skyline settings match the bundles. Sun-centre perpendicular margin > 0 on the 337 hourly samples of
14–28 Nov 2026. Certainty Height = the lowest mast that is 100 % on every map.

**Result.** `result.json` → `certainty_height_m`, plus a per-mast series (min/max Sun % over maps, number of maps at 100 %).
The series is written so that a future bundle can carry it.

**What it does not show.** It uses 20 of the 100 public clones. A Certainty Height that is a k-of-N statement over 21 maps
is not a probability. Hourly samples only (L2 shows continuous timing moves Sun % by ≤ 0.26 pt).
