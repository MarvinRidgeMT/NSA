# POLARIS X browser application

This local WebGL2 application visualizes terrain-aware Sun/Earth target-centre visibility over time and recomputes deterministic fifth-dimension scenarios. Its startup cache contains source-backed NASA PGDA regional terrain and JPL Horizons angles for Connecting Ridge/Site01 and Shackleton Rim/Site04.

**Status: source-based but independently unvalidated.** Peak Near Shackleton and de Gerlache use clearly labelled demonstration inputs until source bundles are generated for them.

## Run

```bash
bash run.command
```

The launcher selects an available localhost port. Directly double-clicking `index.html` is also supported: `dist/polaris-file.js` embeds the compact source case and bundles the JavaScript so Chrome does not block the model under `file://`. No npm dependencies are required at runtime. WebGL2 is preferred; an interactive Canvas2D projection is the fallback.

## Data modes

- `data/polaris-offline-source-case.json` is the compact two-site startup case: 401×401 regional 80 m crops and hourly JPL angles for 14 days.
- `data/polaris-source-site01-2026-11-14-v2.json` is the full Site01 case: regional terrain, 5 m nominal terrain, total-Z RMS evidence and clones 001/002/050/100.
- The terrain realization selector recomputes the horizon and visibility when a full bundle is imported.
- Optional Cesium Moon asset 2684829 is visual context only. It requires the user's ion token and is not sampled by the numerical engine.

The fifth dimension is a named terrain/mission scenario. It is not another spatial axis or a calibrated probability.

The local WebGL model renders regional DEMs at 257² mesh resolution and 5 m local layers at up to 301². A circular source footprint, smooth normals, low-angle regolith lighting, cinematic camera motion, a schematic landing node and target rays provide spatial context. Display relief is explicitly exaggerated 2.4×; every numerical horizon calculation continues to use source elevations in metres.

## Numerical model

The engine samples a 360-bin terrain horizon using bilinear DEM elevations and exact spherical tangent-plane curvature for a `1,737,400 m` Moon radius. It compares JPL airless apparent Sun/Earth centre elevation with that finite terrain skyline. Results do not include partial disks, long-range terrain outside the crop, communications link budgets, DSN schedules, thermal balance or power-system performance.

## Tests

```bash
npm test
python3 tests/browser_smoke.py --screenshot
```

The Node suite currently has 15 science regressions. The Chrome smoke test checks localhost and direct-file WebGL models, the two-site source cache, full Site01 import, six terrain choices, clone recomputation, mission/analysis drawers and browser errors. Its verified screenshots are `docs/browser-source-case.png` and `docs/browser-file-launch.png`.

Rebuild the direct-file runtime after changing JavaScript or cached data:

```bash
npm install
npm run build:file
```

Use the project-root `bash test_all.command --full` for pipeline, schema, Blender and artifact verification.
