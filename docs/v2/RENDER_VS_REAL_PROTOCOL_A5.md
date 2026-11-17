# Render-vs-real protocol — Amendment A5 (the held-out run for LROC NAC)

Written 17 Nov 2026 by the coordinating session (Claude), **before any held-out image is fetched, rendered, looked at or
scored**. Its SHA-256, and the SHA-256 of every code file the run executes, are recorded in `docs/v2/PREREGISTRATION.md`
(Entry 6) in the same commit. The run script refuses to start if any registered hash differs.

**State at writing.**
- Dev: the A1–A4 dev pilot is complete: 181 GRGM900C-orbit rows plus 7 FDF-only rows (`docs/validation/RENDER_VS_REAL.md`).
- Held out: no image has been downloaded, rendered, displayed or scored. The only held-out information used is catalogue
  metadata: ids, times, sites, footprints, strata, URLs.
- Rows: 680 held-out LROC NAC rows. 182 rows (167 images) pass the protocol §2 metadata gates. 159 of the 167 images are
  inside a GRGM900C orbit file's time range.

## A5.1 Scope, and how "run once" is read
- This is the single held-out run for **LROC NAC (CDRNAC4)**.
- **Other instruments are not covered:** LROC WAC, ShadowCam and Kaguya TC each need their own camera model and render
  settings, frozen in their own amendment, and then their own held-out run.
- **How "once" is read:** protocol §6 says "run once, at the end". It is read here as once per instrument. This is
  acceptable because §8 never combines instruments, and no held-out NAC result can inform another instrument's settings
  (none is chosen from scores).
- **Consequence:** after this run, nothing in the NAC pipeline may change without a new amendment. Any changed number is
  then reported next to the original (§6).

## A5.2 Rows
- **Rows considered:** every `split = heldout`, `instrument = LROC_NAC` row of the frozen catalogue (SHA-256 `4b941d61…`).
- **No sampling.** The dev cluster sampling of A1.1 does not apply.
- **Gating:** the protocol §2 metadata gates, then the A1.2/A2 geometry gate, then the §3.1 analysis-window minimum
  (500 px).
- **Accounting:** every row appears in the result as scored, gated (with a reason) or failed (with a reason).

## A5.3 Frozen parameters (identical to the dev pilot; nothing changed after seeing dev scores except as stated in A5.5)
- **Camera, geometry, orbit:** A1.2 with A2's polynomial degree rule.
  - Spacecraft position comes from GRGM900C where an orbit file covers the image; otherwise from FDF `lrorg`, flagged
    `orbit = fdf` (A4.1).
  - Registration radius: ± max(3 px, 3 × 20 m / binned GSD) on GRGM900C rows; ± max(3 px, 400 m / binned GSD) on FDF rows
    (A4.2).
  - Crop lines are computed directly. There is no FDF first pass, so A4.3 does not apply.
- **Grid:** A1.3: binned to 5 m; HRS/HIS and other special pixels leave the window; 8-pixel border.
- **Render:** A1.4.
  - Blender 5.3.0, Cycles CPU, OSL push-broom camera.
  - Beauty pass: 32 samples, 4 bounces, no denoising, seed 0, Sun lamp at the true angular diameter, black sky, no
    earthshine.
  - Shadow pass: one Sun-centre ray, flat shading. The renderMedianZero fallback applies.
- **Terrain products** (A1.5): PGDA 78 5 m (headline), LOLA LDEM_875S_5M, PGDA 90 LDEM_80S 80 m (the protocol's LDEM
  control), flat-sphere control. The near and far levels are as in A1.5. Every product is rendered for every row.
- **Photometry** (A1.5):
  - Hapke, SOUTH_60_70 parameters of the LROC WAC 643 nm map (`blender/v2/hapke.py`), for every product.
  - Lunar-Lambert L = 0.5 and Lommel–Seeliger on PGDA 78 only.
  - No parameter is fitted.
- **Metrics:** §4.1, §4.2, §4.4 and §4.5 as implemented under A1.6 and A3 (`score.py`, `run.py`), plus the A5.5 secondary
  mask.
- **Code:** the files listed in PREREGISTRATION Entry 6, run by
  `python -m tools.validation.render_vs_real.heldout all --workers 4 --threads 4`.
  - Outputs: `tools/validation/render_vs_real/results_heldout/` (ids and numbers only) and
    `$POLARIS_DATA/v2/render_vs_real/heldout/` (renders, git-ignored).
  - Logging: the run records its start, stop and commit in `results_heldout/RUN_LOG.jsonl`.
  - Resuming: the run may be resumed after a crash. The resumption is logged, and rows that were already scored are not
    re-scored.

## A5.4 What changes in the code (no change to any dev number)
- **Split switch:** `common.py` gets the held-out switch (`POLARIS_RVR_SPLIT=heldout`, set only by `heldout.py`) and the
  registration check. Held-out mode admits only held-out LROC NAC ids, and dev mode still refuses every held-out id.
- **Paths:** `geometry.py`, `run.py` and `report.py` read the geometry and render folders from `common.py` instead of
  building them themselves.
- **Secondary mask:** `score.py` gets `count_matched_shadow`, and `run.py` records the A5.5 secondary IoUs.

## A5.5 Near-total-shadow windows: a stratum and a secondary mask; the headline rule is unchanged
- **Dev finding:** 21 of the 181 dev headline rows have a registered predicted shadow fraction ≥ 98 %. Their shadow IoU
  median is 0.532, against 0.949 for the rest (`RENDER_VS_REAL.md` §7.3).
  - In these windows the fixed Otsu rule places its threshold inside the shadow's own brightness distribution: scattered
    light, readout pattern.
  - The weak-bimodality flag does not catch them.
  - Protocol §5 lists the thresholding rule as **never tuned**, so it is **not** changed. The headline and the §8 claim use
    the v1.0 Otsu rule on **all** rows.
- **Stratum (reporting only):** rows whose registered PGDA 78 predicted shadow fraction is ≥ 0.98 are reported as a
  separate stratum next to the rest. The all-rows numbers always come first. The 0.98 cut was chosen from the dev diagnostic
  above, and is stated as such.
- **Secondary observed mask (sensitivity only; never headline, never used in §8):** the *count-matched* mask.
  - Rule: in the analysis window, the k brightest real pixels (exposure-normalised I/F) are lit and the rest are shadow,
    where k is the number of predicted-lit window pixels. Ties are broken by a stable sort on the pixel index.
  - What it tests: whether the lit pixels are *where* the render puts them, independent of Otsu.
  - What it cannot test: how much is lit, which it takes from the render.
  - Recorded per row as `cmIouShadow` and `cmIouLit`, unregistered and registered, for every product and photometry.
  - Dev limitation: it cannot be recomputed on the dev rows, because their window geometry was discarded after scoring.
    So it has no dev baseline, and it is reported for the held-out rows only.

## A5.6 The §8 claim, made precise
- **Unit:** evaluated per site, for each terrain product separately. PGDA 78 5 m is the headline product.
- **Rows:** registered, Hapke, GRGM900C-orbit rows only. FDF-orbit rows are reported separately and never enter the claim.
- **Conditions** (code: `heldout.claim_rule`):
  1. The median shadow IoU is ≥ 0.80.
  2. The median shadow-edge error, over rows where an edge was matched, is ≤ 2 × the median **analysis pixel**: the binned
     GSD of A1.3, the grid on which both masks exist.
     - Disclosure: this reading was chosen after the dev pilot. Measured against the native NAC pixel the dev median of
       5.4 m would fail: the dev native pixels have a median of 1.43 m and range 0.53–1.97 m, against a median analysis
       pixel of 3.9 m. The held-out native pixels range 0.44–20.6 m in the catalogue.
     - So the report also states, per site, whether the edge error is within 2 native pixels. That comparison is reported
       but is not the rule.
  3. The product beats the flat-sphere control on ≥ 80 % of paired images for shadow IoU, **and** on ≥ 80 % for edge
     error.
     - An undefined edge error (no matched edge) counts as worse than any finite one.
     - A pair where both are undefined is not a win.
- **Dry run on dev:** before registration, `claim_rule` was applied to the dev records as a code check. That is not a
  result of this protocol.
  - site01_roi6, site04_roi3 and site11_roi4 (n = 1) met all three conditions.
  - site07_roi1 failed condition 3: it beat the control on edge error in 75 % of pairs.
  - The dry run changed nothing in the rule.
- **Wording:** a site that fails is reported with the failed condition(s) and the numbers. No sentence combines sites,
  products or instruments.

## A5.7 Reporting
- **Report:** `docs/validation/RENDER_VS_REAL_HELDOUT.md`, labelled SOURCE-BASED · UNVALIDATED · held-out.
  - Contents: the §7 breakdown (per site, product and photometry; paired product comparisons with the bootstrap of A1.6;
    registration; FDF rows; weak-bimodality and A5.5 strata; Site04 RoI 3 hero point; every gated or failed row).
  - Dev numbers sit next to the held-out numbers, and are labelled.
- **Galleries** (random 12, seed `polaris-x-v2-gallery`; worst 10 % by shadow IoU) are crops of NASA images. They are built
  locally and **not committed**.
- **Report code:** `report_heldout.py` only formats numbers. The decisions are made by the registered `heldout.py`.
