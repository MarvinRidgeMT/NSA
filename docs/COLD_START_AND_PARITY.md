# Cold start and dev/prod parity (Final Apex P1)

15 Nov 2026, Penumbra session. This extends `docs/PRODUCTION_PARITY.md` (14 Nov, pixel parity of dev and prod) with the
cold-launch investigation; it does not repeat that doc.

## The reported symptom

A tab showed "No bundles/index.json found", and an older preview tab showed an older build.

## What was found on Anish's Mac (00:45 EST, from the built-in browser pane)

| Address | What answered |
|---|---|
| `http://localhost:5174/` | Vite dev server (`/src/main.tsx`), `bundles/index.json` 200 |
| `http://127.0.0.1:5174/` | **nothing** (the dev server bound to `localhost`, which macOS resolves to `::1` first) |
| `http://127.0.0.1:4173/` | a **Python `SimpleHTTP/0.6`** server serving `web/dist` built at 23:01 EST (`assets/index-mtC7LE4E.js`), not `vite preview` |
| `http://localhost:4173/`, `:5173` | nothing |

No service worker was registered and Cache Storage was empty, so caching was not the cause. Two causes together explain both symptoms:
1. **IPv6-only binding.** With `host: 'localhost'`, Vite answered on `::1` only. A tab on `127.0.0.1` reached whatever else held that port (the stale Python server on 4173) or nothing at all (5174).
2. **Silent failure paths in the bootstrap.**
   - A 404 for `bundles/index.json` was turned into an empty list, so the page stayed blank with no message.
   - An HTML answer (a dev-server fallback, or a server rooted at the wrong folder) failed JSON parsing and produced the generic "No bundles/index.json found".
   - Opening `dist/index.html` from disk (file://) also produced that message, because browsers refuse `fetch()` there.

## What changed

- `web/vite.config.ts`: dev and preview bind `host: '127.0.0.1'` explicitly. `strictPort` was already on, so a busy port now fails loudly instead of letting two servers answer on different address families. `localhost` still works, because browsers and Node fall back to IPv4.
- `web/playwright.config.ts`: tests run against `http://127.0.0.1:4173`.
- `web/src/bundle/bootIndex.ts` (new): fetches `bundles/index.json` with `cache: 'no-store'` and gives each failure its own message:

  | Problem | Message names |
  |---|---|
  | file:// | "opened directly from disk … serve the folder" |
  | network | "Could not reach … Is the viewer's server still running?" |
  | HTTP 404 | "No bundles/index.json at <url> (HTTP 404) … serve web/dist rather than the repository root" |
  | HTML instead of JSON | "a web page, not the bundle index … serving the wrong folder" |
  | bad JSON | "not valid JSON" |
  | missing list / unsafe names | "no "bundles" list" / "without a plain .json file name" |
  | empty list | "lists no bundles" |

- `web/src/App.tsx`: the bootstrap is now `coldLaunch()`. Any failure shows a panel with the message, the page URL, **Retry** (re-runs the cold launch) and **Open a bundle file…**. It never substitutes a demo or another bundle, and says so ("no bundle was loaded, and none is substituted").
- `web/src/store/store.ts`: a failed bundle load offers Retry for *the same URL* (`loadRetry`). Bundle fetches use `cache: 'no-store'`.
- Session A's URL state (`startUrlSync`) runs before `coldLaunch()`, so a link's site, time, scenario, camera and layer still apply after a Retry.

## Launch commands (from `web/`)

```
npm run build && npm run preview      # production build, http://127.0.0.1:4173
npm run dev                           # development, http://127.0.0.1:5174
```

If something else already holds the port, Vite stops with "Port 4173 is in use"; stop that process (for example an old `python3 -m http.server 4173`) and run the command again.

## Verified

Cloud, Chrome + SwiftShader. `tests/e2e/cold-launch.spec.ts`, all pass:

| Check | Result |
|---|---|
| index 404 → error panel, no instrument, no demo banner; Retry after the file returns → app loads | pass |
| index answered with HTML → "wrong folder" | pass |
| bad JSON, then empty list (via Retry) → specific messages, no substitute | pass |
| hero bundle 404 → "was not found (HTTP 404)"; only that bundle was requested; Retry loads it and nothing else | pass |
| direct URL `/#decision`, then reload → same workspace, same bundle | pass |
| served `index.html` references the same `assets/index-*.js` as `dist/index.html` on disk, on both 127.0.0.1 and localhost; served `bundles/index.json` equals `dist/bundles/index.json` | pass |

Unit: `tests/unit/bootIndex.test.ts`, 4 cases, all pass. Screenshot: `web/docs/screenshots/penumbra/apex_final/cold_launch_missing_index_1440.png`.

## Parity

- The production build the tests use is built by the Playwright `webServer` command, or is the `dist/` on disk, which the parity test checks.
- Dev = prod pixel parity was shown on 14 Nov (`PRODUCTION_PARITY.md`) and has not been re-shot in this pass.
- Bundle checksums: every served bundle's SHA-256 is in `bundles/index.json`. The Evidence page prints the loaded bundle's hash, and `final-apex.spec.ts` checks it against the index.

## Not done

The stale Python server on the Mac's port 4173 was not stopped by Penumbra: it is not Penumbra's process. Anish should stop it before running `npm run preview`.

## Change log
- 15 Nov 2026 01:50 EST (Penumbra session): created.
