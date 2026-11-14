# POLARIS X — Blender + Codex development kit

This download combines the existing POLARIS X PRO browser application with a **Blender scene builder**, pure-Python terrain visibility helpers and project instructions for Codex. It also includes a link to a real editable Blender scene created in the hosted 3D Jutsu workspace.

**Editable scene (synthetic prototype):** https://higgsfield.ai/3d-jutsu/393826d4-72b2-468b-8def-820509cccdc4

## Start on a Mac

1. Install Blender 4.5+ (or compatible 5.x) and extract this folder.
2. Open Terminal in this folder and run:

```bash
bash run_blender.command --demo
```

The `--demo` builder generates a **synthetic**, local, animated lunar scene. It creates `blender/output/POLARIS_X_connecting_DEMO.blend`, `.glb`, and a report. Open the `.blend` in Blender; use the timeline to scrub through the Sun/Earth visualizations. `--demo` does not download or claim actual NASA data.

3. Run the source-based builder only after the NASA/JPL bundle is available:

```bash
# In this folder, create the real source bundle (requires internet and dependencies):
python3 -m venv .venv
source .venv/bin/activate
python -m pip install rasterio numpy requests
python app/scripts/prepare_science.py --sites connecting shackleton \
  --output app/data/nasa-jpl-science-bundle.json

bash run_blender.command --bundle app/data/nasa-jpl-science-bundle.json --site connecting
```

The resulting Blender animation uses angles from the source bundle and the provided NASA DEM crop, but **its ephemeris coordinate conventions, DEM geometry and independent illumination checks still require validation**. Visibility remains limited to local DEM coverage. The browser app runs separately from inside `app/`.

## Use in Codex

Open this folder in **Codex for Mac** or VS Code with Codex; project instructions are in `AGENTS.md`. Ask Codex to inspect tests and implement the first unvalidated science gate. If you use the Codex CLI and already have it installed, run `codex` from this folder. This ChatGPT conversation cannot automatically open your local Codex or Blender installation.

## Key outputs and limits

- `.blend`: editable Blender scene with named objects, mission markers, animations and cameras.
- `.glb`: portable geometry and basic materials; some Blender procedural look features may not transfer.
- `_metadata.json`: source, site, timeline sample mapping, visibility output and limitations.
- The fifth axis is a 3x3 observer-position test grid, not a probability distribution.
- **Synthetic mode is not NASA terrain or JPL astronomy.** Source mode is research-grade and still requires independent checks; it is not flight software.

## Verification performed here

- Six pure-Python geometry tests pass.
- Python syntax compilation passes for the Blender builder.
- The hosted Blender 5.2 scene was actually created and saved, with 22 objects and animated sightline controls. The local source-mode Blender script has **not yet been executed against a live NASA/JPL bundle in a local Blender installation**.

For the original browser app's tests and limitations see `app/README.md`.
