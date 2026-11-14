# POLARIS X · web viewer (b-experience)

React + TypeScript + Vite viewer for **science-bundle-v2** (`POLARIS-X5D-v2`). It reads bundles and displays them. It does
**not** compute skylines, visibility, margins or metrics; see `docs/VIEWER_BUNDLE_CONTRACT.md`.

The legacy app in `../app/` is untouched and still runs on its own.

## Run

```bash
cd web
npm install
npm run dev        # http://localhost:5174  (copies bundles into public/bundles first)
```

`npm run sync-bundles` lists, in this order: `../data/bundles/*.json` (science branch; `fixture.json` first),
`../app/data/polaris-source-*-v2.json` (Codex source cases), and `public/bundles/demo-fixture.json` (DEMO).
You can also open any bundle file from disk with **Open file…**. `?bundle=<file>` in the URL picks one.

## What you see

- One store (UTC time, site, scenario) drives every panel.
- Horizon chart: bundle skyline vs Sun/Earth az/el, with the bundle margin drawn as a bar.
- Visibility strips: Sun, Earth, both, one cell per bundle sample. Click to seek.
- Metrics and constraints: current margins, plus each scenario metric with its limit, margin and PASS/FAIL.
- Failures: click one (or its red marker in 3D) to open the cross-section from the bundle's profile and critical cell.
- Local 3D: the bundle DEM at 1:1 vertical scale, the observer mast, and Sun/Earth rays clipped at the bundle's first-hit
  distance.
- Global Moon (optional): Cesium ion asset 2684829 on `Ellipsoid.MOON`. The token is typed at runtime and held in memory
  only. Any failure is shown and nothing else breaks.
- Provenance drawer: sources, SHA-256 of the loaded bytes, DEM crop and file hashes, Horizons records, gates and the status
  badge: **DEMO**, **SOURCE-BASED UNVALIDATED** or **VALIDATED**.

## Test

```bash
npm test            # Vitest unit tests (sampling, frame, validation, store)
npx playwright install chromium   # once, on a new machine
npm run e2e         # builds, serves on :4173, runs Playwright, writes docs/screenshots/*.png
```

## DEMO fixture

`public/bundles/demo-fixture.json` is synthetic terrain and an invented sky. Regenerate it with `npm run demo-fixture`.
It is always labelled DEMO: a banner, the badge, and `[DEMO]` in the bundle list.

## Use of AI

This viewer was written by Claude (Anthropic) under the team's direction; commits carry a `Co-Authored-By: Claude` line.
