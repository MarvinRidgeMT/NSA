# POLARIS X — limits and errors across the whole product (Claude, 15 Nov 2026, 21:45 ET)

Sources: repo `submission/merged` docs (RELEASE_READINESS, SCIENCE_VALIDATION_REPORT, FINAL_AUDIT, validation/NAC, SVS4930, SITE01_SFS_OFFSET), bundles and sidecars read directly, and this session's own runs (LONG_FEATURES §0–10). Status everywhere: **SOURCE-BASED · UNVALIDATED**.

## A. Submission blockers and rule risks (fix tonight)
1. **The repo must be public, with no login.** `MarvinRidgeMT/NSA` was private.
2. **Pre-event work.** The first commit (14 Nov 15:24 UTC = 10:24 ET) is labelled "Snapshot: project folder as found". It imports work that existed before the 09:00 start, and the rules warn that early starts "can lead to disqualification". Disclose this honestly in the description, or ask the Local Lead.
3. **~1,334 uncommitted files from another session** sit on the submission branch: raw Horizons clone files, new scenario bundles, science/viewer.py, web src. The last green Mac run (86/86, cbf8420) predates them.
4. **Several agents share one branch.** I collided once and removed 55 lines of BUILD_STATUS; it was restored in ceaa61f. Only one agent should commit from now on.
5. **3D terrain/globe files are git-ignored** (NASA-derived .bin, GLB, NAC crop). A fresh clone shows no 3D terrain until they are rebuilt or fetched. Everything else works.
6. **Demo format** is ≤30 s with English subtitles (or ≤7 slides), and AI images or video need a watermark. **Use of AI** must be disclosed.

## B. What the numbers do NOT mean (state these in the pitch and README)
- **Geometric visibility of the Sun and Earth disc centres only.** It is not solar power, panel output or thermal, and it is not a DSN link (no link budget, antenna pattern or Earth-disc fraction). The only disc-fraction work is the Barker 2021 reproduction.
- **A point observer at the mast top.** Lander self-shadowing appears only in the illustrative Asset Twin (a 2 m × 4 m cylinder, not a design).
- **"k of 20 maps" is not a probability.** The 20 PGDA clones are NASA's uncertainty samples, not a calibrated distribution.
- **Airless geometry**, which is correct for the Moon. The pipeline uses JPL Horizons apparent az/el; the NAC check used SPICE MOON_ME, and MOON_PA would differ by 0.024°.
- **Hourly sampling.** Events between samples are not resolved, so the longest-gap figure (19.44 h) is a count of samples.
- **Mission window = 14 days** (14–28 Nov 2026). The 12-month and 18.6-year results are PILOTS from the cloud batch, not repo bundles.

## C. Scientific limits (biggest first)
1. **The clone range understates terrain uncertainty.**
   - The clones vary only the 5 m tile. Coverage at Site04 RoI 3: only ~34 % of window hours have a Sun-direction horizon set by terrain the clones vary (Earth 58–61 %). Site01 RoI 6 Sun is 9.5–11 %, Earth 0 %.
   - The rest of the horizon (80 m PGDA 90 out to 280 km) has no uncertainty model at all.
   - The 87.5–97.3 % clone range therefore covers about a third of the Sun-horizon hours.
2. **Two NASA terrain products disagree, and the truth is unknown.**
   - GSFC SfS sits above LOLA at all 13 RoIs checked, by 0.24–3.2 m (mean 1.54 m). The difference concentrates on lit crests (+0.33 to +1.09 m) and is ≤0.1 m on dim terrain.
   - Site11 RoI 4: the SfS 12-month Sun (75.85 %) is **outside** the 20-clone range (71.9–74.6 %) at every mast from 1 to 10 m.
   - Site01: SfS is 0.2–0.5 pts above the clone range at 1.5–10 m.
   - Site01 also has a local ~2 m rise in SfS at the site point (+1.97 m; docs/validation/SITE01_SFS_OFFSET.md).
3. **The observation check is mixed, and the hero point is untested.**
   - LROC NAC protocol v1 (region 6: Site01 area and the Site04 west strip): **NOT PASS**.
   - v2 + A1 on new terrain (Site07, Site11 areas): PASS.
   - The **Site04 RoI 3 lander point and its 16 m rise are not covered by any observed product**. Neither are the 1 m mast, the 20-clone spread or the 14-day window.
   - Both NAC crossings are positive (+0.32°, +0.45°): images look lit only when the model's Sun centre is a third to half a degree above the horizon. Near the horizon the model calls "visible" slightly earlier than images show lit. Part of this is centre-vs-disc (the disc radius is 0.27°).
   - SVS 4930: PASS, but on lit samples only at ~113 m/px, so it is a weak test. WAC (100 m) compresses bright pixels; it validates the regional pattern, not site ranking (POLARIS vs WAC ρ −0.52 at the 17 lit RoIs).
4. **Knife-edge sensitivity.** Site04 RoI 3 hinges on a rise 15–16 m away. Worst margin −0.50°, and 32 hours lie within ±0.5°.
   - Example of how fragile this is: the float32 bug (below) moved the horizon by up to 0.45° and the result by 0.6 pts.
   - The 20/40/80 m maps cannot see the rise at all: they give 100 % vs 94.4 % on the 5 m map.
5. **Resolution and range.** 720 azimuth bins (0.5°), 1 m ray step to 25 km, 80 m to 280 km, on a spherical Moon (R 1,737,400 m). Terrain beyond 280 km and anything under 5 m (boulders, regolith texture) is ignored.
6. **The sensitivity and planning models are approximate.**
   - The 16-ridge linearised forecast misses ridge switches: 12-month recall 0.82 at Site04. It captures only 37–44 % of the disagreement at Sites 07/11 (vs 90–95 % at Sites 01/04).
   - NASA `toterr` is wider than the clone spread (ratio 0.63–0.77), so error-map forecasts over-predict flips by about 1.5×.
   - Hotspot ranking **ties** the simple "measure the nearest cells" rule at Sites 01/04.
   - The out-of-sample planner wins by only 7–25 % and ties at Site11.
   - The surrogate screener is rank-only (ρ 0.995–1.0, mean error 0.06–0.15 pts). It is not for quoting.
7. **Sampled what-ifs.** The position grid is 25 m: a sampled grid, not a landing-dispersion probability. In the ellipse sweep, σ 100 m is truncated. Two-lander results use the nominal map only.
8. **Barker 2021 reproduction** uses 5 pixels per RoI and 20 clones (Barker used RoI averages and 100 clones). Agreement: mean +0.06 pts, range −0.38 to +0.66, ρ 1.00.
9. **Certainty Height 1.75 m** comes from the sampled mast list. The bundles carry no 1.75 m series, so the viewer shows only the sampled heights.

## D. Errors found and their status
| Error | Effect | Status |
|---|---|---|
| float32 heights in batch v2 (`core.Dem.open`) | Horizon up to 0.45° off; Site04 RoI 3 93.77 % instead of 94.36 % | Fixed (float64). **Open:** earlier BATCH_RESULTS_* project docs may still need the label "float32, superseded"; the PGDA 69 RMSE numbers were never re-run. |
| Batch vs repo gap (INDEX C19) | Explained by the float32 bug | Closed by the fix |
| Two solvers sample differently (bundle "repo solver" vs batch sweep) | Same quantity can differ by a fraction of a percent | Disclosed by the on-screen legend. **Coverage differs by 0.3–2.6 pts:** Site04 Sun 34.1 (batch) vs 34.4 % (bundle), Earth 58.5 vs 61.1 %; Site01 11.0 vs 9.5 % |
| Merge change: Coverage Gauge now prefers the batch sidecar over bundle `derived.coverage` | Displayed coverage may change by the amounts above | Deliberate (keeps session A's tested view). Note it in BUILD_STATUS |
| Site04 RoI 4 bundle coverage `all_hours_covered_frac` = 0.0 (Sun and Earth) | Looks wrong or empty for that RoI | **Unchecked.** Do not quote coverage for RoI 4 |
| Decision Lab (standalone, cloud batch) vs main viewer (repo bundles) | Two pipelines. They agree on the demo (94.36 / 72.11 / 19 h); the 12-month and new-site numbers exist only in the Lab | Labelled PILOT in the Lab. Keep it that way |
| WAC data offset, NaN in JSON, CSS colours in canvas, mobile overflow, slip-tolerance init | Viewer and data bugs | Fixed during the build |
| Earlier "1-day early start" wording | Wrong | Corrected to "2–7 days earlier" |

## E. Software and test limits
- **Tests:**
  - Mac (cbf8420): Playwright 86/86, Vitest 99 + 2 skipped, Blender 31 OK, app 25/25.
  - Cloud with software WebGL: 84/86. The 3D screenshot tests time out on software rendering; they are not assertion failures.
  - Re-run after the pending uncommitted work lands.
- **Performance:**
  - Mac pane p95 9.2 ms per frame.
  - GPU frame time on the Mac in focused Chrome has not been measured cleanly.
  - Low-end laptops and phones are untested beyond the 390 px layout checks.
  - The 3D view needs WebGL; without it there is a graceful fallback.
- **Static site, no backend.** The solver API (`tools/polaris_solver`) runs locally only; it is not deployed.
- **The Decision Lab is one self-contained ~3–4 MB page.** Threshold edits recompute only pass counts from precomputed values. It does not re-run the solver.
- **Browser storage is per-viewer and optional.** Nothing is shared between users.
- **Blender renders are presentation only.** Boulders and micro-relief are synthetic and labelled VISUAL.
- **Release label.** The one open gate, `independent-illumination-comparison`, is NOT_RUN for the hero point, so the label cannot move off UNVALIDATED.

## F. Suggested one-line disclosure for the submission
"Geometric Sun/Earth-centre visibility from NASA LOLA terrain and JPL Horizons; terrain uncertainty from NASA's 20 alternate maps, which cover only the near-field horizon; results agree with Barker et al. 2021 and pass an LROC NAC image check at two of three regions, but the hero site point has no observational validation. SOURCE-BASED, UNVALIDATED; not power or communications."
