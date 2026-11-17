# POLARIS X v2 — pre-registration record (render vs real)

Append-only. Each entry freezes files by SHA-256 **before** any result that depends on them is computed. The scoring code
must recompute these hashes and refuse to run on a mismatch. `tools/imagery/tests/test_preregistration.py` checks every
`| file | sha256 |` row below against the working tree, so an edit to a frozen file fails the test suite.

## Entry 1 — 16 Nov 2026, session S6

State at freezing: **no render twin exists and no score has been computed** (§6.2, §6.4–6.5 not started). The only images
fetched are 20 ODE thumbnails of `dev` images for a pipeline test (decode check only; not inspected for scoring).

Protocol committed in `cc73020a1c805277ea8c104f3d6ae4ceed312648` (2026-11-16T03:09:30-05:00); the frozen catalogue is the one
committed in `5c6e234` (a rebuild of `70b2b40` that rounds floats to the CSV's precision before the split, so the split can be
re-derived from the file; same rows, images and held-out count).

| file | sha256 |
|---|---|
| `docs/v2/RENDER_VS_REAL_PROTOCOL.md` | `bf85659d39261f34b631be7a75110f227feb64092aa600941307128900721516` |
| `imagery/catalogue.csv.gz` | `4b941d61f1ecb06155a2b0ffcc7f9a5f9ea1dc5b41ef6918ff1f69f424515e01` |
| `imagery/catalogue.schema.json` | `f29c992edf1a3f9dfbcf63ed4085d1e65d0193b2229ea553d15be13c86006f6b` |
| `imagery/catalogue.provenance.json` | `209816e9148af39c431616c181cff993f942fff5ebe97a8ca04a89c434c6383e` |
| `tools/imagery/catalogue.py` | `7ed08b44caa108548d9f1b08c2ef284b9fff9b5229d6e01f30b9d8723878e7e0` |

**Disclosure.** The 20 pipeline-test thumbnails were drawn from `dev` of the `70b2b40` catalogue. After the rebuild, one of them —
LROC WAC `M110175181CC` (1×32 px ODE thumbnail, 1,263 bytes, SHA-256 `38bc4c59…16d7e5ba`) — falls in `heldout`. It was decoded
for its size only and never displayed or scored; the cached copy was deleted. It stays held out (moving it by hand would be a
selection). The other 19 are `dev` in the frozen catalogue.

Catalogue v1: 11,726 rows (image × site), 7,298 unique images, **2,124 held out** (seed `polaris-x-v2-heldout-2026-11-16`,
30 % of the 7,081 eligible images; the 217 `prior_use` NAC images are dev). Counts: `docs/v2/IMAGERY_CATALOGUE.md`.

`tools/imagery/catalogue.py` is frozen with the catalogue because it defines the split rule; a later change to it needs a new
entry here (and must reproduce this catalogue's split byte-for-byte, or produce a new, separately hashed catalogue version).

## Entry 2 — 16 Nov 2026, session R4 (dev-split pilot, LROC NAC)

State at freezing: **no render-vs-real score has been computed.** One dev image (M162485477LC × site04_roi3) was rendered and
viewed next to its real window to debug the camera; nothing was measured. Amendment A1 fixes implementation choices that
protocol v1.0 leaves open (binning to the 5 m terrain grid, line cropping, registration implementation and the 50 m pointing
value, renderer settings, terrain products and photometric models, the dev cluster sampling). Held-out images are untouched.

| file | sha256 |
|---|---|
| `docs/v2/RENDER_VS_REAL_PROTOCOL_A1.md` | `017f86bd62030495f997b89fe352764882f44efead293a2b559c522c1bc7b00f` |

## Entry 3 — 16 Nov 2026, session R4

Still no render-vs-real score computed. Amendment A2: state-polynomial degree chosen per row (3–7) by the A1.2 geometric
fit gate.

| file | sha256 |
|---|---|
| `docs/v2/RENDER_VS_REAL_PROTOCOL_A2.md` | `5e96d41a4863ec598bcae710e110fea5b826610ba37260c4987733ea228bc50d` |

## Entry 4 — 16 Nov 2026, session R4

Disclosure: two dev rows had been scored under A1 (kept in `tools/validation/render_vs_real/results/scores_pre_A3.jsonl`) and
a diagnostic registration (offsets/NCC only) run on ten dev rows before this entry. Amendment A3: registration input bug fix,
search radius ±400 m, along/across-Sun offset reporting. No held-out image involved.

| file | sha256 |
|---|---|
| `docs/v2/RENDER_VS_REAL_PROTOCOL_A3.md` | `db450977d9137919c8b6c040b9e0a3917a55081745f375f2a62deb45ea3480b5` |

## Entry 5 — 16 Nov 2026 (~23:35 EST), session R4

Disclosure: 19 dev rows had been scored under A1–A3 with the FDF orbit (kept in
`tools/validation/render_vs_real/results/scores_A3_fdf_partial.jsonl`). Amendment A4: spacecraft position from the LOLA/LRO
Radio Science GRGM900C SPKs where they cover the image (FDF `lrorg` otherwise, flagged), registration radius back to
3 × the documented 20 m NAC geolocation for those rows. Held-out images untouched.

| file | sha256 |
|---|---|
| `docs/v2/RENDER_VS_REAL_PROTOCOL_A4.md` | `762bdd608dd34a2df9bdbdcac9e0882eb9889dec332414a7adef5c29a926aeb8` |
