# POLARIS X v2 — gates before any public link (prompt §7)

Measured by session T1 on 17 Nov 2026 (EST night of 16→17 Nov), branch `claude/v2-t1-nasa-features-ceef5e` (web app as
on `feature/v2-whole-moon` at 13551d0; T1 changed no UI). Raw results: `docs/v2/gates/*.json` and screenshots.
Machine: MacBook Pro Mac17,9, Apple M5 Pro, 120 Hz built-in display + external QHD, on AC power, Low Power Mode off,
Google Chrome 157.0.8103.79 (ANGLE Metal), viewport 1512 × 982 @2x.

## Summary

| Gate | Rule | Result | Numbers |
|---|---|---|---|
| p95 frame, globe | ≤ 16 ms | **PASS** | uncapped 2.7 ms (idle 2.6 / orbit 2.7; max 29.8 ms); capped 7.8 ms |
| p95 frame, region | ≤ 16 ms | **PASS** (p95), with stalls | uncapped 4.3 ms (idle 4.3 / orbit 3.2 / playback 3.5) but single frames of **1,809 ms** (idle) and 209 ms (orbit); capped 14.7 ms |
| p95 frame, 5 m | ≤ 16 ms | **PASS** (p95), with stalls | 79 PGDA 78 LOD tiles drawn, finest 5 m; uncapped 3.8 ms (idle 3.8 / orbit 3.1), max **698 ms** during orbit; capped 7.7 ms |
| Cold start → first globe frame | ≤ 5 s | **PASS** | 3,131 ms (uncapped run), 2,142 ms (capped run); globe button ready at 963 / 1,030 ms |
| Traceability, rendered numbers | 0 failed | **PASS** | `traceability.spec.ts` on :4221: 544 scanned, 0 failed, 13 bundles (453 SOURCE-BASED) |
| Traceability, every new number | 0 failed | **PASS** | `label_audit.py`: 2,256 exported numbers (2 sites, global grid, Mercury, any-site Site04) read back from their sources; 0 failed |
| Label audit | 0 violations | **PASS** | 41 API results + site list + tool spec + OpenAPI labelled; wording scan 0 hits in T1 text, Decision Card PDFs, decision summaries and `web/src` |
| Accessibility | 0 serious/critical | **FAIL → PASS after fixes (§8)** | axe-core 4.14.0: **9** serious rule hits over 5 views (lite scan: 0 serious, 1 moderate — the lite scan misses them) |
| Mobile layout 390 px | no horizontal scroll, controls reachable, no squeezed headings | **FAIL (3 of 5 views) → PASS 5/5 after fixes (§8)** | Explore and Explore+globe pass; Story, Decision, Evidence fail (below) |

## 1. Frame time (`web/scripts/gates/perf_gates.mjs`)

Method (fixed before the run, docs/v2/PHASE_7_T1_PLAN.md §3): same as `web/scripts/perf_mac.mjs` — headed Chrome window,
visible and focused (`document.visibilityState = visible`, `hasFocus() = true` recorded per measurement), vite preview
of `web/dist`, frame time = `requestAnimationFrame` interval. Per level: 4 s idle + 5 s orbit drag with real mouse
events (+ 5 s playback at region). **Deciding run = `--uncapped`** (vsync and frame-rate limit off, so an interval is
the frame cost, not the display period); the vsync-capped run is context. Levels: globe = `GlobalMoon` (NASA SVS GLB,
VISUAL CONTEXT), region = Explore 3D scene with the terrain context, camera "context"; 5 m = `?lod=1` near-field LOD on
Site04 RoI 3, camera "approach", after all tiles finished streaming.

- Run-to-run spread: a first uncapped run the same night gave region p95 8.3 ms (max 990 ms idle, 483 ms orbit),
  5 m p95 2.3 ms (max 1,169 ms idle), globe p95 2.9 ms, cold start 3,718 ms. All four rules passed in both runs.
- Under vsync on the 120 Hz display, globe and 5 m run at the display rate (p95 7.7–7.8 ms) but the **region view runs at
  about half rate** (p95 14.6–14.7 ms, ~80 fps), even though its uncapped frame cost is ~3–4 ms: a presentation/compositing
  cost the uncapped run hides. Still within 16 ms.
- **Claude browser pane, hidden:** 0 animation frames in 6 s (`visibilityState` still "visible"); frame time cannot be
  measured there (`perf-claude-pane-hidden-2026-11-17.json`). The gate numbers above are from the separate Chrome window.
- The 5 m LOD tiles are git-ignored (`web/public/context/lod/`); for this run they were copied from another local worktree.

## 2. Cold start
Fresh browser context (empty HTTP cache), `performance.now()` from navigation start to the second rAF after
`[data-testid=global-moon][data-loaded=true]`. The app opens in the terrain view, so the path includes clicking "Moon"
as soon as the button exists (~1.0 s). 3.1 s / 2.1 s ≤ 5 s. Not measured: a cold OS-level browser launch.

## 3. Traceability and labels (`web/scripts/gates/label_audit.py`)
Rebuilds the exports, then (1) reads every number in `data/exports/**/numbers.json` back from its source file by JSON
path and checks the source SHA-256; (2) checks labels and the geometric-only disclaimer on API results (41 cached sites
sampled across groups), the site list, the tool spec (AI-GENERATED, "not a probability", "no AI planner") and the
OpenAPI description; (3) scans wording: probability language for k of N, "equally plausible", unqualified
"validated"/"certified", NASA-accuracy claims and the retired phrases of `docs/SCIENCE_LABEL_AUDIT.md`, in T1 text, the
Decision Card PDF text, the decision summaries and `web/src` (read only). One reviewed exception: `web/src/store/surface.ts`
"file (validated)" (a JSON file passed its schema check). Self-test: the patterns flag "95 % probability", "the site is
validated", "NASA-accurate", "certified power" and pass "not a probability", "Not validated yet".
The rendered-number scan is the existing `web/tests/e2e/traceability.spec.ts` (T1 adds no rendered numbers).

## 4. Accessibility (`web/scripts/gates/a11y_mobile.gate.ts`)
axe-core is **not** in `web/node_modules`. The gate runs axe when `AXE_CORE_PATH` points to a local `axe.min.js`, else a
lite scan (lang, title, alt, accessible names, duplicate ids, one main, canvas text alternative, positive tabindex).
Recorded run: `AXE_CORE_PATH` = an axe-core 4.14.0 copy already on this Mac (another project's `node_modules`; nothing
installed or downloaded), tags wcag2a/aa, 21a/aa, 22aa. Views: story, Explore, Explore + globe, Decision, Evidence.

| View | Serious violations (axe 4.14.0) |
|---|---|
| story | none |
| Explore | `nested-interactive` (`.heading-tape`), `target-size` (`[data-testid=lod-toggle]`) |
| Explore + globe | `nested-interactive` (`.heading-tape`) |
| Decision | `color-contrast` ×4 (`.og-pos` in the position buttons), `definition-list` (`.three-heights`), `label-content-name-mismatch` ×9 (`og-*` position buttons), `nested-interactive` (the 760×230 SVG), `scrollable-region-focusable` (`.decision6d-pareto > .table-scroll`) |
| Evidence | `nested-interactive` (`.polar-overlay`) |
Lite scan: 0 serious; 1 moderate (Evidence: a canvas without a text alternative).

## 5. Mobile 390 px (same file; iPhone-size context 390 × 844 @3x, touch)
Rule: no horizontal page scroll; every visible control inside the viewport, inside a horizontal scroller or brought into
view by focus (skip link); no `h1/h2` laid out in under half the width onto 3+ lines. Recorded, not gating: targets under
24 px (WCAG 2.2 2.5.8) and text under 11 px. Screenshots `docs/v2/gates/mobile-390-*.png`.

| View | Result | Detail |
|---|---|---|
| story | FAIL | third hero button ("How we know…") clipped at the right edge; 1 target < 24 px, 1 text < 11 px |
| Explore | pass | 2 targets < 24 px (skip link 103×12, `lod-toggle` 193×22), 24 text nodes < 11 px |
| Explore + globe | pass | 2 targets < 24 px, 20 text nodes < 11 px |
| Decision | FAIL | h1 "Does this ground keep the light?" squeezed to 104 px (two-column layout kept at 390 px); 14 targets < 24 px (e.g. `cert-mast-*` SVG labels 8×6), 80 text nodes < 11 px |
| Evidence | FAIL | h1 "Receipts, not reassurance" squeezed to 156 px; 34 targets < 24 px (`ridge-row` buttons 12–14 × 18) |

## 6. Failures for T2 (web owner) — not fixed here
1. Decision and Evidence keep a two-column grid at 390 px: single column below ~600 px.
2. Story hero: wrap the three buttons (or stack them) at 390 px.
3. axe `nested-interactive`: `.heading-tape` (Explore), `.polar-overlay` (Evidence), the Decision 760×230 SVG — interactive
   children inside elements that are themselves focusable/clickable.
4. axe `label-content-name-mismatch` + `color-contrast` on the Decision position buttons (`og-*`, `.og-pos`).
5. axe `definition-list` (`.three-heights`: `<dl>` children must be `dt`/`dd`), `scrollable-region-focusable`
   (`.decision6d-pareto > .table-scroll`: add `tabindex=0` + a label), `target-size` (`lod-toggle` 22 px tall).
6. Frame stalls: single frames of 0.5–1.8 s at region and 5 m levels (p95 passes); likely main-thread work on context /
   tile upload — worth a Performance trace.
7. Add `axe-core` as a devDependency so the accessibility gate runs without `AXE_CORE_PATH` (needs the user's OK to install).

## 7. How to rerun
```
cd web && npm run build
node scripts/gates/perf_gates.mjs --uncapped && node scripts/gates/perf_gates.mjs
POLARIS_PLAYWRIGHT_PORT=4221 npx playwright test -c scripts/gates/playwright.gates.config.ts
POLARIS_PLAYWRIGHT_PORT=4221 npx playwright test tests/e2e/traceability.spec.ts
cd .. && .venv/bin/python web/scripts/gates/label_audit.py
```

## 8. Re-measured after the fixes (17 Nov 2026, coordinator) — accessibility PASS, mobile 390 px PASS
Same gate file and command (§7), axe-core 4.14.0 via `AXE_CORE_PATH` (a local copy; nothing installed), vite preview :4221.
Before the fixes, on the current branch: 8 serious axe hits (the `lod-toggle` target-size hit of §4 was already gone) and 3
of 5 views failing at 390 px. After: **0 serious/critical** over the 5 views and **5/5 views pass** at 390 px
(`a11y-axe-2026-11-17.json`, `mobile-2026-11-17.json`, screenshots `mobile-390-{story,decision,evidence}.png` rewritten).

| Failure (§4–§6) | Fix |
|---|---|
| `nested-interactive` `.heading-tape` | `role="img"` + label moved from the whole tape to its visual window; the Focus button sits outside it (`HeadingTape.tsx`) |
| `nested-interactive` `.polar-overlay`, Decision 760×230 SVG | `role="group"` (they contain focusable pins / mast labels), label kept (`PolarMap.tsx`, `CertaintyHeight.tsx`) |
| `label-content-name-mismatch` `og-*` | no `aria-label`; the name is the visible text plus a screen-reader-only detail (`ScenarioTable.tsx`) |
| `color-contrast` `.og-pos` | fill computed as an exact sRGB blend, text black or white by WCAG ratio (≥ 4.58:1 for any fill); `.og-pos` inherits it |
| `definition-list` `.three-heights` | the note moved out of the `<dl>`; both wrapped in the `three-heights` test region |
| `scrollable-region-focusable` Pareto table | `tabIndex=0`, `role="region"`, label |
| Story hero buttons clipped (390 px) | `.story .cta` wraps ≤ 760 px |
| Decision / Evidence h1 squeezed (390 px) | `.page-head` stacks ≤ 760 px (h1 full width) |

Still recorded, not gating: targets under 24 px (skip link 103×12, the Decision mast labels in the SVG, Evidence
`ridge-row` buttons) and text under 11 px; axe's own `target-size` rule reports none serious. Not done: §6.6 frame stalls
(needs a Performance trace), §6.7 `axe-core` as a devDependency (needs your OK to install).
