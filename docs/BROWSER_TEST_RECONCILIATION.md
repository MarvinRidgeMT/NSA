# Browser test reconciliation (Penumbra Apex)

Date: 14 Nov 2026, EST. Suite: `web/tests/e2e/*.spec.ts` (Playwright, Chromium, 1440 × 900, `npm run build && npm run preview`).

## Starting point: 6 failing tests
| Test | Classification | Root cause | Resolution |
|---|---|---|---|
| science-v2.spec.ts (4 tests) | **Real app bug** | They deep-link `?bundle=site01_2026-11-14_14d.json`. That file exists in `public/bundles/` but is not listed in `bundles/index.json`, so `App.tsx` silently loaded a *different* bundle (the hero). A user asking for one site saw another. | `App.tsx`: a deep link to an unlisted plain `name.json` loads exactly that file (or shows the load error); never substitutes. Non-plain names are refused with an error. |
| decision-evidence.spec.ts:64 | Real app bug (same) | Same silent substitution. | Same fix. |
| decision-evidence.spec.ts:91 | Real app bug (same) | Same silent substitution. | Same fix. |
| real-and-fallbacks.spec.ts:11 | **Stale test** | Asserted the JPL Sun azimuth/margin (`sun-az`, `sun-margin`) on Explore; since Penumbra those live in the Decision "Metrics & constraints" panel. | Test reordered: the Explore "not in bundle" checks run first, then it opens Decision and asserts the same values. No assertion removed or loosened. |

## Wording updates in assertions (not weakening)
`decision-evidence.spec.ts` expected the old phrase "alternate terrain maps"; the science-label audit replaced it with "alternate terrain realizations" (see SCIENCE_LABEL_AUDIT.md). The two assertions now expect the new text, with the same specificity (pass count and mast height still interpolated from the sidecar).

## New regression tests (`tests/e2e/apex.spec.ts`, 6 tests)
1. Deep link to a missing bundle → error, no instrument, no substitution; a path-like name is refused.
2. Certainty Height selector: chips equal `sampled_masts_m`; pass counts and "every realization" equal the sidecar at 1.75 m; 1.5 m shows "no"; 10 m switches the scenario select to `mast10`, 1 m back to `baseline`.
3. Ridge of Record: "R3" → Ridge camera, R3 caption, ribbon run outline present, instrument says "Sun blocked by"; Return restores sample and removes the outline.
4. Lighting: on-screen tag says "Light: display"; toggle → "Light: true Sun elevation".
5. Guided demo: 5 scenes, live values from the sidecars (1.75 m, 34.1 %, 20/20), route changes, Esc exits.
6. Decision: source legend, bundle tag, coverage explanation and the "However, only 34.1 %" claim.

## Result
| Run | Result |
|---|---|
| Vitest (`npx vitest run`, merged tree incl. session A's Phase 4/5 files) | 11 files, **89 pass, 1 skipped** |
| Playwright full suite (cloud headless Chrome, SwiftShader) | **41 / 41 pass** (35 existing + 6 new) |
| `tsc --noEmit` (cloud and Mac) | clean |
Playwright was not run on the Mac (the VM has no browser); see PRODUCTION_PARITY.md for the Mac checks.

## Change log
| When (EST) | Who | Change |
|---|---|---|
| 2026-11-14 20:52 | Claude (Penumbra Apex session) | Created. |

## Final visual pass (14 Nov 2026, 21:10–23:00 EST)
- New `tests/e2e/visual-final.spec.ts` (3): sight-line labels equal the bundle margin at sample 0 and at the R3 run, R1 labelled "beyond this crop"; camera row ≤ 40 px high at 1440 and Display/Scientific light labels; Decision hero values equal the sidecar and start in the first screen; details open on click with exact pass counts.
- `apex.spec.ts`: the 1.5 m assertion now checks the exact lowest value from the sidecar (`no · lowest 96.1 %`) instead of a phrase; the "no bundle time series" warning is asserted visible in its own element (stronger than before).
- Session A's new `terrain-context.spec.ts` (7) runs in the suite. Two of its checks failed on the first merged tree because of this pass's layout (control row wider than its box at 1440; mast chips not wrapping at 390 px); the layout was fixed, the tests were not changed. Its globe test needs `public/globe/NASA_SVS_moon_small.glb` (13.8 MB), which was copied from the Mac.
- Totals on the merged tree (final run 22:40–22:51 EST): Vitest 89 pass / 1 skipped; Playwright **51 pass, 1 skipped, 0 failed** of 52 (41 earlier + 3 new + session A's 8). The skip is session A's LROC Site01 layer check, which skips by design until its NAC window download completes.
