# POLARIS X — tools that actually improve the lunar twin

**Scientific authority:** NASA LOLA DEM and error products, JPL Horizons, lunar frame documentation, independent validation. Never use an AI-generated landscape for science calculations.

## Production stack and roles

| Tool | Real contribution | Do not use it for |
|---|---|---|
| **Cesium Moon** | Global, NASA LRO-derived 3D terrain and polar exploration, asset 2684829 | The numeric horizon solver without re-validating coordinates and tile elevations |
| **Python + Rasterio + NumPy** | Crop and validate source DEMs, compute horizon and uncertainty runs | Cinematic rendering |
| **JPL Horizons** | Source-backed Sun/Earth topocentric azimuth/elevation over UTC | Terrain obstacle calculations |
| **Blender** | Cinematic presentation, glTF export, material, lander/observer marker, geometry debugging | Inventing true south-pole elevation or orbital positions |
| **Claude Code** | Independent code review, refactoring, test generation on a local working copy | Replacing reference datasets or bypassing validation |
| **Local Qwen via Ollama** | Reusable offline helper for UI, code summaries and test generation | Numerical mission-authority claims |
| **Tripo 3D via Higgsfield** | Optional stylized lander, antenna, educational equipment GLBs with PBR materials | Geologically accurate terrain or actual mission vehicle geometry |
| **NASA SVS Moon GLB** | Credible visual asset with NASA LRO imagery; good for Blender context | Fine local terrain horizon calculations |

Blender background execution is documented in its official Python API:

```bash
blender --background --python blender/build_lunar_scene.py -- \
 --bundle data/nasa-jpl-science-bundle.json --site connecting --output blender/output
```

If `blender` is not on `PATH`, on macOS the executable is often:

```
/Applications/Blender.app/Contents/MacOS/Blender
```

The Blender script is included and Python-syntax-checked, but **not executed here** because Blender isn't installed in the build environment. If the actual NASA bundle is missing, the script refuses to create a fake "NASA" scene.

## NASA visual model source

https://svs.gsfc.nasa.gov/14959/ includes `moon_small.glb` and larger lunar GLBs for web and animation. Unlike the site's compact low-fidelity sphere, its topographic versions are substantially larger. These models are not shipped in the ZIP; download from NASA yourself, then import into Blender to inspect.

## Optional Claude Code review

Install/authenticate Claude Code using Anthropic's official setup instructions, then launch it from the extracted POLARIS folder. An example review request:

> Audit the POLARIS X lunar visibility engine. Find coordinate-frame mistakes, incorrect horizon assumptions, time-series sampling issues, missing independent reference tests, GPU performance problems and accessibility defects. Do not substitute fabricated metrics. Write failing tests first and clearly mark unverified results.

Claude Code is a separate Anthropic product and may require a paid subscription or usage credits. It was **not run** to construct this version.

## 3D model generation

Higgsfield's Tripo generation models can produce GLB assets with detailed geometry and PBR options. Generated rover/antenna props can make an educational view easier to interpret, but all such props must be visually and textually marked illustrative. Do not replace NASA relief tiles or DEM physics with generated landforms. No billable 3D generation was initiated for this release.
