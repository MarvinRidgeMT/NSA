# Frontend source of truth (14 Nov 2026, 19:40 EST)

*Written by the Claude strategy/design session implementing Penumbra V3, after inspecting the repo and the running servers on
Anish's Mac (`~/Downloads/POLARIS-X5D-Blender-Codex`, branch `b-experience`, HEAD `8079924`, large uncommitted working tree).*

## What runs where (checked 19:05–19:10 EST)
| Address | What it is | Source directory | How it is served | State at 19:05 |
|---|---|---|---|---|
| `http://localhost:5174/` | **React/TypeScript science-bundle viewer** (R3F + three.js, zustand) | `web/` (`web/vite.config.ts`: `server.port 5174`) | `cd web && npm run dev` (Vite, hot reload; runs `sync-bundles` first) | Running; reads `web/public/bundles/index.json` (synced from `data/bundles`, `data/viewer`, `app/data`) |
| `http://127.0.0.1:4173/` | **Built preview of the same viewer** | `web/dist/` | `python3 -m http.server 4173 -d web/dist` (BUILD_STATUS 17:41) or `npm run preview` | Running; bundle `index-B28sWnr5.js` built 17:41 EST, i.e. older than the current `web/` sources until rebuilt |
| `http://127.0.0.1:5173/` | **Legacy "Lunar Mission Intelligence" app** (Codex's Three.js UI) | `app/` (`app/package.json`: `python3 -m http.server 5173`) | `bash app/run.command` | **Not reachable** from the built-in browser at 19:05 (navigation refused / connection failed). Not modified by this pass. |

## Answers
1. **Directories:** 5174 and 4173 = `web/` (dev and built); 5173 = `app/`.
2. **Official competition submission:** not formally declared in the repo. The release ZIP (`dist/POLARIS-X5D-SourceBuild-Mac.zip`, 13:40) packages `app/`; the
   hosted preview artifact (T-ORG-03) and all decision-evidence work (B1–B4, Ridge of Record, Certainty Height, Coverage) live in `web/`.
   **Decision taken here:** `web/` is the visual-development target (newest, carries the science integrations; preferred by the brief).
   Confirming which one is *submitted* is Anish's call (see "Open").
3. **Latest verified working viewer:** `web/` (Vitest 56/56 + 1 skip; Playwright 29 pass, 6 pre-existing failures, see BUILD_STATUS 19:40).
4. **Shared bundles:** `data/bundles/*.json` (a-science results bundles), `data/viewer/*.json` (ROI export with 401² 5 m DEM crops), copied into
   `web/public/bundles/` by `web/scripts/sync-bundles.mjs`; certainty and coverage sidecars in `web/public/certainty/` (built from `data/batch/2026-11-14`).
5. **Branches:** working tree = `b-experience` (`8079924` + uncommitted). `app/` work by Codex is also uncommitted in the same tree. `integration`
   worktree (`dca7d22`) not touched. Science = `a-science` on GitHub (`971df9a`, later `d7b5463`).
6. **Uncommitted files:** ~100 (`git status --short`), in `app/`, `web/`, `docs/`, `data/`, `tools/`. Nothing was committed or pushed by this pass.
7. **Actively edited by others (mtime check, 19:05–19:40):** `app/src/styles.css`, `app/index.html` (17:47–17:57, b-experience session A); `tools/sources/*`
   (new files ~19:25, another session — LROC NAC tools). `web/` had no edits since 14:36 before this pass.
8. **Preview vs source:** 4173 serves `web/dist`, which is only as new as the last `npm run build`. Rebuilt by this pass at the end (see BUILD_STATUS).
9. **Two frontends developed independently:** yes. `app/` (Codex: global Moon, presets, simple UI) and `web/` (bundle viewer: workspaces,
   decision evidence) diverged today. They share data only.
10. **Preserve / retire / integrate:** keep `app/` untouched until `web/` is accepted as the submission; do not build a third frontend.
    Integrating `app/`'s global-Moon flight into `web/` is a separate milestone.

## Rollback
- Before this pass: `tmp/web_before_penumbra_20261114_1906.tgz` (`web/src`, tests, package files, configs).
- To roll back: extract it over `web/` (`tar xzf tmp/web_before_penumbra_20261114_1906.tgz --overwrite`) and delete the new files listed in
  `docs/PENUMBRA_IMPLEMENTATION_STATUS.md` → "Changed files".

## Open (for Anish)
- Which frontend is the competition submission (`web/` recommended) and whether 5173 should keep running.
- Commit the `web/` working tree when Codex is idle (nothing here was committed).

## Concurrency note (19:45 EST)
While this pass was finishing, another session started editing `web/` at ~19:41 EST: new `web/src/bundle/visualLayers.ts`,
`web/tests/unit/visual-layers.test.ts` (23 tests, passing), `schemas/visual-layers-v1.schema.json` and `schemas/fixtures/`. None of the Penumbra files
were touched by it (SHA-256 of `App.tsx`, `styles.css`, `Scene3D.tsx`, `HorizonDome.tsx`, `CameraRig.tsx` checked equal to this pass's versions at 19:44).
**Coordinate before the next edit of `Scene3D.tsx` / `App.tsx`**: both sessions now work in `web/`. Vitest with their file: 79 passed, 1 skipped.

## Concurrency note (20:42 EST, Apex)
Session A (rebuild Phase 4/5) had edited `App.tsx`, `styles.css` and `three/Scene3D.tsx` (surface layer, south-pole context view) after the Apex backup. Apex changes were merged 3-way (both sides kept), tested (Vitest 89/1 skip, Playwright 41/41) and written only after re-checking the Mac hashes. Apex also adds one line to session A's `three/TerrainSurface.tsx` (the true-elevation light toggle). Penumbra/Apex is now quiet in `web/`.
