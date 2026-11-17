# POLARIS X v2 — round 3 split (16 Nov 2026)

Base: `feature/v2-whole-moon` at the commit that adds this file (rounds 1–2 merged except R4 render-vs-real, still running).
Same rules as before: own branch cut from it, commit only there, never push; shared docs append-only; own STATUS row.

| Session | Prompt § | Owns | Must not edit |
|---|---|---|---|
| T1 NASA-user features + gates | §7 | `science/exports/**`, `science/api/**` (solver API generalised to worlds: OpenAPI, local server, batch, AI tool-spec), `docs/v2/API.md`, `docs/v2/GATES.md`, gate scripts under `web/scripts/gates/**` | web UI components (T2), worlds (T3) |
| T2 web integration of v2 | §2.2 coverage layer, §2.5 query panel, §5.1 Blender-exported globe | `web/src/**` new components and the globe/layer wiring, `web/tests/**` for them, git-ignored `web/public/globe|layers/**` assets | `science/**` (call T1's API or precomputed files only) |
| T3 Mars + solver/world follow-ups | §3.3, open items of R1/R6 | `science/worlds/**`, `science/anysite/**` (the `world=` hook, SLDEM2015 per-product adapter bug), Mars/Mercury data under `$POLARIS_DATA/v2/products/{mars,mercury}_*` | web, exports/API |
