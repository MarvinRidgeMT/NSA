# SVS 4930 comparison — result (run 15 Nov 2026 00:42 EST)

Protocol: `docs/validation/SVS4930_PROTOCOL.md`, frozen before any frame was compared; SHA-256
`1946a9c58b406de56d2e79624c31748db7db688cab68304cafefa4d613ef0038` (the comparison script refuses to run if it differs).
Script: `tools/validation/svs4930_compare.py`. Output: `data/validation/svs4930/svs4930_comparison.json` (every row, every frame hash).

**Release status is unchanged: `SOURCE_BASED_UNVALIDATED`.** The protocol says a PASS does not change the label; changing it is a
team decision (Sid / Anish). This is not a NASA validation, endorsement or review of POLARIS.

## Reference
NASA SVS 4930 south-pole illumination frames 3805–3973 (169 frames, 1920×1080, 2-hour steps, 2026-11-14T00Z → 2026-11-28T00Z),
one SHA-256 per frame in the JSON. Registration: pole at the cyan crosshair (959, 539), 112.75 m/px, rotation 0°, not mirrored;
mean Lambert correlation 0.50 over five fit frames using the sub-solar point printed on each frame's overlay.

## Result per site (fixed parameters: Y < 8 = shadow; 3×3 block disagreement = ambiguous, excluded; |margin| < 0.5° = near-critical, excluded)

| Site | Frames | Ambiguous | Near-critical | Compared | Agreement | Without near-critical exclusion |
|---|---|---|---|---|---|---|
| Site04 ROI3 | 169 | 65 | 16 | 89 | 1.000 | 0.914 |
| Site04 ROI4 | 169 | 74 | 0 | 95 | 1.000 | 1.000 |
| Site01 ROI6 | 169 | 22 | 0 | 147 | 1.000 | 1.000 |

Verdict per the protocol: **PASS** (≥ 20 compared samples and ≥ 0.90 agreement at all three sites).

## What this does and does not show
- **Low discriminating power.** Every compared sample is lit in both products (confusion: both lit 331, both shadow 0, disagreements 0).
  The comparison confirms that POLARIS does not report shadow where SVS 4930 shows sunlight over these two weeks; it does not test
  whether POLARIS finds shadow where SVS shows shadow.
- The 16 Site04 ROI3 near-critical samples are hours when POLARIS reports the Sun centre blocked by a ~1.6 m rise about 16 m away.
  That feature is far below the 113 m frame resolution, so SVS cannot resolve it; the protocol excluded these before results were seen.
- Site01 ROI6: the 3×3 SVS pixels around the site are often mixed (11 dark centre pixels while POLARIS has +3.7° margin); those
  samples were excluded as ambiguous by the fixed rule.
- SVS 4930 is a rendered visualization product, not a numerical illumination dataset; resolution (~113 m/px) is far coarser than the 5 m DEM.
- A discriminating test needs a period or product with shadow at these sites (or a numerical product such as a PGDA illumination
  time series at matching resolution). Not done.
