# Final visual QA (Final Apex P6 + P12)

15 Nov 2026, Penumbra session. This extends `docs/PENUMBRA_FINAL_VISUAL_AUDIT.md` (14 Nov). The V3 PDF was not attached to the session. The reference is the V3 canvas source the PDF was made from: the board files in the V3 Penumbra canvas project, rendered at 1440 px wide.

| Page | Board |
|---|---|
| 13 | Scientific panels and charts |
| 16 | Main application · Explorer |
| 17 | Sky and horizon |
| 18 | Decision |
| 19 | Evidence and provenance |
| 20 | Responsive variations |

App screenshots are in `web/docs/screenshots/penumbra/apex_final/` (1440×900 unless named otherwise).

**Kinds of difference.** **Defect** = should match and did not. **Deviation** = differs on purpose, with the reason given. **Data** = the board shows numbers the viewer has no file for. Those are not drawn: a mock-up number is never shown as a result.

## Page 16 · Explorer

| # | Difference | Kind | Action |
|---|---|---|---|
| 1 | At 1440–1699 px the bundle, site and scenario selectors were squeezed to ~100 px (narrower than at 1280 px) by the breadcrumb, which repeats the stage title | defect | **fixed**: breadcrumb hidden below 1700 px; selectors now 170/180/180 px at 1440 (test P6) |
| 2 | Board labels give direction; app labels gave margin only | defect (directive P5) | **fixed**: 3D sight labels now carry azimuth and elevation from the bundle (test P5) |
| 3 | Near the instrument (1024–1280 px) a sight label ran under the panel | defect | **fixed**: labels flip to the left of their anchor (test P6) |
| 4 | Board has a left icon rail; the app puts the views in one labelled row under the stage | deviation | labelled buttons are clearer than unlabelled icons; the row stays one line at 1280 and 1440 (checked) |
| 5 | Board's terrain is a Blender render with long grazing shadows; the app's real-time approach view is brighter, with a large sunlit slope in the upper left | deviation for now | real-time shading belongs to session A (`TerrainSurface.tsx`, not edited by Penumbra); the Blender hero render exists separately |

Also added: a **Reset view** button (↺) that re-frames the current view after orbiting.

## Page 17 · Sky and horizon

| # | Difference | Kind | Action |
|---|---|---|---|
| 1 | Board leads with a polar horizon wheel; the app had only the unrolled horizon | defect | **fixed**: new `HorizonWheel` (north up, clockwise, linear elevation radius stated on screen), left column like the board |
| 2 | Board draws the Sun and Earth tracks over the whole window | defect | **fixed** in the wheel; blocked samples marked in red |
| 3 | Board has a Ridge of Record card and "Longest Sun gap 19.4 h" | already present | ridge list in the instrument; failures list "Sun … 19 samples"; metrics 19.4 h |
| 4 | Board's unrolled horizon exaggerates elevation ×20; the app plots true degrees | deviation | true scale keeps the margin bars honest |
| 5 | App includes the optional Cesium global Moon box in this section | deviation | optional, clearly labelled "context only"; not in the board |

## Page 18 · Decision

| # | Difference | Kind | Action |
|---|---|---|---|
| 1 | Directive: separate the three heights (meets requirements / Sun 100 % on all / agreement) | defect | **fixed**: "three heights" row from the sidecar; the 1 m column is now "Lowest height meeting the team requirements" (test P7) |
| 2 | Card headline named 1.75 m but its figures were 1 m only | defect | **fixed**: card adds "100 % · Sun, 1.75 m, on all 20 (Certainty Height)" |
| 3 | Coverage was on the card's fine print, not next to the conclusion | defect | **fixed**: coverage line with the < 50 % warning right under the card headline, and in the Certainty Height verdict |
| 4 | Board's hero is an eleven-region table (Sun % across 20 maps per region) | data | no all-region sidecar exists in `web/public`; the app shows one site honestly. Open: needs an all-region batch sidecar |
| 5 | Board has "Copy link" and "Export PDF"; the app has "Print / save PDF" (the card prints alone) | deviation | shareable links now exist through session A's URL state; Print covers PDF (test P13) |

## Page 19 · Evidence

| # | Difference | Kind | Action |
|---|---|---|---|
| 1 | Board opens with a numbered pipeline (terrain → ephemeris → horizon → batch → store) | defect | **fixed**: "How each number was made", five lines from the bundle and sidecar |
| 2 | Board has a "Not validated yet" box | defect | **fixed**: lists the open gate by name plus the solver-of-record and geometric-only limits |
| 3 | Directive P9 asks for files, checksums, solver, schema, conventions, sampling, realizations, limitations and reproduction | defect | **fixed**: "Dataset record" with five disclosure sections, raw-data download links (test P8/P9) |
| 4 | Board shows a PGDA 69 correlation table (0.787 …) and "reproduced on four machines" | data | those results are in project docs, not in any file the viewer loads; not drawn |
| 5 | Board's left half is an overhead DEM render; the app shows the PGDA 69 polar reference map | deviation | the map is real NASA data with a reference-product label |

## Page 13 · Scientific charts

| # | Board chart | App | Kind |
|---|---|---|---|
| 1 | One dot per terrain map (20 dots) | min–max range bars with nominal tick | data: the sidecar stores min/max/nominal, not per-realization values |
| 2 | Certainty Height curve | present (sampled heights only, connecting line labelled as a guide) | match |
| 3 | Eleven regions at 1 m | not present | data (same as page 18 #4) |
| 4 | Coverage donut 34.1 / 58.5 % | coverage gauge with the same numbers and definitions | deviation (form only) |
| 5 | Margin ribbon (marked MOCKUP SHAPE on the board) | real per-sample bundle margins, clickable | match, with real data |

## Page 20 · Responsive

| # | Difference | Kind | Action |
|---|---|---|---|
| 1 | Under 640 px the board puts the views in a bottom tab bar | defect | **fixed**: Explore / Decision / Evidence form a fixed bottom bar (44 px targets); the tall header no longer sticks |
| 2 | At 390 px the light tag, the title meta line and the sight labels overlapped | defect | **fixed**: light tag to the bottom of the stage, meta line hidden, labels reduced to state + margin (test P6) |
| 3 | At 390 px the time-bar heading collided with "Sample table · 337 rows" | defect | **fixed**: the toggle wraps under the heading |
| 4 | Board replaces 3D with a still on phones | deviation | 3D kept; phone performance not measured (PERFORMANCE_REPORT) |
| 5 | Board shows tablet as a bottom sheet | deviation | the instrument stacks under the stage; no overlap at 1024 × 768 (checked) |

Checked sizes:
- 1440×900, 1512×982, 1920×1080, 1280×800, 1024×768 and 390×844, on Explore and Decision.
- No horizontal overflow at any size.
- No instrument/title or instrument/view-row overlap, except at 390 px, where the stacked view row now sits below the instrument.

## Score (rubric: 1–5 per criterion, after the fixes)

| Screen | Fidelity to board | Hierarchy | Legibility | Scientific honesty | Responsive | Notes |
|---|---|---|---|---|---|---|
| Explorer (16) | 3 | 4 | 4 | 5 | 4 | real-time terrain look is the gap |
| Sky (17) | 4 | 4 | 4 | 5 | 4 | wheel new |
| Decision (18) | 3 | 5 | 4 | 5 | 4 | eleven-region view needs data |
| Evidence (19) | 4 | 4 | 4 | 5 | 4 | |
| Charts (13) | 3 | 4 | 4 | 5 | 4 | per-map dots need data |
| Responsive (20) | 4 | 4 | 4 | 5 | 4 | |

The scores are Penumbra's own judgement and were not reviewed by anyone else.

## Change log
- 15 Nov 2026 02:00 EST (Penumbra session): created.
