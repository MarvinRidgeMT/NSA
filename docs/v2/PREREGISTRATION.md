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

## Entry 6 — 17 Nov 2026, coordinating session (held-out run, LROC NAC)

State at freezing: **no held-out image has been fetched, rendered, looked at or scored.** The dev pilot (A1–A4) is complete.
Amendment A5 defines the single held-out run for LROC NAC: every held-out NAC row of the frozen catalogue, the dev pilot's
frozen parameters, a reporting-only near-total-shadow stratum with a secondary count-matched mask (the headline Otsu rule is
unchanged), and the §8 claim rule made precise. The code that the run executes is frozen here too;
`tools/validation/render_vs_real/heldout.py` refuses to start if any row below (or above) differs, and a later change to any
of these files needs a new amendment.

| file | sha256 |
|---|---|
| `docs/v2/RENDER_VS_REAL_PROTOCOL_A5.md` | `a1469c09c5046bbb335ca380c7f4029f62f4845b407cc4a98ae8f36fa6c0faa6` |
| `tools/validation/render_vs_real/common.py` | `5eb2fddf1f4fae5013f10dcb6db7d57e8239d31d9c3bd0303eaf6144387d1588` |
| `tools/validation/render_vs_real/fetch.py` | `94ec5aa43b08c9ff27b75f10f320d60df48fd8a561da5d37a5fec08e9e6367fb` |
| `tools/validation/render_vs_real/geometry.py` | `69e35fdb33fd9ec9f7ec19a531ae7a74ce2ae25cef8cee5786fcd91a02bbbfab` |
| `tools/validation/render_vs_real/nac_camera.py` | `07e304c62d8803a11430ecea5a9136906eb9b5486730243a9f3b7969b5feb990` |
| `tools/validation/render_vs_real/realimage.py` | `34cb5da3981044278c31a4279eb1469cd62d8c8912c9410864700acec272e2c8` |
| `tools/validation/render_vs_real/score.py` | `e919b97d8d27219df00a09af73f6e3cfc92bd657e2a11527b95cb3fc3c764868` |
| `tools/validation/render_vs_real/run.py` | `aaaf884a5f6c4e37f08c869ecce9810790246cc495f62c919324ca190f2af375` |
| `tools/validation/render_vs_real/blender_twin.py` | `cb2e31d84e924e29da6095e85bea90c5611a7fc2d71fc9ff1f35bd018e27e957` |
| `tools/validation/render_vs_real/terrain_products.py` | `e7e2454b698a5084ef113aa45e1fc0f60f0babcbc9bcc498fdea62e5a1097907` |
| `tools/validation/render_vs_real/spice_kernels.py` | `9904790d5db3e13d0158108185a521ab27fa973864426ebc50f5ba7859d9feda` |
| `tools/validation/render_vs_real/heldout.py` | `8a81e35f847b4189e95b4510a72706d4800106cf65dd0380a205d98b099792a5` |
| `blender/v2/hapke.py` | `753687ea635973e7028c079849f536ed0c9c6ae4c633e86d34eff1eae2238d82` |
| `blender/v2/hapke_nodes.py` | `fae1c7438470f1230d564d5e0396aaae7983a5091fc7f1a585be1c9d7d6df1e8` |
| `blender/v2/terrain.py` | `00d2ada28dde6f1d19f9435e7b8eb348b85519a5fcae2ea303a2352a17028363` |
| `tools/imagery/sites.py` | `9cb686b560fca36975c95ae36fec3bbad5f84ba173652a1ac018b15d420ce09e` |

## Entry 7 — 17 Nov 2026, coordinating session (dev pilot, LROC WAC)

State at freezing: **no LROC WAC row has been scored on any split; no held-out WAC image has been fetched.** One dev image
(3 rows) was rendered and displayed as the pipeline test, without metrics (A6, state at writing). Amendment A6 fixes the WAC
643 nm camera model, the native-pixel grid with the framelet rule, the dev selection and the reporting for the WAC dev pilot.
The WAC code is not frozen here; A7 freezes it before the WAC held-out run.

| file | sha256 |
|---|---|
| `docs/v2/RENDER_VS_REAL_PROTOCOL_A6.md` | `26a48bab464f81e7b579a2fefa1867028c64094ea0354060cf97cade478f401a` |

## Entry 8 — 17 Nov 2026, coordinating session (held-out run, LROC WAC 643 nm)

State at freezing: **no held-out WAC image or label has been fetched, rendered, looked at or scored.** The A6 dev pilot is
complete (6985db3). Amendment A7 defines the single held-out run for LROC WAC: every eligible held-out WAC row, the A6
parameters unchanged, the v1.0 Otsu rule unchanged, and a prediction written before the run. The WAC code that the run
executes is frozen here; the NAC code it imports is frozen in Entry 6. `wac_heldout.py` refuses to start if any row differs.

| file | sha256 |
|---|---|
| `docs/v2/RENDER_VS_REAL_PROTOCOL_A7.md` | `ca6ebc0790b109ca119e12fe89a8d531756fba75ac7d153aefa06ed207cb3464` |
| `tools/validation/render_vs_real/wac_camera.py` | `db72cff89709eb427fd29508908520afb2be49846ff563a0ec8a3e142641d32f` |
| `tools/validation/render_vs_real/wac_common.py` | `f54bfa9e84d6df907d26675f9811675dacba7d2ecc7810e1c4ad82e5cfa1f763` |
| `tools/validation/render_vs_real/wac_io.py` | `04e675f109f176533b1ecd96f7992f7d4e9919e4953f18872ce04437bd003eda` |
| `tools/validation/render_vs_real/wac_geometry.py` | `60422e986652ec6bdacc4bcf88e955fe8e9ac77f401886b07ee6f5160773ddb8` |
| `tools/validation/render_vs_real/wac_run.py` | `b6eb91ffe96820a72f93f1dbbf5a6dc6725023a9ad3a528bdbafd4143d240600` |
| `tools/validation/render_vs_real/wac_twin.py` | `00fce37f3ef3785f3239752ac120ead21de84219cccd0e3fac5b437a7984efa0` |
| `tools/validation/render_vs_real/wac_select.py` | `550640c577ec60df773b54ef158fb5398127f8eb328076029b7aa6bc26440baa` |
| `tools/validation/render_vs_real/wac_heldout.py` | `09a0ac581eae5494697a108f667548575763e963622eb59a279b1d64c18bb284` |

## Entry 9 — 17 Nov 2026, coordinating session (ShadowCam catalogue v2 and dev plan)

State at freezing: **no ShadowCam image has been rendered or scored on any split.** Catalogue v2 (camera-model footprints
for the 4,815 ShadowCam rows of v1, split unchanged; built by `shc_catalogue.py` at commit f172d6c from labels and KPLO SPICE
only) and Amendment A8 (camera model, convention test rule, dev pilot plan) are frozen here, as protocol §2 requires before
any ShadowCam render.

| file | sha256 |
|---|---|
| `docs/v2/RENDER_VS_REAL_PROTOCOL_A8.md` | `256bf8dda2f510ad3f5286ee5000c37a89a5647f0aaf5b2b5f1882512e2bc554` |
| `imagery/catalogue_shadowcam_v2.csv.gz` | `c21e3ddd7cb0d4d82b2cf20e1e5d565e4ab13b44975ac45bb8d1ff532c6584d3` |
