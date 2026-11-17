# Render-vs-real protocol — Amendment A3 (registration search radius; registration input bug)

Written 16 Nov 2026 by session R4. Hash in `docs/v2/PREREGISTRATION.md` (Entry 4). Disclosure of what had been computed
before this amendment is part of it.

**What happened under A1.** The pipeline was run end to end on two dev rows (M162478694LC and M162485477LC, both
site04_roi3), producing A1 scores. In both, the registered offset sat on the A1 search boundary (± 150 m = 3 × the A1
engineering value σ = 50 m, which A1 said was not a citation). A code bug was also found: the real image was set to 0 outside
the analysis window *before* the Sobel filter, so the window outline itself was a strong "edge" in the real image's gradient.
A diagnostic registration with the bug fixed and an unbounded search (±95–110 px) was then run on ten dev rows (8 more rows,
PGDA 78 only, 8 samples; offsets and NCC only, no shadow metric computed). Result: offsets of 7 m to 290 m on the ground; the
NAC-L and NAC-R frames of one orbit moved identically (98 m / 97 m, so not a detector-mapping error); per site they are not
constant (not a datum/terrain frame error); the largest were in July 2009 (commissioning) and one 2011 orbit. Some offsets are
perpendicular to the Sun azimuth (pointing-like), some along it (where a shadow-length difference from terrain can look like
an offset). Published single-image NAC accuracy is ~20 m (Speyerer et al. 2012 ISPRS; Wagner et al. 2024 PSJ), so these
offsets are larger than documented; their cause is **not resolved** here (open item).

**Changes.**
1. Registration input: the Sobel gradient magnitude is computed on the whole exposure-normalised crop (special pixels set to
   the median, 1.0), then masked by the analysis window. (Bug fix; no rule change.)
2. Search radius: **± max(3 px, 400 m / binned GSD)** instead of ± 3σ with σ = 50 m. 400 m covers the largest diagnostic offset
   (290 m) with margin. This is chosen from the diagnostic offsets (not from shadow scores), on dev only, and is stated as such.
3. Because a wide search can also absorb part of a terrain-caused shadow displacement, every row additionally reports the
   ground offset split into along-Sun and across-Sun components (m), and the report gives unregistered and registered
   numbers side by side with equal prominence. Rows whose offset exceeds 60 m (3 × the documented 20 m) are flagged
   `offsetBeyondDocumented`.
4. The two A1-scored rows are kept, unchanged, in `tools/validation/render_vs_real/results/scores_pre_A3.jsonl` and listed in
   the report; all scores in `results/scores.jsonl` are computed under A1 + A2 + A3.
