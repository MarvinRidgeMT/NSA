# POLARIS X — 5D Lunar Digital Twin

**Runnable local prototype.** No npm install, GitHub, accounts, separate backend, or connection to another Mac is required to launch the *demonstration-mode* application. Its default terrain is synthetic and its default Sun/Earth direction model is a pedagogical analytic approximation. **Do not present synthetic outputs as NASA or JPL observations.**

## Launch on macOS

1. Unzip the project and open Terminal.
2. Type `cd ~/Downloads/POLARIS-X5D` (adjust path if needed).
3. Run `./run.command` (or `bash run.command`).
4. Open <http://localhost:5173> in Chrome. Allow WebGL2 hardware acceleration.
5. If port 5173 is busy: `python3 -m http.server 5174` and open <http://localhost:5174>.

You can also use `npm test` (Node 22+ recommended). No runtime packages are installed.

## What works now

- WebGL2-rendered procedural global Moon and local 3D terrain with orbit/zoom controls; selectable reference sites.
- A time axis with play/pause, speed, start time, 24–336-hour duration and timeline scrubbing.
- Sun and Earth apparent azimuth/elevation from pedagogical analytic mode or **imported** JPL Horizons samples.
- 360-direction local horizon solver with terrain-height sampling, Moon curvature approximation and observer-height changes.
- Derived geometric solar and Earth access fractions, longest interruption times, joint-visibility timeline, obstruction and angular margins.
- Adjustable lander offset (east/north), observer height, terrain perturbation stress scenario and user-selected mission thresholds.
- Nine scenario comparisons, local reproducibility, data provenance and downloadable JSON report.
- Import of a NASA/JPL science bundle; optional Cesium Moon 3D Tiles with a personal Cesium ion token.

The **5D** terminology denotes latitude, longitude, elevation, time, and a scenario/uncertainty control. The last is an additional decision parameter, not a physical spatial dimension.

## Upgrade to NASA terrain and JPL Horizons for local scientific study

The included `scripts/prepare_science.py` retrieves a small crop from the NASA PGDA product 90 *LOLA south-polar 80m cloud-optimized GeoTIFF* using HTTP range reads (when supported), then fetches apparent azimuth/elevation for Sun and Earth using separate JPL Horizons API requests for the Moon site.

On the Mac in Terminal:

```bash
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install numpy rasterio requests
python3 scripts/prepare_science.py --sites connecting shackleton --pixels 401 --days 14
```

If GDAL cannot remote-read the GeoTIFF, download `LDEM_80S_80MPP_ADJ.TIF` yourself from <https://pgda.gsfc.nasa.gov/products/90> and run:

```bash
python3 scripts/prepare_science.py --sites connecting shackleton --dem-file ~/Downloads/LDEM_80S_80MPP_ADJ.TIF
```

Use the **Import NASA/JPL science bundle** control to open `data/nasa-jpl-science-bundle.json`. Nothing is silently substituted if data acquisition fails. Network access is needed for the one-time data preparation.

**Scientific caution:** NASA PGDA product 90 describes MOON_ME / DE421 polar stereo. JPL Horizons uses its lunar observer frame; a complete solution must verify frame conventions, vertical datum, longitude convention, azimuth bearing and sample timing against independent references. Local 80m cropping omits some distant horizon features; a regional multi-scale skyline will be needed. No claim of flight accuracy is made from importing data.

## Optional Cesium Moon globe

Choose **Enable Cesium Moon terrain**, paste your personal token from <https://ion.cesium.com/tokens>, and activate. The Cesium Moon tileset is asset ID `2684829`. Its south polar tiles can reach approximately 5m resolution according to Cesium. This requires an online browser, asset access and a Cesium ion token. It replaces only the visual scene; numerical horizon analysis still uses the imported DEM. Tokens are not saved to disk.

## Verified and not verified

**Tested in this package:** Node-based calculation tests including site projection, bilinear sampling, observer-height monotonicity, horizon interpolation, time integration, schema rejection, and JPL sample interpolation. Automated browser smoke testing could not complete in the build environment because its browser administrator blocks local URLs. Launch on your Mac and verify the GPU scene and user controls.

**Not independently verified:** alignment of NASA raster projection and JPL local frame, comparison against authoritative shadow imagery, sub-hour horizon crossings, far-ridge occlusion, uncertainty calibration, energy budget, DSN links, or mission safety. This is a research/education prototype, not a NASA-validated mission planning system.

## Source credits

- NASA PGDA LOLA south pole elevation / Barker et al. (2023): <https://pgda.gsfc.nasa.gov/products/90>
- JPL Horizons API: <https://ssd-api.jpl.nasa.gov/doc/horizons.html>
- Cesium Moon (NASA LRO based 3D Tiles): <https://cesium.com/platform/cesium-ion/content/cesium-moon/>
- NASA SVS Moon model and visualization resources: <https://svs.gsfc.nasa.gov/14959/>

Historic study-site coordinates are drawn from the supplied POLARIS planning documents, which recommend cross-verification with NASA Lunar Surface Data Book Rev. A. These are research locations, **not** current selected Artemis touchdown coordinates.

## Competition

Review the NASA Space Apps 2026 official start-time, source attribution, AI disclosure, and submission rules. Work begun before the official implementation window may be ineligible for submission. Distinguish this prototype from independently created event work.
