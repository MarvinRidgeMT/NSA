# POLARIS X architecture

POLARIS X is a local research prototype with one scientific data contract and two visual consumers. It does not use Blender lighting or Cesium imagery as numerical science inputs.

```text
NASA PGDA GeoTIFFs ─┐
                    ├─ app/scripts/prepare_science.py
JPL Horizons API ───┘              │
                                   ▼
                         POLARIS-X5D-v2 JSON
                         schema + provenance
                              │       │
                  ┌───────────┘       └───────────┐
                  ▼                               ▼
       Browser science engine             Blender scene builder
       horizon / visibility / 5D          editable .blend / GLB /
       scenarios / WebGL dashboard        three evidence renders
```

## Components

- `app/scripts/prepare_science.py` ingests official raster and ephemeris responses, validates declarations and orientation, and writes the v2 bundle. It never substitutes synthetic data after a source failure.
- `schemas/science-bundle-v2.schema.json` specifies the interchange contract.
- `app/src/science.js` performs finite-DEM terrain horizons, target-center visibility, time interpolation and deterministic scenario calculations.
- `app/src/scene.js` renders the local terrain. Optional Cesium Moon is a separate visual context and is not sampled by the solver.
- `blender/polaris_geometry.py` supplies the pure-Python horizon/ray geometry used by the Blender builder.
- `blender/build_lunar_science_scene.py` authors named collections, UTC-keyed Sun/Earth geometry, cameras, manifests, `.blend`, `.glb` and evidence frames.

## Responsibility boundaries

The browser and Blender outputs are consumers of source bundles. The browser is the interactive numerical front end. Blender is the editable authoring and presentation scene. Neither turns source-based inputs into a validated mission product. Scientific status remains `SOURCE_BASED_UNVALIDATED` until an independent illumination comparison is completed and recorded.

The fifth axis is a selected terrain realization or deterministic mission assumption. It is not another spatial dimension and is not a probability distribution.

## Local execution

- `bash run_polaris.command` launches the browser app on localhost.
- `bash run_blender.command --demo` builds an explicitly synthetic scene.
- `bash run_blender.command --bundle app/data/polaris-source-site01-2026-11-14-v2.json --site connecting` builds the source-backed scene.
- `bash test_all.command` runs fast checks; add `--full` to rebuild and verify both Blender scenes.
