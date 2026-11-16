# POLARIS X browser application

This local WebGL2 application visualizes terrain-aware Sun/Earth target-centre visibility over time and recomputes deterministic fifth-dimension scenarios. Its startup cache contains source-backed NASA PGDA regional terrain and JPL Horizons angles for Connecting Ridge/Site01 and Shackleton Rim/Site04.

**Status: source-based but independently unvalidated.** Peak Near Shackleton and de Gerlache use clearly labelled demonstration inputs until source bundles are generated for them.

## Run

```bash
bash run.command
```

The launcher selects an available localhost port. Directly double-clicking `index.html` is also supported: `dist/polaris-file.js` embeds the full runtime source case, Three.js renderer and NASA Moon GLB so Chrome does not block the model under `file://`. No npm dependencies are required at runtime. WebGL2 is preferred; an interactive Canvas2D projection is the fallback.

## Data modes

- `data/polaris-runtime-source-case.json` is the startup case: Site01's 401×401 5 m/RMS/clone layers, two 401×401 regional 80 m crops and hourly JPL angles for 14 days.
- `data/polaris-offline-source-case.json` is retained as the older compact two-site cache.
- `data/polaris-source-site01-2026-11-14-v2.json` is the full Site01 case: regional terrain, 5 m nominal terrain, total-Z RMS evidence and clones 001/002/050/100.
- The terrain realization selector recomputes the horizon and visibility when a full bundle is imported.
- `assets/nasa/NASA_SVS_Moon_NASA_LRO_8k_Topo_Small.glb` is the embedded official 8K LRO color-plus-height model (about 2.02M vertices / 1.02M triangles). The compact color-only GLB is retained as a fallback. Optional Cesium Moon asset 2684829 is an online visual alternative requiring the user's ion token. None is sampled by the numerical engine.

The fifth dimension is a named terrain/mission scenario. It is not another spatial axis or a calibrated probability.

The local Three.js model renders the full 401² 5 m surface over a 241² regional 80 m context, about 435,000 triangles total. Coverage lines, a presentation-only LOD seam blend, smooth normals, low-angle regolith lighting, cinematic cameras, a schematic landing node and frame-correct target rays provide spatial context. Display relief is explicitly exaggerated 2.38×; every numerical horizon calculation continues to use source elevations in metres without the visual seam treatment.

## Numerical model

The engine samples a 360-bin terrain horizon using bilinear DEM elevations and exact spherical tangent-plane curvature for a `1,737,400 m` Moon radius. Local ENU azimuths and landing offsets are rotated into the south-polar stereographic DEM grid before sampling. It compares JPL airless apparent Sun/Earth centre elevation with that finite terrain skyline. Results do not include partial disks, long-range terrain outside the crop, communications link budgets, DSN schedules, thermal balance or power-system performance.

## Tests

```bash
npm test
python3 tests/browser_smoke.py --screenshot
```

The Node suite currently has 18 science regressions. The Chrome smoke test checks localhost and direct-file WebGL models, the full startup cache, Site01 import, six terrain choices, clone recomputation, the embedded global Moon, mission/analysis drawers and browser errors. Its verified screenshots are `docs/browser-source-case.png`, `docs/browser-global-moon.png` and `docs/browser-file-launch.png`.

Rebuild the direct-file runtime after changing JavaScript or cached data:

```bash
npm install
npm run build:file
```

Use the project-root `bash test_all.command --full` for pipeline, schema, Blender and artifact verification.

## 14 Nov 17:03 UTC additions

- Camera presets `REGIONAL` (80 m context) and `OBSTRUCTION` (side-on close-up of the first sampled terrain hit of a blocked ray). All presets fly with an eased, log-distance camera move; drag or Escape cancels. Global → local is a two-stage cancelable flight. Reduced-motion users get instant cuts.
- Time console: `⇤` / `⇥` (keys `[` / `]`) jump to the previous/next Sun or Earth visibility transition and name the two bracketing hourly samples; the crossing time is not refined.
- `window.__POLARIS_SCENE__.getPerf()` returns measured frame time (mean/p95/max), draw calls, triangles and JS heap for QA; it holds no credentials.

## Simple UI layer (14 Nov 2026, 17:55 EST)
The default layout follows NASA's Eyes / Moon Trek pattern: full-screen 3D, place name top-left, a **View** card on the
right (camera, surface layer, vertical scale, target rays), **Settings / Charts / Rotate** on the left, and a summary card
plus the time bar at the bottom. It is a CSS layer scoped to `.simple-ui` on `#app`; remove the class to restore the
previous layout. No science or data changed. Screenshots: `docs/visual-audit/simple-ui-*.png`.
