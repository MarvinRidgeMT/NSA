# POLARIS X v2 — how the work is split across sessions

Source prompt: `docs/v2/inputs/CLAUDE_CODE_PROMPT_6D_worlds_blender_v2.md` (replaces the earlier 6D prompt).
Integration branch: `feature/v2-whole-moon` (worktree `../NSA-v2`), cut from `feature/5d-complete` at ae9f6d9.
Each session works in its own worktree on its own branch cut from `feature/v2-whole-moon`, commits only there, never
pushes. The coordinating session merges finished branches into `feature/v2-whole-moon`.

Frozen references (verify unchanged at the end of every session):
- tag `submission-2026-11-15` → c5dce9f (PR #2 merge, 15 Nov 22:58 ET; created before the last pre-deadline commit)
- tag `submission-final` → 8dde4f1 (main, 15 Nov 23:57 ET, contains submission/merged 62cc7b1)
- branch `submission/merged` → 62cc7b1 (15 Nov 23:46 ET). Never commit to, rebase or push `submission/merged`, `main`
  or `codex/lab-integration`.

| Session | Prompt § | Owns (create/edit freely) | Must not edit |
|---|---|---|---|
| S1 6D model + cube v2 | §1, team-prompt backlog | `docs/v2/6D_MODEL.md`, `docs/v2/BACKLOG.md`, `schemas/scenario-cube-v2.schema.json`, `science/cube/v2*.py`, `web/src/bundle/scenarioCubeV2.ts`, slicer grouping in `web/src/components/CubeSlicer.tsx` | terrain, Blender, imagery files |
| S2 whole-Moon data | §2.1, §0.4 | `tools/globe/fetch*.py`, `tools/globe/products.py`, `docs/v2/DATA_BUDGET.md`, `docs/v2/PRODUCTS.md`, `docs/DATA_PROVENANCE.md` (append), `$POLARIS_DATA/v2/products/**`, `docs/v2/DATA_MANIFEST.json` | pyramid code |
| S3 global pyramid | §2.2, §2.3, §2.5 maps | `tools/globe/pyramid*.py`, `tools/globe/seams.py`, `tools/globe/coverage.py`, `tools/globe/roughness.py`, `science/terrain/stack.py`, `$POLARIS_DATA/v2/pyramid*/**` | fetch code, solver |
| S4 any-site solver | §2.4 | `science/anysite/**`, its tests | `science/skyline.py` semantics (reuse it) |
| S5 Blender v2 | §5 | `blender/v2/**`, `blender/tests/**`, glTF-proof test | web 3D components except a test |
| S6 imagery + protocol | §6.1, §6.3 | `tools/imagery/**`, `imagery/catalogue.parquet`, `docs/v2/RENDER_VS_REAL_PROTOCOL.md` | everything else |

Shared files, append-only, one section per session: `docs/BUILD_STATUS.md`, `docs/v2/STATUS.md` (edit only your own row),
`.gitignore` (append lines). Interface between S2/S3/S4: `docs/v2/TERRAIN_STACK_CONTRACT.md` (change it only by
appending a dated amendment).

Not started tonight (sequential after Phase 1 per §8): Phase 3 decision tools across the whole Moon (§4), worlds
abstraction / Mercury / Mars (§3), NASA-user features and gates (§7), render twins and scoring (§6.2, §6.4–6.5).
