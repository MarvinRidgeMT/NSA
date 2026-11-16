# Science label audit (Penumbra Apex)

Date: 14 Nov 2026, EST. Scope: every user-visible sentence in `web/src` that states a result, a source or a limit.
Status of all numbers: **SOURCE-BASED · UNVALIDATED** (no independent validation of the solver yet).

## Verified against source data
| Claim on screen | Source | Value |
|---|---|---|
| Sun centre visible (bundle) | results bundle, repo solver, interval-based | 94.213 % (hourly 94.362 %) |
| Sun + Earth (bundle) | same | 71.912 % (hourly 72.107 %) |
| Sun-blocked hourly samples (bundle) | same, 2026-11-26T23:00 → 11-27T17:00 | **19**, contiguous, all attributed to R3 |
| Batch nominal at 1 m | batch sweep CSV (a-science 971df9a) | 93.769 % = 316/337 → **21** blocked hours |
| Longest Sun obstruction | bundle | 19.4434 h (time-weighted, interval crossings) |
| 1 m range across 20 realizations | certainty sidecar | Sun 87.24–97.03 %, Sun+Earth 62.61–74.78 %, pass 20/20 |
| Lowest sampled mast with Sun 100 % on all 20 | sidecar `all_maps_100pct_sun_mast_m` | 1.75 m (independently re-derived in VALIDATION_CHECKS) |
| Coverage | coverage sidecar | Sun 34.1 %, Earth 58.5 % of window hours (nominal DEM, 1 m) |
| R3 | bundle attribution | 12–169 m, az 78–144°, +1.563 m vs site ground, 5 m DEM, Sun 19 h |
| R1 | bundle attribution | 127.7–129.6 km, az 153–156°, +3232 m, 80 m DEM, Earth 41 h; never drawn in the 2 km crop |
> E1 (15 Nov 2026), Site04 RoI 3 1 m batch-v2 values quoted above (93.77 / 71.22 / 87.2–97.0): float32 heights, superseded by the float64 rerun (94.36 / 72.11 / 87.54–97.33).

19 vs 21: the bundle (repo solver) and the batch (separate solver) differ by two knife-edge hourly samples (A_SCIENCE_STATUS 13:06). The UI now labels every number `bundle` or `batch sweep` and says the two sample differently.

## Wording changes
| Before | After | Why |
|---|---|---|
| "NASA publishes 20 equally plausible versions of this terrain" | "NASA's PGDA 78 product includes alternate realizations of this terrain that reflect its elevation uncertainty; we evaluated 20 of them… They do not exhaust what the real ground could be." | "Equally plausible" is not a claim the product makes; agreement ≠ certainty. |
| "20 alternate NASA terrain maps" / "N maps tested" / "alternate maps" (Story, Decision Card, Certainty Height, Coverage, ridge notes, mast instrument) | "evaluated alternate (NASA) terrain realizations" / "realizations tested" | User brief wording. |
| "of Sun hours decided by terrain the maps vary" | "of window hours whose Sun horizon lies in the varied tile" | Coverage is over all window hours, not Sun hours. |
| "every hour without Sun is decided by a rise…" | "the bundle attributes every Sun-blocked hourly sample (19) to one rise…" | Names the quantity (hourly samples) and its source. |
| "19 h of Sun lost" | "19 Sun-blocked hourly samples attributed to it (bundle attribution, repo solver)" | Samples ≠ time-weighted hours. |
| Decision card: "keeps the Sun on all 20 tested maps" | "keeps the Sun centre in view on all 20 evaluated alternate terrain realizations"; "team requirement"; "agreement is not certainty" | Centre visibility, team (not NASA) requirement. |

## Distinctions kept on screen
- Geometric centre visibility ≠ power or communications (readouts, mast instrument, guide, decision card).
- Agreement across realizations ≠ certainty or probability (Certainty Height, Coverage, decision card).
- Team requirements (Sun ≥ 70 %, Sun+Earth ≥ 40 %) ≠ NASA standards.
- Imported ≠ validated: status badge and card footer "SOURCE-BASED · UNVALIDATED".
- Display-only items labelled: light clamp (on-screen tag), fill light, outline mast at heights with no bundle series, shadows on the context surface.
- No interpolation between sampled mast heights; the 128 km ridge is declared "beyond this 2 km DEM crop", never drawn.

## Change log
| When (EST) | Who | Change |
|---|---|---|
| 2026-11-14 20:52 | Claude (Penumbra Apex session) | Created. |
