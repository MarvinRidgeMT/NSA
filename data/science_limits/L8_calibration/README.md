# L8 (part 2) — toterr vs clone calibration factor

**Label:** PILOT · SOURCE-BASED · UNVALIDATED.

**Question.** The PGDA 78 `toterr` layer, used as a Gaussian height-error model, was reported to over-predict state flips
by ≈ ×1.5 relative to the 20 clones. Is that one factor, or does it vary by site?

**Method.** `python -m science.limits.l8_calibration`: arithmetic on `research/long_features/results/rq2_report.json`
(model B, independent ρ = 0 and empirically correlated ρ). Factor = observed / expected flip clone-hours; also the
median per-pixel σ ratio clone-std / toterr at the controlling cells.

**Result.** See `RESULT.md`. 12-month window: toterr **over**-predicts at Site04 RoI 3 (×1.41) and Site01 RoI 6 (×1.69),
but **under**-predicts at Site07 RoI 1 (×0.55) and Site11 RoI 4 (×0.70), although the per-pixel σ ratio is similar
(0.63–0.77) everywhere. So no single factor applies; a per-site factor is needed, and at Sites 07/11 the flips come
from something the per-pixel σ does not capture (likely correlated, multi-cell ridge changes — the same sites where the
16-ridge forecast captures only ~37–44 %).

**What it does not show.** The clones are themselves 20 draws of one error model (Barker et al. 2021), so this is
"toterr vs that model", not vs truth. The demo-window rows have too few flips to calibrate. Not a probability.
