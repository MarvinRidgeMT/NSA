# POLARIS X — BUILD_STATUS (branch `a-science`)

> **Provenance of this checkout.** The live repo was not reachable from the cloud session
> (no git checkout, no Mac folder connected, invalid GitHub token). At Sid's instruction this
> branch was built on the archived `POLARIS-X5D-Blender-Codex-Mac.zip` from the Claude project,
> imported as commit `cc1d7f0` on `main`; `a-science` branches from it. Port these commits onto
> the live `a-science` (e.g. `git am` from the delivered patch series). `CLAUDE.md` was read from
> the project docs; the archive has no `CLAUDE.md` or `docs/SCIENCE_BUILD_STATUS.md` (this file is new).

## 0. Baseline (before any edits) — 2026-11-14 ~13:05 UTC

| Command | Exit | Result |
|---|---|---|
| `git status` | 0 | `On branch a-science, nothing to commit, working tree clean` |
| `python3 -m unittest discover -s blender -p 'test_*.py' -v` | 0 | `Ran 6 tests ... OK` |
| `(cd app && npm test)` | 0 | node --test, 13 pass / 0 fail (Node v22.23.4) |

Env: Python 3.13.18, numpy 2.5.3, rasterio 1.5.2 (GDAL 3.12.2), pyproj 3.8.0.
Scope rule honoured: no edits to `web/` or `app/src/`.

## 1. T1 — frames + Moon-fixed 3D model ✅ (red → green)

Files: `science/frames.py`, `science/dem.py`, `science/skyline.py`, `science/tests/test_frames.py`.

- Red: `python3 -m unittest discover -s science/tests -t . -v` → exit 1 (`ModuleNotFoundError: science.dem`), then one
  test failure from a forward-difference bias in the test itself (fixed to central differences).
- Green: same command → exit 0, `Ran 9 tests ... OK`.
- Covered: grid↔ENU (local north = (sin L, cos L), east = (cos L, −sin L)); grid_az = local_az + L, so the legacy error is
  exactly L (Site01 −137.49°, Site04 −171.87°); synthetic ridge 2 km due local east of Site01 gives el(az 90) > 5°,
  el(az 270) < 0°; pyproj round-trip from the LDEM COG's own CRS (WKT cached at `data/raw/LDEM_80S_80MPP_ADJ.crs.wkt`)
  < 1 mm, and the closed form agrees with that CRS < 1 mm at both sites.
- Model: P = (R+h)·u(lat,lon), R = 1 737 400 m; elevation = asin((P−P_obs)·up/|P−P_obs|); rays are great circles.
- Not changed: `app/src/science.js` (out of scope) and `blender/polaris_geometry.py` still contain the grid-direction bug;
  they are superseded as numeric authorities by `science/` + the bundle.
