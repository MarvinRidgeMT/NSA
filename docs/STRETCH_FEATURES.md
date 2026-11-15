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

## 2. Information hotspots — done

**What it computes.** `science/stretch/hotspots.py` starts from the nominal skyline-controlling samples already traced
by `derived.attribution`. For each near-field controller it samples that location and the observer ground across aligned
PGDA 78 clones 1–20, computes deterministic pixel-minus-observer relief variance, maps that spread through the local
skyline Jacobian `degrees(cos(theta)^2 / distance)`, then sums the resulting horizon-angle variance over bundle-defined near-horizon
Sun/Earth target-hours. Samples are grouped by their containing 5 m PGDA pixel and ranked in deg² h. The complete
ranking and explicit top ten are written to `derived.hotspots` and `data/stretch/hotspots/`; every block and tile has a
stable result ID and `PILOT` label.

**Inputs.** The two 1 m reference bundles, their nominal `derived.attribution` and `derived.coverage` blocks, nominal
PGDA 78 5 m terrain, and aligned absolute-elevation clones 1–20. The critical-margin band comes from each bundle rather
than the browser. The existing `science/` code and results are read-only.

**Limits.** This is a piecewise nominal-controller sensitivity ranking, not probability, formal value of information,
or a calibrated risk estimate. Paired relief removes clone-wide shared vertical shifts; absolute pixel variance remains
a diagnostic. A controlling bilinear ray sample is assigned to its containing 5 m pixel. Controller
switching is not modeled here and will be tested by the flip-forecast PILOT. PGDA 78 clones cover the near tile only;
far-field controllers are excluded, and the scoring function forces any candidate beyond the finite horizon distance
to zero. A zero score can mean no clone-covered near-critical target-hours, not globally certain terrain.

**Runtime.** With the 20 public clone rasters cached, the final deterministic rerun completed both sites together in
1.31 s on this Apple Silicon checkout. The viewer only projects and filters the pre-ranked bundle tiles.

**Key result.** Site04 ROI3 evaluates 111 nominal controlling pixels, seven with positive sensitivity. The leading tile
is `p78-r1418-c1262` at −89.780403170321°, 203.803049295234°E, 15–17 m from the observer, with score
9.666043742541 deg² h; it is part of the already documented local rise controlling marginal Sun hours. Site01 ROI6
evaluates 174 pixels and has zero positive clone-supported scores: it has no near-critical Sun hours, and all 33
near-critical Earth hours are controlled by far-field terrain outside the PGDA 78 clone tile. The viewer discloses this
zero state rather than treating clone agreement as global certainty.

## Current ordered-stop report

| feature | status | tests | runtime | key result | safe to show in demo? |
|---|---|---|---|---|---|
| Arrival-slip sweep | done | 5 stretch, 47 science, 21 Blender, 15 app, 34 web unit; typecheck/build; 19 Playwright | 260.9 s Site04 + 269.1 s Site01 cold terrain; 18.6 s + 20.9 s cached | Site04 drops from 20/20 to 19/20 at +66 h and +72 h; 0 h = 94.362 % nominal Sun | yes, only with visible PILOT + SOURCE-BASED UNVALIDATED labels and the deterministic-clone/local-visibility caveats |
| Information hotspots | done | 5 hotspot tests (10 stretch total), 47 science, 21 Blender, 15 app, 34 web unit; typecheck/build; 21 Playwright | 1.31 s for both sites, cached | Site04: 7/111 positive tiles, top local tile 9.666043742541 deg² h; Site01: zero positive because critical Earth controllers are outside clone coverage | yes, as a PILOT sensitivity proxy with the zero-state, coverage and nominal-controller limitations visible |

Features 3–4 are intentionally not started in this ordered stop. Their final status rows will be added after their own
implementation/report stops.
