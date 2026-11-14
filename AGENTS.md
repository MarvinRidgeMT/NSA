# POLARIS X — Codex development instructions

## Objective
Build a scientifically transparent, interactive 5D lunar digital twin on Apple Silicon. Treat dimensions 1–3 as local position (east, north, elevation), dimension 4 as UTC time, and dimension 5 as selected uncertainty/mission scenario; never call the scenario axis a physical spatial dimension.

## Project entrypoints
- `app/`: Existing POLARIS X PRO interactive web application (run `bash app/run.command` from `app/`).
- `blender/build_lunar_science_scene.py`: Blender 4.5+/5.x builder. Run `bash run_blender.command --demo` for a visibly labeled synthetic DEM, or `--bundle app/data/nasa-jpl-science-bundle.json --site connecting` for real inputs.
- `blender/polaris_geometry.py`: Pure Python geometry (no bpy). Unit-test this first.
- `app/scripts/prepare_science.py`: Candidate NASA LOLA DEM / JPL Horizons data ingest. Verify projection/orientation and Horizons output against independent references; do not treat the script as validated astronomy.

## Non-negotiable scientific invariants
1. NEVER replace a missing NASA DEM with invented elevations and then label the output NASA.
2. NEVER infer physical Sun or Earth position from cinematic Blender lamps.
3. Keep azimuth convention: 0° north, 90° east, in a documented local ENU frame. Verify compatibility with JPL surface observer coordinates.
4. Z values are metres; DEM source frame must be documented. Distinguish Moon radius and vertical datum; do not silently apply Earth geospatial transforms.
5. Terrain visibility from finite DEM rays is only local geometric visibility. It is not certified illumination/power or DSN telecommunications availability.
6. Stress-test grids are deterministic alternatives, not probabilistically calibrated risk assessments.
7. Make the 3D time frame and science chart refer to the same timestamp. Do not extrapolate outside real ephemeris samples.
8. Clearly disclose NASA/JPL source links, dates, DEM resolution, horizon reach, uncertainty method and limitations.

## Implementation priorities (in order)
- Verify Blender demo scene builds with Blender CLI and exports a nonempty `.blend` and `.glb`.
- Render at least three animation frames (start/middle/end) and inspect both scene geometry and visibility/lighting correspondence.
- Add reproducible NASA DEM file ingestion and JPL UTC samples; validate coordinate frame, longitude signs, azimuth bearing, pixel indexing and nodata.
- Implement ray-based horizon obstruction and compare a flat-horizon control against terrain-aware results.
- Add observer position/height perturbations, mission-window and risk-band diagrams supported by recomputed data.
- Integrate 3D output with web app's time slider using a JSON contract; Blender is for authoring/pre-rendering, Cesium/WebGL for web-native navigation.
- Improve accessibility, camera controls and frame-rate only AFTER numerical checks and data provenance pass.

## Tests/acceptance
- Run `python3 -m unittest discover -s blender -p 'test_*.py' -v`.
- Run `cd app && npm test`.
- Ensure **all** rendered metrics are declared DEMO or source-backed plus explicitly unvalidated until independent checks are complete.
- Do not claim NASA accuracy based on an attractive render or an ML/AI model's explanation.

## How Codex should work
First inspect the code and run the tests. Implement one small validated step per change. Create a reproducible Blender command and an automated regression test for each scientific issue found. Use `bpy` only inside Blender's bundled Python. Do not introduce paid APIs or request credentials without user approval. Avoid modifying unrelated files on the user's Mac.
