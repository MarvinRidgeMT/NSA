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
