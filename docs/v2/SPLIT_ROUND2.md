# POLARIS X v2 — round 2 split (16 Nov 2026 ~11:40 EST)

Base: `feature/v2-whole-moon` at d79f035 (all six round-1 sessions merged). Each session works on its own branch cut from
it, commits only there, never pushes; the coordinator merges. Shared files stay append-only (`docs/BUILD_STATUS.md`,
`.gitignore`); in `docs/v2/STATUS.md` add or edit only your own row.

| Session | Prompt § | Owns | Must not edit |
|---|---|---|---|
| R1 pyramid as solver terrain | §2.4 finish | `science/anysite/**`, `science/terrain/stack.py` (API additions only, contract amendments appended), `data/anysite/**` | `tools/globe/**`, Blender, web |
| R2 pyramid finishing | §2.3, §2.5, §2.2 display formats | `tools/globe/**`, `pyramid_visual`, global analytics maps, display tiles under `$POLARIS_DATA` / git-ignored `web/public/globe/**` | `science/**` |
| R3 Blender whole Moon | §5.1, §5.2 | `blender/v2/**`, `blender/tests/**` | `science/**`, `tools/**` |
| R4 render twins + scoring | §6.2, §6.4–6.5 | `tools/imagery/**`, `tools/validation/render_vs_real/**`, `docs/validation/RENDER_VS_REAL.md`, in-app viewer component `web/src/components/RealVsModel*.tsx` | the pre-registered protocol and catalogue (frozen; hashes in `docs/v2/PREREGISTRATION.md`) |
| R5 6D decision tools | §4 | `science/decision/**`, `science/cube/v2.py` (additions), `web/src/components/Decision6D*.tsx`, `web/src/bundle/scenarioCubeV2.ts` (additions) | terrain, Blender, imagery |
| R6 worlds abstraction + Mercury | §3.1, §3.2 | `science/worlds/**`, Mercury data under `$POLARIS_DATA/v2/products/mercury_*` | Moon numbers (the Moon regression must be unchanged) |
