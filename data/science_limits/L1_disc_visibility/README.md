# L1 — Disc vs centre visibility

**Label:** PILOT · SOURCE-BASED · UNVALIDATED. Geometric visibility only (not power, not comms).

**Question.** The bundles call the Sun/Earth "visible" when the disc centre is above the terrain horizon. How do the
headline numbers change if "visible" means *any part of the disc* or *the full disc*, and does a disc-based rule explain the
NAC v2 finding that images look lit only when the centre is ~+0.31° to +0.45° above the horizon?

**Method.** `python -m science.limits.l1_disc`. Hourly samples of the 1 m-mast bundles (14–28 Nov 2026, 337 samples),
the bundle's perpendicular margin m⊥ and per-sample apparent radius r (Horizons angular diameter). Skylines recomputed
with the bundle settings (720 bins, 1 m near step, PGDA 90 far field to 280 km); the nominal skyline equals the bundle's
bit-for-bit, and the centre variant reproduces the bundle's 94.362 % / 72.107 % and the clone range. Variants:
any = m⊥ > −r, centre = m⊥ > 0, full = m⊥ > +r. Disc fraction from the circular-segment formula, with the horizon
**assumed locally flat across the disc** ("flat") and, for comparison, as a straight line at the local skyline slope
("tilted", the bundle's own `disk_fraction`). Longest gap counts hidden hourly samples (× 1 h); L2 gives sub-hour gaps.

**Result.** See `result.json` → `sites.<site>.nominal|clone_range`, and the table in `RESULT.md`.

**NAC.** A "disc fraction ≥ 0.5" rule is mathematically the centre rule (flat or straight horizon ⇒ half the disc is up
exactly when the centre is on the horizon), so it does **not** shrink the crossing offset. The observed crossings
(+0.31° region 8, +0.45° region 9) are ≈ 1.2–1.7 solar radii: at the crossing the disc is already fully up under
the flat-horizon assumption. Measured against a full-disc rule the offsets shrink to ≈ +0.05° and +0.18°.

**What it does not show.** It does not say which rule matches a real lander (power depends on panel geometry and on
the partial disc; this is geometry only). Limb darkening is ignored (disc fraction is area, not flux). The NAC re-score uses
the binned crossing, not per-point re-classification; it holds for the two NAC v2 test areas only and does not observe the
Site04 RoI 3 lander point. Sites 07/11 are not included (no local clone tiles or demo-window Horizons series on this Mac).
k of N clones is not a probability.
