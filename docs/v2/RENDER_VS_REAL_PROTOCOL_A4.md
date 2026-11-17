# Render-vs-real protocol — Amendment A4 (spacecraft orbit source; registration radius back to the protocol rule)

Written 16 Nov 2026 (~23:35 EST) by session R4. Hash in `docs/v2/PREREGISTRATION.md` (Entry 5).

**Disclosure of what had been computed.** Under A1–A3 the full dev run had scored 19 image × site rows (228 records,
all products and photometry variants) with the NAIF PDS `lrorg` spacecraft ephemeris when this amendment was written. Those
records are kept unchanged in `tools/validation/render_vs_real/results/scores_A3_fdf_partial.jsonl` and are reported as the
"FDF orbit" comparison; the two A1 rows stay in `scores_pre_A3.jsonl`.

**Finding that motivates it.** The `lrorg` SPKs in the NAIF PDS archive are the LRO project's flight-dynamics (FDF) definitive
orbits (NAIF `spkinfo.txt`: "merged ... daily LRO definitive spacecraft ephemeris SPK files (fdf29_...)"). The LOLA / LRO
Radio Science team's GRAIL-gravity orbits (GRGM900C, PDS Geosciences node `lro-l-rss-1-tracking-v1`, files
`lro_{co,no,sm,es}_*_grgm900c_l600.bsp`; Mazarico et al. 2018, ~10 m class) differ from them, at the mid-times of the
diagnostic rows, by horizontal vectors that equal the registration offsets measured in A3's diagnostic with the opposite sign
(GRGM900C − FDF vs measured real − render ground offset: (−295, −146) vs (+266, +148) m; (−65, −76) vs (+65, +76);
(−65, −76) vs (+63, +75); (−105, −65) vs (+94, +58); (−18, +3) vs (+17, +35); (−9, +9) vs (+5, +16)). The large offsets were
the FDF orbit error, not pointing and not terrain.

**Changes.**
1. **Orbit:** the spacecraft position comes from the GRGM900C science SPK whenever one covers the cropped lines (loaded after
   `lrorg`, so it takes precedence); otherwise from `lrorg` (FDF), and the row is flagged `orbit = fdf`. Recorded per row
   (`orbit` in `results/geometry.csv`). The July 2009 commissioning images before 2009-07-13 06:25 UTC have no GRGM900C
   coverage.
2. **Registration radius:** back to protocol v1.0 §3.1: ± max(3 px, 3 × σ / binned GSD) with the documented single-image
   NAC geolocation σ = 20 m (Speyerer et al. 2012, ISPRS XXXIX-B4; Wagner et al. 2024, PSJ "Where is that crater?") for
   `orbit = grgm900c` rows; rows with `orbit = fdf` keep A3's ± 400 m and are reported separately.
3. **Crop lines:** each row keeps the image lines chosen in the first geometry pass (FDF orbit); the margin (≥ 1 km beyond
   the 10 km square) exceeds the largest orbit change found (≈ 330 m), so the square stays inside the crop. Real-image line
   windows are therefore not re-downloaded.
4. Everything else (A1–A3 metrics, products, photometry, gates) unchanged. All `results/scores.jsonl` records after this
   entry are computed under A1–A4.
