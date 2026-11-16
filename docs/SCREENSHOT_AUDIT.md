# Screenshot audit

Captured 14 November 2026 with the automated Chrome smoke workflow at 1512×982. The script fails on browser console/page errors and also checks that each WebGL canvas encodes to a nontrivial PNG.

## Local source terrain

`app/docs/browser-source-case.png`

- Site01 full 401×401 5 m surface is visible over the wider 80 m regional context.
- HUD reports `5 M + 80 M LOD` and approximately 435K triangles.
- Cyan line marks finite local coverage. The alpha/height LOD seam is presentation-only.
- Surface node, correctly rotated target rays, scale/compass HUD, UTC, source status and binding constraint are visible.
- Status remains `SOURCE-BASED · UNVALIDATED`.

## Global Moon

`app/docs/browser-global-moon.png`

- Embedded NASA SVS 8K LRO color-plus-height GLB is centered, textured and visibly topographic without Cesium or a token.
- HUD reports 2.02M vertices / 1.02M triangles and `NASA SVS LRO TOPO GLB · LOADED`.
- Orbit preset is aligned to the selected south-pole site, with the site marker centered and polar latitude rings visible; drag remains available for free global orbit.
- The asset is explicitly a global orientation model, not numerical terrain.

## Direct-file launch

`app/docs/browser-file-launch.png`

- `file://.../app/index.html` loads the same full local source runtime without module/fetch failures.
- The source terrain canvas is nonempty and the scientific status remains unvalidated.

## PGDA 69 South Pole reference

`web/docs/screenshots/06-polar-map-overview.png` and `07-polar-map-site01-earth.png`

- Whole-pole 240 m Sun-average view and native 60 m Site01 Earth-average view render from the generated NASA reference layer.
- All 17 PGDA 78 regions are listed with source zonal averages/ranges; the selected ROI and loaded bundle observer are overlaid.
- Product badge, scale, graticule, no-data key and caveat disclosure are visible. These 18.6-year averages are not presented as POLARIS mission-window results.

These images demonstrate rendering and UI integration only. They are not evidence of independently validated illumination or terrain accuracy.
