# Science limits — status (branch `science/limits-2026-11-15`, 15 Nov 2026)

PILOT · SOURCE-BASED · UNVALIDATED. Post-submission work on its own branch, in a separate worktree; nothing here changes a
bundle, the Decision Lab or `submission/merged`. Nothing goes into the submission unless Sid and Anish decide so.
Geometric visibility only (not power, not comms). k of N maps is not a probability.

**Scope tonight.** The ship and errors sessions had not pushed when this started (21:49 ET, Mac load average 18–68), so by
agreement only the light items ran, at low CPU priority: L1, L2, L3 (analytic part), L6, L7, L8 (calibration part).
The ray-march-heavy items were held until the submission was pushed (23:22 ET). In the ~25 min left before 23:59, under
shared load, two time-boxed runs fit: L3 numerical (nominal maps) and the L10 Certainty Height series (masts 1.0–2.0 m).
L4, L5, L8 (rest), L9 and the rest of L10 are **open**.
Every result is in `data/science_limits/<item>/` (result.json, manifest.json with input SHA-256s, README.md) and has a
test in `science/tests/test_limits.py`.

## Two findings that change the plan
1. **All 100 PGDA 78 clones are public, not 20.** `https://pgda.gsfc.nasa.gov/data/LOLA_5mpp/Site04/Clones/` serves
   `…_0001_err.tif` to `…_0100_err.tif` (HTTP 200, image/tiff, ~41 MB each; `_0101` does not exist); the product page lists
   100 per site. The statement "Barker used 100 clones (only 20 are public)" is wrong: L4 and L10 can use all 100.
2. **PGDA products ship the density and error layers L4/L5 need.** PGDA 78 has `SiteNN_final_adj_5mpp_ldec.tif` (LOLA
   spot count per pixel) and `SiteNN_final_adj.xyzi` (~31 MB, the co-adjusted laser shots). PGDA 90 has
   `LDEM_80S_{20,40,80}MPP_ADJ_ERR.TIF` (per-pixel height error) and `LDEC_80S_*` (counts). So L4's far-field members can
   use the documented per-pixel error rather than an assumed RMS, and L5's "interpolation flattens crests" test can
   use the real shot positions.

## Table

| | Limit | Done tonight | Result | Still open | What would close it |
|---|---|---|---|---|---|
| L1 | Centre-only visibility | Any-part / centre / full-disc variants, disc fraction (flat and tilted horizon), nominal + 20 clones, NAC v2 re-expressed | Site04 RoI 3 Sun % **97.03 / 94.36 / 92.28** (clones 88.13–99.70 / 87.54–97.33 / 86.65–95.25); Sun+Earth 79.23 / 72.11 / 65.28; longest hourly gap 10 / 19 / 26 h. Site01 RoI 6 Sun 100 % in all; Sun+Earth 86.05 / 81.60 / 77.15. "Disc fraction ≥ 0.5" is exactly the centre rule, so it does **not** shrink the NAC offset; the observed crossings (+0.31°, +0.45°) are 1.2–1.7 r☉, i.e. full disc up; vs a full-disc rule the offsets become +0.05° / +0.18°. | Sites 07/11 (no local clones/demo ephemeris); 12-month window | Fetch Site07/11 clones + Horizons; decide which rule a lander design needs (power model, not geometry) |
| L2 | Hourly sampling | Continuous timeline for nominal + 20 clones and all three variants; spline-interpolated Horizons validated against the bundle's real-Horizons bisection | Spline vs Horizons bisection: **≤ 0.2 s** on all 12 events. Nominal reproduces the bundle (94.213 %, 19.443 h). Site04 clones continuous Sun % 87.59–97.19, Sun+Earth 64.51–74.46, longest gap 9.44–41.72 h. Change vs hourly: Sun % ≤ 0.26 pt, longest gap ≤ 2.2 h (two sub-hour "blinks" over all maps). All refined transitions inside their hourly bracket. | Clone ephemeris spline validated only at nominal events | Real Horizons bisection for a few clone events (raw files for clones 1/11/20 already exist in the main checkout) |
| L3 | Numerical convergence | Analytic bound beyond 280 km; numerical sweep on the **nominal** maps of both sites: bins 720→1440→2880, near step 1→0.5 m, range 280→289 km (edge of loaded far window) | Even 10.8 km relief beyond 280 km changes **no hour** (min per-hour slack +3.8° Site04 Sun, +0.82° Site01 Earth). **Every refinement changes Sun % by 0.000 pt (PASS < 0.1 pt).** Near step 0.5 m moves single bins by up to 0.18° (Site04) / 0.06° (Site01), median 0; |ΔE| at the baseline azimuths is 0 for the bin refinements by construction (finer grids contain those azimuths), so the bin test checks inter-bin interpolation through Sun %. | Clones; near radius 25/50 km (5 m tile is ~16 km wide, cannot be tested); far DEM 40/20 m (not cached); range 600 km (outside loaded window; covered by the analytic bound) | Download PGDA 90 40/20 m windows; run clones 1 and 11 |
| L4 | Clone tile only | Not run (held) | Found the documented inputs: PGDA 90 per-pixel `_ERR` layers at 20/40/80 m; 100 public near-field clones | Whole item | Envelope = 100 clones + far-field members from the `_ERR` layer (correlation length still assumed: 1/5/20 km) + 20/40/80 m structural members |
| L5 | LOLA vs SfS | Not run (held) | Shot-density layer exists (`_ldec.tif`) and the raw shots (`.xyzi`) | Whole item; SfS region 6 tile not on this Mac | Download region 6 SfS + `_ldec`/`.xyzi`; regress SfS−LOLA on distance-to-shot, slope, illumination; 3D co-registration; write `docs/validation/LOLA_vs_SfS.md` |
| L6 | Hero point unobserved | Searched all 13 GSFC SfS regions (header reads) and PDS ODE; protocol + amendment frozen with SHA-256 before any pixel | **Hero point stays UNCHECKED.** No GSFC ortho-NAC/SfS region covers it (region 6 ends **322 m** short; all 322 of its NAC maps checked, none contains it). PDS ODE lists **234 raw NAC frames** over it (mostly 2010, incidence 87–93°) and **one ASU NAC stereo DTM** (`NAC_DTM_ESALL_SR12`, 2 m) containing it. | Orthorectification of frames; DTM download and test T | Run amendment A1 test T (relative height of the rise vs the point, pass ≤ 0.56 m); orthorectify frames onto a non-PGDA DEM and run Sets A–C |
| L7 | Knife-edge | Margin distribution, uniform-error robustness, dE/dh | Site04 RoI 3: **31 h** within ±0.5° (6 / 15 / 31 / 40 within ±0.1 / 0.25 / 0.5 / 1°; the earlier "32 h" differs by one hour of definition), **28 of them controlled by one 5 m cell 16 m away** (dE/dh = 3.58°/m). Sun % at horizon shifts −0.5…+0.5°: 99.8 / 96.7 / 95.2 / 94.8 / **94.2** / 93.9 / 93.5 / 92.4 / 90.7. The **70 % Sun verdict flips only at a uniform +2.0° raise** (Sun+Earth 40 %: +1.95°), equivalent to **+0.56 m** at the controlling cell. Site01: no hour within ±1°; flip at +2.73°. | Hour-level state is fragile, the 14-day verdict is not | L6 test T would measure the rise directly |
| L8 | Planning-model limits | **Calibration part**: toterr vs clone flip counts per site | No single factor: toterr **over**-predicts flips at Site04 (×1.41, 12 months) and Site01 (×1.69) but **under**-predicts at Site07 (×0.55) and Site11 (×0.70), with similar per-pixel σ ratios (0.63–0.77). At Site07 in the demo window toterr predicts ~0 flips; the clones show 50. | 32/64-ridge forecast + re-linearisation; swapped-fold planner | Run step3/step18c variants (needs the research `work/` caches) |
| L9 | Sampled what-ifs | Not run (held) | — | 10 m grid, Monte Carlo dispersion, two-lander re-score | ~880 skylines at Site04; run when CPU is free |
| L10 | Barker / Certainty Height | **Certainty Height part**: Site04 RoI 3, masts 1.00–2.00 m in 0.25 m steps × 21 maps (nominal + 20 clones), written to `data/science_limits/certainty_fine/` | Maps at 100 % Sun: 0 / 7 / 17 / **21** / 21 of 21 at 1.00 / 1.25 / 1.50 / **1.75** / 2.00 m; min Sun % 87.54 / 91.40 / 96.44 / 100. **Reproduces the published 1.75 m.** Correction: 100 clones are public (finding 1). | Masts 2.25–3.0 m; Barker all-pixel RoI averages; 100-clone versions | Run the rest of the series and step10_barker with all-pixel polygons on 100 clones |

## Reproduce
```bash
python -m science.limits.l1_disc
python -m science.limits.l2_timing
python -m science.limits.l3_far_bound
python -m science.limits.l6_search
python -m science.limits.l7_knife_edge
python -m science.limits.l8_calibration
python -m pytest science/tests -q
```
Needs `data/cache/` (PGDA 78 tiles and clones, LDEM 80 m; git-ignored, SHA-256 in the bundles).
