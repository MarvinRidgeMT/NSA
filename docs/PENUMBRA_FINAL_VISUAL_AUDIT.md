# Penumbra Apex — final visual audit

Date: 14 Nov 2026, 20:10–20:52 EST. App: `web/` (React + R3F), hero bundle `polaris-x5d-roi-2026-11-14-v2.json` (Site04 ROI3, 401² × 5 m DEM), results bundle `site04_roi3_2026-11-14_14d_mast1m.json`.
Method: headless Chrome (SwiftShader WebGL) at 1440 × 900 plus 1512 × 982, 1920 × 1080, tablet (834 × 1112) and mobile (390 × 844), same script before and after (`audit.mjs`, 22 screens). Mac built-in browser used for dev/preview parity (see PRODUCTION_PARITY.md).

Screenshots: `web/docs/screenshots/penumbra/apex-before/` and `web/docs/screenshots/penumbra/apex-after/` (same file names).

## Top 10 defects (ranked by visibility) and what changed

| # | Defect (before) | Fix (after) | Screens |
|---|---|---|---|
| 1 | Mast-eye: the mast cylinder and its marker filled the frame; no terrain visible. | Camera sits at the bundle mast top, looks along the Sun azimuth ~2° down; mast mesh hidden in this view only. | 04 |
| 2 | Decision page mixed bundle (repo solver) and batch-sweep numbers without saying which is which (94.2 % vs 93.8 % nominal). | `bundle` / `batch sweep` source tags on every panel + a one-paragraph legend explaining why the two differ. | 08, 10, 11 |
| 3 | Coverage: two different quantities (blocked-sample tally 100 % Sun vs batch 34.1 % of all hours) shown side by side, unexplained. | "What is measured" and "Reading the two numbers" text, data-driven claim sentence ("20/20 tested realizations meet… However, only 34.1 %…"), the tally relabelled "blocked samples only". | 12 |
| 4 | No mast-height control in Explore. | Certainty Height instrument: chips for the 10 sampled heights only, ranges/nominal/pass counts/Sun+Earth/1 m comparison from the sidecar; 1 m and 10 m switch the bundle series; other heights draw a labelled outline mast and say the time series stays at 1 m. | 02, guide |
| 5 | Ridge caption duplicated the instrument callout and covered terrain (overhead). | Stage caption appears only for an explicit selection or in the Ridge of Record view (where it must say "beyond this 2 km crop"). | 05, 06 |
| 6 | Bundle select showed "Connecting Ridg…" for the ROI export. | Short option labels from the file name ("ROI export · 3 sites · 5 m DEM"); full label stays in title/provenance. | header |
| 7 | Instrument facts truncated ("41 samp…"). | Facts wrap instead of ellipsis. | 02 |
| 8 | Shadowed terrain pitch black; the 0.5° light clamp disclosed only inside "About this view". | On-screen light tag states the mode and the true elevation; toggle "Light: true Sun elevation" (key light off when the Sun is below the horizon); faint disclosed hemisphere fill in display mode. Applies to the crop-only path and the context surface (TerrainSurface). | 02–06 |
| 9 | Story: "NASA publishes 20 equally plausible versions". | "evaluated alternate NASA terrain realizations", with the limit stated (they do not exhaust what the ground could be). | 01 |
| 10 | "no DEM grid… 3D view" bundle warning shown on Decision/Evidence where it is irrelevant. | 3D-only warnings are shown in Explore only. | 08, 09 |

Also: Ridge of Record list (always available when attribution applies to the series shown) with Inspect → clock to the first attributed obstruction, ribbon outline of that run, bin highlighted, Ridge camera; "Back to the previous view" restores camera and sample. Guided demo (5 scenes) added.

## Known remaining issues (not fixed in this pass)
- Camera row wraps to two lines at 1440 px since the surface-layer picker (rebuild Phase 4/5, session A) joined it; "About this view" was moved up to clear it. A one-line layout is a design follow-up shared with session A.
- The floating "Earth · blocked" tag at the mast top is still drawn in every view (minor).
- Shadowed slopes remain very dark in display mode by design (airless Moon); no ambient boost beyond the disclosed fill.
- WebGL frame-rate was not measured on the Mac GPU (the built-in browser pane was hidden, which throttles rAF). Headless SwiftShader numbers are not meaningful for real hardware.

## Change log
| When (EST) | Who | Change |
|---|---|---|
| 2026-11-14 20:52 | Claude (Penumbra Apex session) | Created. |

## Final visual-quality pass (14 Nov 2026, 21:10–23:00 EST)
Compared at 1440 × 900 with V3 page 16 (Explorer) and page 18 (Decision); sheets in `web/docs/screenshots/penumbra/final/compare-v3-*.png`
(the boards are rendered from the canvas HTML; page 16 uses the board's own Site04 render).

**Explorer: what changed** (`explore-approach-prod-1440.png`, before: `before-explore-1440.png`)
1. Terrain shading: Lambert × 5.2 with a 0.56 grey clipped Sun-facing slopes to white and left the rest black. Now McEwen Lunar-Lambert photometry, regolith albedo ~0.16, AgX tone mapping, fixed exposure.
2. Shadows: the 10 m / 7.5° horizon map smeared crater shadows; the 5 m crop now uses cast shadows marched on the true DEMs (5 m crop, then 80 m regional, with lunar curvature), once per sample on the GPU (1.1 ms on the M5 Pro).
3. Light modes on screen: Display (Sun ≥ 0.5°, weak relief fill, labelled) vs Scientific (true elevation, no fill).
4. Approach camera: cross-lit (50–110° from the Sun azimuth, lowest bundle skyline), so slopes and shadows both read; before it looked into the Sun at backlit faces.
5. Sight lines: target line to the bundle first hit, skyline line in the same azimuth to the controlling point, margin arc and a label with the bundle margin and ridge; a ridge beyond the crop (R1, 128 km) fades at the crop edge and is labelled "beyond this crop".
6. Composition: one control row at 1440 (View · Display/Scientific · Surface), meta line instead of boxed chips, scrims, compact instrument (mast first, as on the board).
7. Ridge of Record: one camera move (the second, competing animation removed), a profile view beside the mast→obstruction line, controlling points drawn as dots (no invented line), ribbon run outlined.

**Explorer: five largest remaining differences from page 16**
1. Lighting: the board still uses an illustrative Sun (az 120°, 1.5°); the app shows the bundle Sun at the selected sample, so more ground is in shadow. Kept on purpose.
2. Header: the app carries bundle / site / scenario selectors, Guided demo and Provenance; the board has a bare nav.
3. Bottom bar: the app's temporal bar (clock, Play, go-to-UTC, two ribbon rows) is ~200 px; the board's Horizon Bar is ~150 px.
4. Instrument: ten sampled mast heights instead of the board's four; Sun-at-sample readouts and the ridge list add height (it scrolls).
5. The app draws scientific annotations (sight lines, labels, ridge dots) that the board's still image does not have.

**Decision: what changed** (`decision-prod-1440.png`, `decision-full-page.png`; page 2,310 → 1,867 px)
Hero = paper Decision Card + 1 m vs Certainty Height comparison (range bars on one 50–100 % scale, team-requirement lines, pass counts) + three takeaways; then "The evidence behind it". Tables, CSV hashes and methodology are one click away in expandable sections; the < 50 % coverage warning and the coverage claim stay visible. Mast scenario buttons moved onto the Certainty Height chart axis.

**Decision: five largest remaining differences from page 18**
1. The board's eleven-region table needs an all-region sidecar; the app's sidecar covers Site04 ROI3 only (not invented).
2. Board takeaway "5 m → 11 / 11" is all-region; the app's takeaways are this site's (+0.75 m, ≤ 78.9 %, coverage 34.1 %).
3. The card statement is longer (site name and "evaluated alternate terrain realizations" wording).
4. The board has "Copy link / Export PDF"; the app has Print / save PDF.
5. Header density, as on Explore.
