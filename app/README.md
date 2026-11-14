# POLARIS X — 5D Lunar Mission Resilience Studio

**Version 0.2 PRO | Local Mac application with a transparent scientific core.**

This is a substantial upgrade of the original prototype. It has an interactive WebGL2 local Moon terrain scene, dynamic direction-aware terrain shading, 3D Sun/Earth rays, three cameras, terrain overlays, a synchronized clock, a physical obstruction cross-section, four-site comparisons, nine uncertainty scenarios, and reproducible tests. Its standalone **software-rendering fallback** remains usable even if WebGL2 is blocked.

**Crucial scientific caveat:** It launches in DEMONSTRATION mode with synthetic terrain and approximate analytic sky directions. DEMO results are **not NASA measurements**. The included `scripts/prepare_science.py` is the upgrade path to actual NASA LOLA elevation crops and JPL Horizons sky geometry. Alignment of the source raster coordinates and lunar observer frame is still subject to independent validation. Do not represent this app as NASA mission-ready software.

## Fastest way to launch on your M5 Pro MacBook

1. Unzip `POLARIS-X5D-PRO-Mac.zip`.
2. Open Terminal and run:

```bash
cd ~/Downloads/POLARIS-X5D-PRO
./run.command
```

If macOS blocks direct execution, run `bash run.command`. Your default browser opens the local app. It runs entirely from the ZIP's files with **no npm packages** and no API token for the demo.

You can also use `npm test` to run the science test suite, or `npm start` to use port 5173 explicitly.

**Browser requirement:** WebGL2 and hardware acceleration for the main 3D renderer. The program automatically falls back to an interactive Canvas2D projected DEM if WebGL2 is not usable. Do not mistake the fallback's projection for the full GPU-rendered view.

## What is new in PRO

| Feature | What actually works |
|---|---|
| **High-contrast 3D terrain view** | WebGL2 DEM mesh, elevation-aware material and directional light from the computed Sun position |
| **DEM-based shadow preview** | Samples terrain toward the Sun for displayed surface shading, re-evaluated as time advances; approximate point-source, finite-range model |
| **3D line-of-sight rays** | Obstruction rays stop at the first sampled blocking terrain; rays and observer markers track the simulation clock |
| **Camera / visualization** | Orbit, overhead and low-horizon presets; natural regolith, elevation and illumination modes; show/hide rays |
| **Physical ray-trace cross-section** | Terrain and Sun/Earth ray height versus distance, highlighting first modeled obstruction |
| **Four-site comparison** | Connecting Ridge, Shackleton Rim, Peak Near Shackleton and de Gerlache Rim in the same mission window |
| **Resilience dashboard** | Nine defined scenarios, plots, feasibility margins, and honest source-coverage flags |
| **Data integrity improvements** | Angular sky vectors are no longer overwritten by Boolean sunlight flags; JPL sample coverage never silently falls back to approximate sky |
| **Screenshot + report** | Export the current scene image and a JSON report of the model inputs/results |
| **Optional Cesium Moon** | Connect lunar 3D Tiles asset 2684829 with your ion token. Geographic site marker and model Sun/Earth direction rays are added when possible. |
| **Blender companion** | Open the provided illustrative GLB preview, or use `blender/build_lunar_scene.py` to produce `.blend` and `.glb` from an imported DEM bundle |

The **fifth dimension** is a controllable uncertainty/scenario axis: not a physical fourth spatial axis and not a calibrated success probability.

## Connecting actual NASA / JPL data

The local web app does not make network requests for scientific data on its own. Make one NASA/JPL source bundle using the included Python pipeline:

```bash
cd ~/Downloads/POLARIS-X5D-PRO
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install numpy rasterio requests
python3 scripts/prepare_science.py --sites connecting shackleton --pixels 401 --days 14
```

If `rasterio` lacks Python 3.14 wheels on your Mac, use a separate Homebrew Python 3.13 environment instead of replacing your system Python.

The script attempts to read an ~32-km NASA 80 m regional south-pole DEM crop remotely, with a local-file fallback. If remote access fails, download the 80-m COG (`LDEM_80S_80MPP_ADJ.TIF`) from [NASA PGDA product 90](https://pgda.gsfc.nasa.gov/products/90) and specify `--dem-file /path/to/file.TIF`.

Select **Import NASA/JPL science bundle** in the app and choose `data/nasa-jpl-science-bundle.json`. This generated file can be large; it is deliberately not bundled with the ZIP and is not cached online. Invalid or out-of-period JPL data will be explicitly rejected/marked unavailable, rather than silently replaced with demonstration sky.

**Unresolved validation work:** Confirm polar stereographic projection orientation, MOON_ME/DE421 vs the JPL lunar observer frame, vertical datum, azimuth sign, the observer site position, raster nodata, horizon extent, ephemeris parsing, and independent illumination checks. A 32-km crop does *not* capture every distant ridge. All observer tests use a finite footprint, and only Sun/Earth centers are checked. The thermal model, DSN link budget and certified lander power model are not included.

## High-resolution lunar rendering with Cesium Moon

From the web app, click **Enable Cesium Moon terrain**, and enter a personal Cesium ion token from <https://ion.cesium.com/tokens>. Cesium Moon supplies global NASA LRO-derived 3D Tiles (asset `2684829`), with finer coverage near the poles. The local preview is retained as a fallback. Cesium visual terrain and NASA LOLA numerical terrain are **separate sources**, and cross-aligning them is a future validation task. Never imply that visual pixels are the DEM used in the science engine.

Cesium uses an external CDN and online token-based asset access; these were not end-to-end verified in this restricted browser environment.

## Blender: high-fidelity art and scientific reference

`assets/ILLUSTRATIVE_terrain_preview.glb` is a genuine GLB triangle mesh of the deterministic synthetic demonstration terrain, made solely to allow immediate Blender inspection. It is **not an actual lunar map**.

Once a NASA/JPL bundle exists, use:

```bash
/Applications/Blender.app/Contents/MacOS/Blender --background \
  --python blender/build_lunar_scene.py -- \
  --bundle data/nasa-jpl-science-bundle.json --site connecting \
  --output blender/output
```

Blender scene output uses 1 m per scene unit, physically scaled DEM vertices, adjustable lighting, cinematic camera, and a clearly illustrative observer marker. The script is Python-syntax-checked but **not run here** because the current build environment has no Blender. The exported `.glb` geometry is visual only; scientific computations continue to read raster values.

See [`docs/TOOLCHAIN.md`](docs/TOOLCHAIN.md) for the division of responsibilities across Cesium, Blender, Claude Code, local Ollama/Qwen, NASA and optional Tripo GLB generation tools.

## Tests and evidence

Run:

```bash
npm test
```

The included **13 automated tests** cover: projection pole, bilinear sampling, increasing observer height, horizon wraparound, scenario evaluation, schema rejection, interpolation, solar-vector regression, synthetic ridge obstruction, scenario baseline fidelity, strict ephemeris coverage, time-window events, and four-site mode labeling.

During this release, a local in-memory browser harness exercised the dashboard and switched time, site, color mode, camera, and target cross-section with **no page JavaScript errors**. WebGL2 creation is prevented in that browser environment, so the fallback renderer was browser-checked; GPU WebGL2 and Cesium live terrain must still be checked on your Mac. `docs/render-test.png` is a screenshot of the fallback in the restricted testing browser, not evidence of a hardware-rendered final scene.

## Reference & competition provenance

- [NASA PGDA 80m south-pole DEM](https://pgda.gsfc.nasa.gov/products/90)
- [NASA PGDA 5m DEM clones / elevation uncertainty](https://pgda.gsfc.nasa.gov/products/78)
- [JPL Horizons API](https://ssd-api.jpl.nasa.gov/doc/horizons.html)
- [Cesium Moon official overview](https://cesium.com/platform/cesium-ion/content/cesium-moon/)
- [NASA SVS Moon GLBs](https://svs.gsfc.nasa.gov/14959/)

The **provided POLARIS X technical blueprint** is the conceptual basis of this prototype. Follow the current NASA Space Apps 2026 implementation-time, attribution, AI usage and submission rules. If source code is prepared before the permitted start time, it might not qualify as a new competition submission.

> POLARIS X is an educational decision-support research prototype, not flight software or a NASA endorsement.
