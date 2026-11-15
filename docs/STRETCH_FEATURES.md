# POLARIS X stretch features

All stretch results are research-pilot decision evidence. They remain source-based and explicitly unvalidated until the
independent checks in the science bundles pass. A terrain-clone count is a deterministic comparison across the tested
PGDA 78 realizations, not a probability or calibrated risk estimate.

## 1. Arrival-slip sweep beyond ±12 h — done

**What it computes.** `science/stretch/arrival_slip.py` shifts each fixed 14-day reference window from −72 h through
+72 h in 6 h increments. For each of the 25 windows it reports hourly-sample Sun-centre % and Sun+Earth %, nominal and
PGDA 78 clone 1–20 min/max, and the number of clones that meet both bundle-carried requirements: Sun-centre ≥ 70 % and
Sun+Earth ≥ 40 %. The output is `derived.arrival_slip` in each 1 m reference bundle plus a sidecar under
`data/stretch/arrival_slip/`. Every block and point has a stable result ID and the `PILOT` label.

**Inputs.** Site04 ROI3 1 m and Site01 ROI6 1 m `polaris-science-results-v1` bundles; NASA PGDA product 78 nominal 5 m
terrain and clones 1–20; NASA PGDA product 90 LDEM 80 m far field; JPL Horizons target-centre observer ephemerides at
one-hour cadence. The existing skyline and margin solvers are imported read-only.

**Limits.** Local finite-DEM geometric visibility only. The 1 m near-ray step and 280 km reach match the input bundles.
The MVP counts hourly samples including both endpoints and does not bisect shifted-window crossings. Product 78 clones
vary the near 5 m tile only; they do not represent far-field uncertainty. Clone min/max and k/20 are not probabilities.
NASA/JPL inputs and frame checks remain source-based unvalidated; this is not flight, power or DSN certification.

**Runtime.** On this Apple Silicon checkout, the cold terrain sweep took 260.9 s for Site04 and 269.1 s for Site01,
excluding one-time JPL/far-raster acquisition. With those public inputs cached, the final deterministic rerun took
18.6 s and 20.9 s respectively. The viewer performs no science computation.

**Key result.** At Site04 ROI3, the 0 h nominal Sun value exactly reproduces the bundle's 94.362 %. At 0 h all 20 clones
pass; the clone ranges are Sun 87.537–97.329 % and Sun+Earth 64.392–74.481 %. The first drop is at +66 h: 19/20 pass
because the minimum clone Sun value is 69.733 %, below the 70 % requirement; +72 h is also 19/20. Every other tested
Site04 slip is 20/20. Site01 ROI6 is 20/20 across the full sweep; nominal and clone Sun values are 100 %, while
Sun+Earth ranges from 60.237 % to 97.329 % across the tested slips.

## Current ordered-stop report

| feature | status | tests | runtime | key result | safe to show in demo? |
|---|---|---|---|---|---|
| Arrival-slip sweep | done | 5 stretch, 47 science, 21 Blender, 15 app, 34 web unit; typecheck/build; 19 Playwright | 260.9 s Site04 + 269.1 s Site01 cold terrain; 18.6 s + 20.9 s cached | Site04 drops from 20/20 to 19/20 at +66 h and +72 h; 0 h = 94.362 % nominal Sun | yes, only with visible PILOT + SOURCE-BASED UNVALIDATED labels and the deterministic-clone/local-visibility caveats |

Features 2–4 are intentionally not started in this ordered stop. Their final status rows will be added after their own
implementation/report stops.
