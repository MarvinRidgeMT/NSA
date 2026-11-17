# POLARIS X v2 — final report (16–17 Nov 2026)

Branch `feature/v2-whole-moon` (worktree `../NSA-v2`), cut from `feature/5d-complete` at ae9f6d9. 128 commits.
**Not pushed.** Prompt: `docs/v2/inputs/CLAUDE_CODE_PROMPT_6D_worlds_blender_v2.md`. Per-session detail: `docs/v2/STATUS.md`
and `docs/BUILD_STATUS.md`. Every science number in this report is SOURCE-BASED · UNVALIDATED unless it is marked otherwise.

## 1. How it was built
Fifteen parallel sessions ran in three rounds. Each worked in its own worktree and branch; the coordinator merged them.
- **Round 1:** S1–S6.
- **Round 2:** R1–R6.
- **Round 3:** T1–T3.

The split is recorded in `SPLIT.md`, `SPLIT_ROUND2.md` and `SPLIT_ROUND3.md`. The interface between data, pyramid and
solver is `TERRAIN_STACK_CONTRACT.md`; it was changed only through dated amendments.

## 2. What exists now, by prompt section
| § | State | Main results |
|---|---|---|
| §1 6D model, cube v2 | done | Decision axis; `schemas/scenario-cube-v2`; slicer grouping |
| §2.1 data | done (unvalidated inputs) | 105.9 GB, 172 files, each with a SHA-256 manifest entry. Not downloaded: Ch-2 TMC-2 and CNSA (both need accounts). |
| §2.2–2.3 pyramid, seams | done, partial in places | 85,982 COG tiles for the whole Moon (git-ignored). 96.5 % of the area is 40–80 m; 0.064 % is ≤ 5 m. 20 product seams and 2 zone seams pass. Craters/boulders not added. Quantized mesh built instead of 3D Tiles. |
| §2.4 any-site solver | done | The pyramid is the default terrain; the legacy stack gives exact identity. 1,251 precomputed sites. |
| §2.5 global analytics | done | Earth visibility for the whole globe (0.125°) and the poles (1 km). Sun visibility at the poles. Slope and roughness. All are display-only layers in the viewer. |
| §3 worlds | partial | World API. Mercury: Prokofiev and a south-pole site. Mars: one site, Jezero rim, served by the solver API; relay-orbiter geometry for 14–30 Nov 2026 (`MARS_RELAYS.md`). Mars has no sky model, and neither Mercury nor Mars has a cube or Decision Card. |
| §4 decision tools | partial | Robust choice, regret, value of information, landing search and Pareto, all for the two precomputed sites only. Not run across the whole Moon. |
| §5 Blender | done, partial in places | Whole-Moon globe: a 2.0 MB Draco GLB that passes the glTF provenance proof. Pyramid close-ups anywhere. WAC albedo, shadow-free. Hapke shading. Blender run_all 14/14. |
| §6.1, 6.3 imagery, protocol | done (orbital metadata only) | Catalogue of 7,298 images. Protocol pre-registered. |
| §6.2, 6.4–6.5 render vs real | partial: LROC NAC dev pilot and held-out run done; WAC, ShadowCam, Kaguya TC not scored | See §3 and §3a. |
| §7 NASA-user features, gates | partial | Exports, solver API (OpenAPI, 14 routes) and gates exist. All gates pass after the 17 Nov fixes (accessibility and 390 px: `GATES.md` §8). Single long frames traced; the shader-compile stalls are fixed (`GATES.md` §9). AI planner not built. |

## 3. Render vs real (R4), dev split only, not the held-out headline
- **Rows scored:** 181 NAC image × site rows on the LOLA/LRO RS GRGM900C orbit (amendment A4), plus 7 rows with only the FDF orbit.
- **Scores**, PGDA 78 5 m, Hapke, registered:
  - shadow IoU median 0.946 (IQR 0.898–0.965);
  - shadow-edge median 5.4 m;
  - unregistered: 0.923 and 10.2 m;
  - flat-sphere control: IoU 0.000.
- **Finding:** the NAIF `lrorg` FDF orbits are off by up to about 330 m against GRGM900C. The render-vs-real registration offsets measured this before A4 switched orbits.
- **Weak spots:**
  - The 21 windows that are ≥ 98 % predicted shadow have a median IoU of 0.532.
  - SSIM is low (0.35); there is no scattered-light model.
  - An along-Sun offset bias is unexplained.
- **Pre-registration:** all 9 pre-registered SHA-256s verify at merge. Amendments A1–A4 were each registered before the scores they govern; two earlier-scored rows are kept and disclosed in A3.
- **Gallery images:** the 29 report JPEGs are crops of NASA LROC NAC images and are **not in git**. They are rebuilt locally by `python -m tools.validation.render_vs_real.report`.

## 3a. Render vs real, held-out run (Amendment A5, 17 Nov 2026)
Report: `docs/validation/RENDER_VS_REAL_HELDOUT.md`. SOURCE-BASED · UNVALIDATED · held-out. LROC NAC only.
- **Order:** A5 and the hashes of every code file the run executes were registered (e8164af) before any held-out image
  was fetched. The run (16:48–19:29 UTC, one start, no resumption) verified the hashes first.
- **Rows:** 680 held-out NAC rows; 498 gated by the §2 metadata rules; 32 gated by the geometry fit; 150 scored, 0 failed.
  144 are on the GRGM900C orbit (the claim set) and 6 on FDF only (reported, never in the claim).
- **§8 claim, PGDA 78 5 m (headline): met at all four sites**, each site judged on its own:

  | site | n | median shadow IoU | median edge m (limit) | beats flat control: IoU / edge |
  |---|---|---|---|---|
  | site04_roi3 | 34 | 0.965 | 6.5 (8.4) | 31/34 / 29/34 |
  | site01_roi6 | 34 | 0.953 | 4.6 (8.6) | 33/34 / 32/34 |
  | site07_roi1 | 35 | 0.937 | 5.0 (7.2) | 33/35 / 29/35 |
  | site11_roi4 | 41 | 0.902 | 5.2 (6.7) | 38/41 / 33/41 |

  - **site11_roi4 is one row from failing** condition 3 (edge: 33/41 = 80.5 %, the threshold is 80 %).
  - **The edge limit is 2 × the 5 m analysis pixel**, a reading chosen after the dev pilot and disclosed in A5.6. Against
    2 native NAC pixels (median 1.3–1.4 m) no site passes.
  - **Other products:** LOLA LDEM_875S 5 m meets the claim at three sites and fails the edge condition at site04_roi3
    (9.2 m vs 8.4 m). PGDA 90 80 m fails the edge condition at every site (30–39 m).
- **Held-out vs dev** (PGDA 78, Hapke, registered): shadow IoU median 0.941 vs 0.946; edge 5.2 m vs 5.4 m; SSIM 0.29 vs 0.35.
- **Weak spot confirmed:** the 24 near-total-shadow windows (predicted shadow ≥ 98 %) have a median shadow IoU of 0.492 under
  the fixed Otsu rule, against 0.949 for the rest. On the A5.5 count-matched mask (sensitivity only) they score 1.000, and
  the worst row overall (M146860458LC, IoU 0.119) scores 0.953: the failures are in thresholding the image, not in where
  the render puts the shadow. All 17 rows with a registration NCC below 0.05 are in this stratum, as are 12 of the 13
  registration offsets beyond 60 m.
- **Flat control:** its median shadow IoU is 0.490 here and 0.000 on dev, because 88 of 144 held-out rows have the Sun
  below the flat horizon (the control predicts all shadow) against 82 of 181 on dev.
- **Gallery:** the thumbnails are crops of NASA LROC NAC images; built locally, not committed.

## 4. Tests on the final branch (17 Nov ~03:00 EST)
- pytest `science tools`: 779 passed, 3 skipped.
- Blender `run_all.py`: 14/14, with `POLARIS_PYTHON` set to the project venv.
- vitest: 175/175. Build: OK.
- Playwright on :4199: 105 passed, 4 skipped, 2 failed:
  - `cold-launch` only works on port 4173;
  - the final-apex P6 sight label passes alone (2/2).

## 5. Rule checks
- **Frozen refs unchanged:**
  - `submission-2026-11-15` c5dce9f
  - `submission-final` 8dde4f1
  - `submission/merged` 62cc7b1
  - `main` 8dde4f1
  - `codex/lab-integration` d24fae3
- **No NASA/JAXA/ISRO/CNSA raster, mesh or image was added in v2.** The images v2 added (`docs/v2/phase4/*.png`,
  `blender/tests/reference/*.png`, `docs/v2/gates/*.png`) are POLARIS renders and screenshots. The instrument names in
  some file names are POLARIS camera presets, not mission images. The data products, derived PNGs and GeoTIFFs, the
  globe GLB and the R4 gallery JPEGs are git-ignored and rebuilt by scripts.
- **Committed before v2, not touched:** NASA files such as the PGDA 78 TIFFs under `app/data/source/` and the SVS GLB.
- No secrets and no paid services were used; no accounts were created.

## 6. Open items, in suggested order
1. ~~Point T2's "compute now" at T1's `/v1/solve` (:8767).~~ **Done 17 Nov** (see `BUILD_STATUS.md`). The same pass fixed
   "Python quit unexpectedly": git provenance calls forked while PROJ was in use; they now use posix_spawn (`science/gitinfo.py`).
2. ~~Fix the accessibility and 390 px mobile gate failures.~~ **Done 17 Nov:** axe 0 serious, 390 px 5/5 (`GATES.md` §8).
   Adding axe-core as a devDependency still needs your OK.
3. ~~Move the 10.3 MB Mars bundle JSON out of git, or compress it.~~ **Done 17 Nov:** stored gzipped, 1.6 MB (content unchanged).
4. ~~Before the held-out render-vs-real run: register A5 (Otsu on near-total-shadow windows), then run it.~~ **Done 17 Nov** (§3a). Score WAC, ShadowCam and Kaguya TC (each needs its own amendment and held-out run). ~~Wire `RealVsModel.tsx` into the app.~~ **Done 17 Nov:** on the Evidence page; images rebuilt locally (not in git).
5. ~~Mars relays~~ **(geometry done 17 Nov, `MARS_RELAYS.md`; MAVEN has no trajectory for the window)** and the Mars sky model. Clone members for Mercury and Mars, so they can have a cube and Decision Card. Decision tools across the whole Moon.
6. Rerun the Moon precompute: the legacy eq caches now include SLDEM2015.

## 7. After this report (17 Nov, afternoon)
- e8164af, 6177758: Amendment A5 registered; held-out report formatter. Then the held-out run (§3a) and its report.
- 2138ca9: Mars relay-orbiter geometry at the Jezero rim (`docs/v2/MARS_RELAYS.md`).
- 665e94a: the solver API serves the precomputed Mars bundle instead of 501.
- 0cc3b2f: frame stalls traced; scene shaders compile before interaction (`GATES.md` §9).
