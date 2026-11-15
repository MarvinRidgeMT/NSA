# POLARIS X: long-feature pilots + Decision Lab viewer (Claude cloud session, Sun 15 Nov 2026, 00:07–01:55 and 13:32–15:10 EST)

*Session: Sid asked to "finish some of the unfinished features that take over 4 h" from the Features Not Done Yet sheet
(https://claude.ai/artifact/J4D38DPs3UWnur9CgPhPDa). Work done in this chat's Claude cloud workspace (2 cores, 7 GB) from NASA
data downloaded here. **No repo access** (no folder connected, no GitHub): nothing in `science/`, `web/`, bundles or git changed.
Code + results ZIP sent in the chat (`polaris_long_features_2026-11-15.zip`).*

**Labels:** SOURCE-BASED, UNVALIDATED pilots. Geometric visibility of the Sun/Earth **centre**, 1 m mast, 1 m near ray step,
720 bins, 5 m PGDA 78 + 80 m PGDA 90, JPL Horizons hourly. "Pass on k/20 clones" is not a probability. These are post-freeze /
roadmap results; nothing here should go into the 30-s video without Sid + Anish deciding.

## 0. Bug found first: `polaris_batch` v2 loses precision (resolves INDEX C19)
`core.Dem.open` reads heights as **float32**; `R_MOON + h` then stays float32 (NumPy 2 type rules; ~0.125 m resolution at 1.74e6 m).
At Site04 ROI3 the blocking rise is 15–16 m away, so the rounding moves the horizon by up to ~0.45°.

| Site04 ROI3, 1 m mast, 14–28 Nov 2026 | Sun % | Sun+Earth % | 20 clones Sun % |
|---|---|---|---|
| batch v2 as written (float32) | 93.77 | 71.22 | 87.2–97.0 |
| batch v2 with `astype(np.float64)` | **94.36** | **72.11** | **87.54–97.33** |
| repo / independent re-derivation (VALIDATION_CHECKS §2) | 94.36 | 72.11 | 87.5–97.3 |

So the batch-vs-repo gap (C19) was this bug, not the knife-edge/bin-placement explanation. **Quote the repo numbers.**
Fix for the batch session / third and fourth computers: in `core.py`, `z = ds.read(1).astype(np.float64)`. Batch results
already published (BATCH_RESULTS_CLOUD/THIRD/FOURTH) should be labelled "float32 heights, superseded". Certainty Height 1.75 m
is unchanged (all three sources agree). Not checked here: whether the PGDA 69 RMSE numbers move (they were run with the same code).

## 1. Jacobian + flip-forecast pilot (RQ2), sheet row 9: **done**
**Question:** can a sensitivity calculation on the *nominal* map predict which hours flip between visible and blocked across NASA's
terrain clones, without ray-marching the clones?

**Method.** Analytic derivative of horizon elevation with respect to terrain height at the controlling point, dE/dh, and with
respect to the lander's own ground height, dE/dh0. Forecast A: linearised clone horizons from 3 pixel lookups (controlling
point, runner-up, lander). Forecast A16: the same over the top 16 distinct ridge candidates per azimuth (captures ridge
switching). Forecast B: no clones at all; NASA's `toterr` sigma + Gaussian. Truth: full ray march on clones 1–20.

**Finite-difference test** (raise a 4×4 pixel block at the controlling point by 0.25 m / 1 m, re-march that azimuth):
terrain Jacobian within 5 % in 21/24 (Site04, median error 0.27 %) and 23/24 (Site01, 0.07 %). Lander-height Jacobian
within 5 % in 10/12 and 5/12. The failures are ridge switches (raising the lander makes a different ridge control), which is why
A16 carries one candidate per ridge.

| Forecast | Window | Truth: flip hours (any clone) | Recall | Precision | Clone Sun % range predicted vs true |
|---|---|---|---|---|---|
| A16 linearised | Site04 ROI3, 14-day demo | 33 | **1.00** | **1.00** | 87.54–97.33 vs 87.54–97.33 |
| A16 | Site04 ROI3, 12 months | 1,410 | 0.82 | 0.98 | 64.6–75.6 vs 62.7–75.5 |
| A16 | Site01 ROI6, 12 months | 588 | 0.92 | 0.99 | 80.5–86.2 vs 80.1–86.1 |
| A (controlling point only) | Site04, 12 months | 1,410 | 0.63 | 0.96 | |
| B (toterr only, P(any of 20) ≥ 0.5) | Site04, demo | 33 | 1.00 | 0.48 | flags 69 h |
| B | Site04, 12 months | 1,410 | 0.72 | 0.50 | |
| B | Site01, 12 months | 588 | 0.67 | 0.53 | |

Per clone-hour (A16, 12 months): Site04 recall 0.89 / precision 0.98, 99.47 % of clone-hours predicted correctly; Site01 0.90 /
0.95, 99.86 %. (Site01 ROI6 has no flips in the demo window: 100 % Sun on all clones.)

**Findings.**
- A linear model with ridge candidates reproduces the 20-clone result **exactly in the demo window** at the cost of pixel lookups
  instead of 20 ray marches. Over a full year, misses are remaining ridge switches and nonlinearity.
- NASA's `toterr` is wider than the clone spread at the controlling points (clone std / toterr median 0.63 Site04, 0.77 Site01),
  so forecast B over-predicts flips by ~1.5× (expected 10,512 vs observed 7,261 flipped clone-hours at Site04). Clone errors at
  the lander and at the rise 15 m away are nearly uncorrelated (median ρ 0.09 / 0.03).
- At Site04 ROI3 the clones put the lander cell 0.21 m **lower** than the nominal on average (std 0.13 m). Not investigated.

## 2. Information Hotspots pilot (PDF §5 #2), sheet row 14: **pilot done**
**Score** per 5 m cell = expected Sun flip-hours removed if that cell were measured to 0.05 m (forecast B, 12 months).

| | Site04 ROI3 | Site01 ROI6 |
|---|---|---|
| Expected flip-hours / year (toterr model) | 494 | 126 |
| **Lander's own ground cell** | **145 h** (toterr 0.31 m) | **40 h** (0.27 m) |
| Top other cells | rise 13–17 m away (19, 19, 11, 7 h); a cell 133 m away with toterr 1.23 m (4 h) | cells 28–48 m away (10, 4, 3 h …) |

**Test that can fail.** In each of the 20 clone worlds, "measure" a set of cells (copy the clone's heights in a 3×3-pixel block
into the nominal map), re-run the full ray march, and count clone-hours where the updated map still disagrees with that clone
(12 months; nothing measured = Site04 7,261, Site01 1,701):

| Measured | Site04 ROI3 | Site01 ROI6 |
|---|---|---|
| top-10 hotspots | 7,055 | 1,498 |
| 10 random controlling cells (3 draws) | 6,806–7,258 | 1,690–1,697 |
| 10 nearest controlling cells | 6,803 | 1,497 |
| lander cell only | 5,748 | 1,224 |
| **top-10 hotspots + lander** | **769 (−89 %)** | 513 (−70 %) |
| 10 random + lander (3 draws) | 2,884–5,733 | 1,138–1,198 |
| **10 nearest + lander** | 906 (−88 %) | **462 (−73 %)** |

Demo window, Site04: hotspots + lander and nearest + lander both → **0** disagreeing clone-hours (from 243); top-10 without the
lander → 267 (worse: fixing the rise but not the lander removes errors that used to cancel).

**Reading.** (1) The decision is driven by the lander's own height plus the terrain within ~50 m; measuring both removes
70–89 % of clone disagreement, 10 random cells + the lander remove 21–60 %. (2) The hotspot ranking beats random clearly but
**ties the simple "nearest terrain" rule** at these two sites (better at Site04, slightly worse at Site01). So the claim we can
make is "the hotspot map identifies what to measure, and here it agrees with the near-field rule", not "hotspots beat simple
heuristics". (3) The `toterr` model ignores error correlation; a correlated model is the next step. Sites with far controlling
ridges are where the hotspot ranking could differ from "nearest"; not tested.

## 3. 12-month window strip + arrival-slip sweep + season comparison (PDF §4 B7, B5, A9), sheet rows 41, 42, 44: **science side done**
Every hourly 14-day mission start from 14 Nov 2026 to 14 Nov 2027 (8,761 starts), nominal + 20 clones, team thresholds.

| 14-day starts over 12 months | Site04 ROI3 | Site01 ROI6 |
|---|---|---|
| all 20 clones ≥ 70 % Sun | 38.8 % | 65.8 % |
| clones disagree (MARGINAL) | 28.8 % | 9.9 % |
| no clone ≥ 70 % Sun | 32.4 % | 24.2 % |
| all 20 ≥ 40 % Sun+Earth | 31.3 % | 47.1 % |
| longest Sun gap ≤ 120 h on all 20 | 62.5 % | 83.2 % |
| hourly Sun-centre over the year (nominal) | 73.8 % | 85.1 % |

**Arrival slip around the demo start (14 Nov 2026 00:00 UTC), Site04 ROI3:** the nominal stays at 94.36 % for any start from
−6 h to +7 days, but the worst clone falls steadily: −24 h 94.7 %, 0 h 87.5 %, +12 h 85.2 %, +24 h 81.6 %, +48 h 74.5 %,
+72 h 69.7 %. **All 20 clones stay ≥ 70 % for starts up to +63 h; from +64 h one clone fails.** Worst-clone longest Sun gap
grows from 42 h (0 h) to 102 h (+72 h); nominal 19 h throughout. Starting 2–7 days *earlier* gives 100 % Sun on every clone.
Site01 ROI6: 100 % Sun on every clone for every start in ±7 days.

**Seasons (Site04 ROI3, nominal mean Sun % of 14-day starts by start month):** Nov 95.6, Dec 96.1, Jan 90.3, Feb 78.0, Mar 44.4,
Apr 31.3, May 33.2, Jun 50.9, Jul 78.8, Aug 91.7, Sep 96.1, Oct 97.4. Site01 ROI6: 100 % Aug–Jan, lowest Apr–May (~50 %).
No April–May start passes 70 % on all 20 clones at either site (at Site04 the nominal never reaches 70 % then).

**Story line (for Sid, optional):** "The demo window is robust to a 2½-day launch slip, but not to a 3-day one" is a sharper,
true statement than the window alone; it also shows why the nominal number hides the risk (nominal flat at 94.36 %).

**Viewer handoff (Anish, post-freeze):** `results/strip_<site>.csv` in the ZIP has one row per start (nominal, clone min/max,
Sun+Earth, longest gap, k/20 for both thresholds); `slip_pm7d.json` has the ±7-day curve. No computation needed in the browser.
Figures: `window_strip_12mo.png`, `arrival_slip_pm7d.png`, `information_hotspots.png`.

## 4. Not done (and why)
Superseded by §6 (01:55): the viewer, Failure Replay, Sky Envelope, Repairs, Decision Card, Barker reproduction, Model
Disagreement Lens pilot and landing-ellipse pilot are now done. Still not done: anything inside the repo's `web/` (no access; the
viewer is a standalone page), LROC WAC observed-illumination validation, the months-long roadmap items.

## 6. Round 2 (00:59–01:55): the Decision Lab viewer and the remaining features
Sid chose: a **standalone page** (no repo access; nothing in `web/` changed) and "everything I can finish tonight".

**Viewer: POLARIS X Decision Lab**, https://claude.ai/artifact/A2AYd1jPf99LgsSfUX6odN (private to Sid until shared; one
self-contained HTML file, 3.4 MB, all data embedded, team palette, light + dark, checked at 1366 px and 390 px, no script errors).
Both sites; editable thresholds (default team 70 % / 40 %, plus longest dark ≤ 120 h) recompute every pass count from per-clone
values in the browser. Sections: Decision Card, 12-month strip, seasons, arrival slip (slider), Sky Envelope, Failure Replay,
Repairs (mast / timing / position), Information Hotspots, Evidence (RQ2, Model Disagreement Lens, Barker 2021).

| Feature (sheet row) | Result (SOURCE-BASED, 1 m mast unless stated) |
|---|---|
| Decision Card (7) | Card per site with requirements, nominal, clone range, k/20, verdict, Certainty Height, slip tolerance, best nearby spot, top hotspot, input SHA-256. Print = browser Print (only the card prints); "Copy card as text". The repo version (`science/decision_card.py`, byte-identical tests) is still a-science's task. |
| Failure Replay (8) | Site04 ROI3: one blocked interval, **26 Nov 23:00 → 27 Nov 17:00 UTC, 19 h, worst margin −0.50°**; 32 hours stepped (blocked + \|margin\| < 0.5°) with Sun az/el, horizon, margin, controlling ridge (15–16 m), terrain profile, clones still lit (e.g. 17:00 on 26 Nov: +0.48°, Sun visible on 8/20 clones). Site01 ROI6: no blocked hour. |
| Sky Envelope (16, 18) | 18.6-yr cycle (2024-01-01 → 2042-09-01, 6 h, 27,273 samples): Sun centre above the nominal 1 m skyline **72.9 %** (Site04 ROI3) / **84.2 %** (Site01 ROI6); Earth 51.3 % / 53.5 %. Sun range straddles the skyline on 247 / 204 of 360 azimuth degrees; always blocked on 9 / 0. |
| Inline-editable thresholds (19), longest-darkness row (20) | In the viewer header; the card has a "Longest Sun-blocked stretch ≤ 120 h" row (Site04 ROI3 demo: nominal 19 h, clones 9–42 h). |
| Repairs: mast (21) | Masts 1–10 m × 21 maps. Certainty Height **1.75 m** (Site04 ROI3; clone ranges 1.25 m 91.4–100 %, 1.5 m 96.4–100 %, = repo A2). New: keeping **every 14-day start of the year ≤ 120 h dark on every map** needs a **5 m mast at both sites** (worst start: Site04 ROI3 127 h at 3 m, 69 h at 5 m; Site01 ROI6 130 h at 3 m, 112 h at 5 m, 102 h at 10 m). |
| Repairs: timing (21) | All three requirements on all 20 maps: Site04 ROI3 **−120 h to +63 h** around 14 Nov 00:00 UTC (early side fails Sun+Earth); Site01 ROI6 −140 h to beyond +7 d. |
| Repairs: position (21) + landing-ellipse pilot (43) | 9×9 grid at 25 m (±100 m, grid axes polar-stereographic), nominal; inner ±25 m with clones 1–10. Site04 ROI3: three cells 25 m away (grid 0,+25 / +25,0 / +25,+25) are **100 % Sun on all 10 clones** vs 94.36 % (clones 88.7–96.1 %) at the centroid. Within 50 m, 12 of 13 grid points pass all three requirements (nominal); within 100 m 27 of 49 (Site01 ROI6: 13/13 and 40/49). A sampled grid, not a landing-dispersion probability. |
| Model Disagreement Lens pilot (15) | Same decision on PGDA 78 5 m (+80 m), PGDA 90 20 m, 40 m, 80 m. Site04 ROI3 demo Sun: **94.4 % on 5 m vs 100 % on 20/40/80 m** (only 5 m resolves the rise); 12 months 73.8–81.4 %. Site01 ROI6: all four agree on the demo window (100 % / 81.6 %); 12 months 82.2–86.0 %. |
| Barker 2021 reproduction (26) | Barker et al. 2021 Table 2 (Site01 RoIs 1–7, 5 m above surface, 1 Jan 2024 – 1 Jan 2026 hourly, visible disc fraction, RoI-averaged, 1st percentile of 100 clones). Ours (5 pixels per RoI, 10 clones): worst clone minus Barker **−0.34 to +0.68 pts** (mean +0.10), nominal +0.74 pts, rank correlation **1.00**. **RoI 4 (the 88.1 %): ours 87.8 % worst clone, 88.2 % nominal.** RoI polygons from PGDA `Site01_ROIs.tgz`. |
| 12-month strip, seasons, arrival slip (41, 42, 44) | Now in the viewer, live with the thresholds (§3 numbers used Sun only; with all three requirements, 15.8 % of Site04 ROI3 starts pass on every map). |

Code for round 2 (in this workspace; added to the ZIP on request): `jobs.py`, `make_jobs.py`, `step6_ephem2.py`, `step7_replay.py`,
`step8_sky.py`, `step9_lens.py`, `step10_barker.py`, `build_data.py`, `viewer_template.html`.

## 7. Round 3 (13:32–15:10, after the freeze): remaining computable features
Sid: "continue the features". Viewer republished at the same link (https://claude.ai/artifact/A2AYd1jPf99LgsSfUX6odN, version
`1794776046-b203`): new Layout section, Measurement planner, two Evidence cards (SfS, WAC), Skeptic mode + grounded narrator.
Still no repo access; nothing in `web/` changed. All SOURCE-BASED; 1 m mast unless stated.

| Feature (sheet row) | Result |
|---|---|
| Position grid + Barker at **20 clones** (21, 26) | Replaces last night's 10-clone compromise. Site04 ROI3: grid (0,+25) and (+25,+25) stay **100 % Sun on all 20 clones** (14-day demo); (+25,0) 99.1–100 %. Barker Table 2: worst of 20 clones minus Barker's 1st percentile **mean +0.06, range −0.38 to +0.66 pts, ρ 1.00**; RoI 4: 88.2 % nominal, 87.7 % worst clone vs 88.12 %. |
| **Two-lander complementarity** (46) | 9×9 grid ±100 m, 12 months hourly, nominal. **Site04 ROI3: one lander at the centre 73.8 % Sun, worst dark stretch 461 h; best pair 250 m apart (grid −100,+100 / +50,−100) 86.6 % with at least one lit, worst both-dark 98 h.** Site01 ROI6: 85.1 % / 164 h → best pair (56 m) 86.9 % / 129 h: little gain. |
| **Landing-ellipse sweep** (43) | Isotropic Gaussian scatter, grid-weighted, all three requirements, demo window. Site04 ROI3: σ 10 m 100 %, 25 m 91.8 %, 50 m 65.3 %, 100 m 54.6 % of the scatter passes. Site01 ROI6: 100 / 99.4 / 85.9 / 71.6 %. Sampled grid, σ 100 m truncated. |
| **Measurement planner** (45) | Greedy, NASA `toterr` model, 12 months. Step 1 is always the lander's own ground cell (Site04 494 → 349 expected flip-h/yr; Site01 126 → 85); then the rise 13–17 m away (Site04) or cells ~30 m away (Site01); after ~10 cells extra measurements buy little. Consistent with the full-ray-march test (§2). |
| **Asset Layout Twin pilot** (17) | Illustrative lander body: 2 m-radius, 4 m-tall cylinder (not a design). Per-asset skylines + self-shadowing, 12 months. Ground panel 5 m away loses ~950–1,100 h/yr to the lander body (Site04 72.1 → 61.3 % Sun); deck-top panel at 4.5 m: 87.0 % (Site04), 88.4 % (Site01), longest gap 69 h / 112 h. **Antenna 5 m on the far side from Earth sees Earth 0 % of the year** (from the south pole Earth stays toward grid north, behind the lander); on the Earth side 51–52 %. Power + Earth link together: 44.8 % (Site04) / 47.4 % (Site01) with the good layout, 0 % with the bad one. |
| **Model Disagreement Lens + NASA GSFC SfS** (15) | Added the GSFC shape-from-shading DEM (Bertone et al. 2026, Zenodo 10.5281/zenodo.17954508, CC-BY-4.0, region 6 Connecting Ridge, same 5 m lattice as PGDA 78). Site01 ROI6, 12 months: **SfS 85.25 % vs LOLA 85.10 % (20 clones 80.1–86.1 %)**; inside the clone range at 1–1.25 m, but **0.2–0.5 pts above it at 1.5–10 m** (clones too narrow there). SfS puts the lander's ground **1.99 m higher**. Split test: SfS only within 100 m → 86.0 %; SfS only beyond 150 m → 81.9 %: near and far differences pull in opposite directions and mostly cancel. SfS vs LOLA disagree on 109 h/yr; the LOLA clones flip on only 66 of them. Position grid (81 cells): 3 verdict changes; one cell 25–55 m away goes 100 % → 34.7 % Sun. Barker RoIs on SfS: +0.86 pts vs Barker (−0.29 to +2.35). Site04: SfS covers only the west 26 % of the tile (not the lander or its rise); hybrid result unchanged (94.36 %). |
| **LROC WAC observed illumination at 17 RoIs** (27) | PDS `WAC_POLE_ILL_TWI_SOUTH_100M` (one lunar year, 15 Feb 2010 – 5 Feb 2011, 3,807 images, 100 m). Model run for the same year (2 h, 0.5 m, 5 points per RoI). **Registration verified** over all of 88–90° S: WAC vs PGDA 69 Pearson r = 0.956 (flipped orientations ≈ 0); below 50 % they agree bin by bin within ~2 pts. **But WAC compresses bright pixels** (max 71.7 %; PGDA 69 70–80 % → WAC 52 %), so at the 17 well-lit RoIs every model reads ~30 pts above WAC and ranks differ (POLARIS ρ −0.52, PGDA 69 ρ 0.32, POLARIS vs PGDA 69 ρ 0.23). Conclusion: WAC validates the regional pattern, not landing-site ranking; a finer observed product is needed. |
| **Skeptic mode + grounded narrator** (49) | In the viewer: each headline claim, its strongest objection, what was checked, link. Narrator paragraph built by fixed templates from the page data (no language model), every number linked to its section; follows the threshold inputs. |

Not done (needs the repo, a team decision, or months): rebase/commits/captions (10, 11, 36), repo bundle hash on two machines (29),
Playwright traceability scan in `web/` (28), Blender renders (12), walkthrough (13), AI drawer / solver API / surrogate (23, 38, 39),
relay comms, rover sorties, moonshots, Shadow Tomography (47, 48, 50, 51), decisions (31–35, 37).

Code (this workspace): `step10_barker.py` (20 clones + SfS), `step11_sfs_prep.py`, `step11_sfs_analyze.py`, `step11b_split.py`,
`step12_more.py`, `step13_asset.py`, `step14_wac_prep.py`, `step14_wac_analyze.py`, `build_data.py`, `viewer_template.html`.

## 5. Handoffs
- **Batch session / 3rd + 4th computers (P1):** apply the float64 fix (§0) and relabel published batch numbers.
- **Organizer (P3):** add this doc to INDEX, close C19 with §0, CHANGELOG row "15 Nov 00:07–00:50, long-feature session:
  float32 bug in batch v2 (explains C19); RQ2 pilot; Information Hotspots pilot; 12-month strip / arrival slip / seasons".
- **Sid + Anish:** whether the arrival-slip line goes in the story (§3); nothing here changes the demo-window numbers (repo values).
- **Anish (post-freeze):** port viewer sections into `web/` if wanted; the page's `build_data.py` output is the data contract.
- **Sid + Anish:** the SfS result is a science lead worth one sentence in the pitch only if you want it: an independent NASA terrain product agrees at Connecting Ridge (85.25 vs 85.10 %), but by partial cancellation.
- **a-science:** repo Decision Card (`science/decision_card.py`) still open; the viewer's card is a stand-in.

## Change log
| When (EST) | Change |
|---|---|
| 15 Nov 00:45 | Created. |
| 15 Nov 15:10 | §7 added (round 3: 20-clone upgrades, two-lander, ellipse, planner, asset twin, SfS, WAC, skeptic mode). |
| 15 Nov 01:55 | §6 added (Decision Lab viewer + round-2 features); §4 updated. |
| 15 Nov 00:50 | Wording checked against the result files: early-start claim (2–7 days, not 1), April–May wording, random+lander range 21–60 %. |
