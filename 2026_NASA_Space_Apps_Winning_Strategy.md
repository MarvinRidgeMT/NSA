# 2026 NASA Space Apps Greensboro: adversarial winning strategy

**Decision date:** 13 November 2026  
**Event:** 14–15 November 2026  
**Team assumption:** two people; Apple-silicon MacBook, 2017 Intel MacBook Pro (16 GB), Surface Pro 8 (8 GB)  
**Scope:** research and strategy only. No project implementation was created before the official start.

## Executive verdict

The best strategy is a **gated primary plus a prepared fallback**, not unconditional loyalty to POLARIS or any other prior concept.

1. **Primary, if it passes a three-hour kickoff data gate: _NISAR WITNESS_**  
   A claim-testing map for surface change. Instead of merely showing a before/after radar image, it asks: **“Does this apparent change survive the product-maturity, geometry, mask, coherence/quality, polarization, and control checks needed to trust it?”** It returns `supported`, `ambiguous`, or `not comparable`, with a reproducible evidence record. This is the highest global upside because fully validated NISAR Level 0–2 products were released only on 6 November 2026, one week before the event.

2. **Immediate fallback: _EVIDENCE FRONTIER_ for Lunar Landing Site Navigator**  
   Do not build another lunar 3D viewer or generic sunlight calendar. Build a **decision-falsification and observation-priority tool**: show whether alternate terrain models overturn a site/date decision, then identify the horizon sector whose improved measurement would resolve the decision. This is the safer two-person path and the stronger risk-adjusted local option, but it faces unusually mature prior art.

3. **Second non-lunar fallback: _FIRE CONCORDANCE_ for MODIS/VIIRS Hot Spots**  
   A sensor-harmonized burning-activity calendar that separates real fire-regime change from sensor/overpass/coverage change. This has excellent data readiness and validation potential, but less “new frontier” novelty than NISAR.

The kickoff rule is decisive:

- If, by **hour 3**, the team can obtain two scientifically comparable NISAR products for one small area, render one interpretable signal plus one control, and expose the necessary quality layers, continue with NISAR WITNESS.
- If any of those conditions fails, stop. Move immediately to EVIDENCE FRONTIER. Do not spend half the hackathon rescuing a SAR pipeline.

This recommendation is a genuine restart from all 14 challenges. It incorporates the prior POLARIS/NOVA/FRONTIER/APEX work, but it does not assume that lunar is best.

## Evidence limits

The prior chat was recoverable and supplied the accumulated objectives and earlier critiques. However, the current workspace was empty, and the referenced uploads—`NSA.txt`, `Challenges.txt`, `Finalists.txt`, `NASA-3d-model.txt`, `NASA-GITHUB.txt`, and prior POLARIS PDFs—were not attached to this task or recoverable from the thread preview. I therefore did **not** claim to read them. Their absence is an unresolved evidence gap.

Repository statements below are separated into:

- **Observed:** source, documentation, license, commit history, or test result inspected directly.
- **Claimed:** a repository author’s README or report statement, not independently reproduced.
- **Conditional:** a proposed capability that does not exist yet.

## Official 2026 rules: verified versus unresolved

| Item | Status | What the evidence supports |
|---|---|---|
| Event dates | Verified | NASA Space Apps 2026 runs **14–15 November 2026**. |
| Global project-editing window | Verified | Project submission opens **Saturday 14 November at 9:00 AM** and closes **Sunday 15 November at 11:59 PM local time**. This is about 39 hours. |
| Team size | Verified | Teams should have no more than **six** members. A two-person team is valid. |
| Start restriction | Verified through a current GO Team answer | A NASA Space Apps Global Organizing Team representative stated that participants should not start project work before **14 November**, or they risk disqualification. Research and challenge selection are distinct from building the submission; when uncertain, ask the local lead. |
| Required submission fields | Verified through the same GO Team answer | Title, high-level summary, demo link, final-project link, detailed description, NASA and other data/resources, AI/SI tool disclosure, and acceptance of terms. |
| Under 18 | Verified | The Greensboro page says minors must register with a parent/legal guardian. The official terms additionally require registration by a parent/legal guardian and accompaniment. |
| Greensboro venue | Verified | Guilford College, primarily the Early College trailers, 5608 W Friendly Ave, Greensboro. |
| Greensboro operating hours | Partly verified | The venue says “morning until evening”; exact hours were still listed as forthcoming when checked. Do not assume overnight access. |
| Greensboro local pitch | **Unresolved** | No authoritative local pitch duration, slide limit, judging time, or local submission cutoff was published on the event page when checked. |
| 30-second video or seven slides | **Current community guidance, not fully verified** | A current Space Apps GitHub answer says the demo may be a public video of at most 30 seconds or up to seven slides. The announced 2026 Project Submission Guide was not discoverable on the public Resources page at the time of checking. Treat this format as provisional until the official guide appears. |
| Exact 2026 judging weights | **Unresolved** | The recurring criteria are Impact, Creativity, Validity, Relevance, and Presentation. Exact 2026 percentages were not located, so this analysis does not invent them. |

Authoritative links: [2026 event home](https://www.spaceappschallenge.org/2026/), [Greensboro event](https://www.spaceappschallenge.org/2026/local-events/greensboro/), [official terms](https://www.spaceappschallenge.org/legal/), [GO Team submission/start answer](https://github.com/nasa/spaceapps/discussions/1858), and [current submission-format discussion](https://github.com/nasa/spaceapps/discussions/1973).

**Action at check-in:** ask the local lead, `ecgrocketry@gmail.com`, for the local pitch duration, pitch deadline, judging rubric/weights, internet policy, and whether minors need a guardian physically present for the entire venue session. Preserve the answer.

## The 17-category evaluation model

Every category is scored from **0 to 100**. Weights total 100. The first five are the official recurring NASA criteria and receive 42% of the total. The remaining categories prevent a flashy but scientifically weak concept from winning the analysis.

| Category | Weight | Meaning |
|---|---:|---|
| Impact | 9 | Consequence for a real user or decision |
| Creativity | 8 | Distinct insight, not feature count |
| Validity | 10 | Scientific correctness, bounded claims, evidence |
| Relevance | 8 | Direct answer to the challenge |
| Presentation | 7 | One-minute comprehensibility and demo strength |
| Scientific/technical depth | 6 | Meaningful method, not decorative complexity |
| NASA-data integration | 6 | NASA data drives the result rather than branding it |
| Competitive uniqueness | 8 | Separation from professional tools and likely entries |
| 39-hour feasibility | 8 | Can two people finish the scoped MVP? |
| Validation/testability | 6 | Can core claims be checked during the event? |
| Data readiness/completeness | 5 | Access, size, coverage, formats, quality |
| Reliability/offline resilience | 4 | Demo survives network/service failure |
| UX/usability | 4 | A judge can reach the “aha” moment quickly |
| Accessibility | 3 | Keyboard, contrast, captions, nonvisual alternatives |
| Explainability/provenance | 3 | Result carries source, version, assumptions, limitations |
| Long-term value | 3 | Useful beyond the weekend |
| Two-person hardware fit | 2 | Works on the stated devices without cloud dependence |

“Unbuilt” is an honest score for the strategy as it exists before a prototype. “Conditional finished” assumes only the tightly scoped MVP described here, with all hard gates passed—not a fantasy roadmap.

## Ranking all 14 official challenges

| Rank | Official challenge | Best concept found | Unbuilt | Conditional finished | Main reason it is not ranked higher |
|---:|---|---|---:|---:|---|
| 1 | Dancing with the SARs | **NISAR WITNESS**—challenge apparent change claims with quality evidence | 55 | **91.3** | High data/skill risk; score applies only after kickoff gate |
| 2 | Lunar Landing Site Navigator | **EVIDENCE FRONTIER**—decision flips and value of the next terrain observation | 64 | **90.3** | Severe incumbent/prior-art crowding |
| 3 | Harmonization of MODIS and VIIRS Hot Spots | **FIRE CONCORDANCE**—sensor-aware fire calendar with discontinuity audit | 49 | **89.2** | Less surprising frontier story; harmonization is established work |
| 4 | Be an Earth System Trend Detective! | **TREND WITNESS**—test whether a trend survives sensor, season, coverage, and baseline changes | 50 | **88.6** | Broad prompt encourages generic dashboards; must choose one variable/place |
| 5 | Identify Earth Locations that Analog Permanent Moon Base Locations and Mars | **ANALOG CONTRACT**—rank analogs by explicit mission requirement and uncertainty | 48 | **87.3** | Risk of subjective scoring and “map of similar places” sameness |
| 6 | The Earth Information Jukebox | **EARTH SCORE**—accessible, real-time sonification with causal layer explanation | 46 | **87.0** | Easy to impress locally; harder to prove global scientific distinction |
| 7 | Abandoned but not Forgotten | **OBJECT BIOGRAPHIES**—hardware-centered stories with evidence trails and classroom inquiry | 45 | **86.7** | Strong storytelling field; lower technical/scientific ceiling |
| 8 | Field Shift: Adapting Farms with NASA Data | **ROTATION COUNTERFACTUAL**—show what evidence would change a rotation recommendation | 47 | **86.6** | Agronomic validity and local ground truth are hard in 39 hours |
| 9 | Planet X and SPHEREx | **MOTION PRISM**—spectral/time motion explorer with artifact and PSF checks | 51 | **86.1** | New DR1 is powerful, but data geometry/calibration and crowded interest raise risk |
| 10 | Interplanetary Survival Guide: Martian Map | **TRAVERSE EXPLAINER**—route tradeoffs with hazard and science evidence | 47 | **85.2** | Many mature Mars maps; route optimization easily becomes arbitrary |
| 11 | Build a Junior Astronaut Mission Trainer | **FAILURE CHAIN TRAINER**—teach coupled outpost systems through explainable failures | 43 | **83.8** | Game polish dominates the weekend; NASA data can become superficial |
| 12 | Flame in Freefall | **EVIDENCE LADDER**—trace each fire-safety answer to experiments and uncertainty | 45 | **83.6** | Domain interpretation risk; “AI dashboard” is likely crowded and generic |
| 13 | Space Mission Design Game | **TRADESPACE TUTOR**—teach why one design choice breaks another | 42 | **83.0** | STK/FreeFlyer-style scope is impossible; games require content and balancing |
| 14 | Create Health Monitoring Software for Astronauts | **ESCALATION TRACE**—bounded anomaly triage with provenance | 40 | **78.8** | Medical validity, privacy, calibration, and false-alarm risk are poor hackathon fits |

### Conditional-finished category matrix

Abbreviations follow the rubric above: `Imp, Cre, Val, Rel, Pre, Sci, NASA, Unq, Fea, Tst, Dat, Rlb, UX, Acc, Prv, Lng, HW`. Each number is `/100`; the final column is the weighted result.

| Concept | Imp | Cre | Val | Rel | Pre | Sci | NASA | Unq | Fea | Tst | Dat | Rlb | UX | Acc | Prv | Lng | HW | Total |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| NISAR WITNESS, after gate | 95 | 93 | 90 | 96 | 92 | 92 | 96 | 96 | 84 | 91 | 86 | 86 | 89 | 83 | 95 | 93 | 82 | **91.3** |
| Lunar EVIDENCE FRONTIER | 88 | 88 | 90 | 97 | 93 | 94 | 98 | 83 | 84 | 93 | 90 | 88 | 92 | 84 | 96 | 91 | 88 | **90.3** |
| MODIS/VIIRS FIRE CONCORDANCE | 91 | 82 | 91 | 97 | 88 | 85 | 98 | 79 | 86 | 94 | 94 | 91 | 86 | 84 | 93 | 90 | 90 | **89.2** |
| Earth TREND WITNESS | 92 | 84 | 89 | 95 | 88 | 88 | 96 | 82 | 83 | 91 | 89 | 87 | 88 | 85 | 94 | 91 | 86 | **88.6** |
| Earth ANALOG CONTRACT | 86 | 86 | 84 | 95 | 95 | 87 | 96 | 76 | 82 | 87 | 88 | 86 | 94 | 89 | 88 | 87 | 86 | **87.3** |
| EARTH SCORE/Jukebox | 88 | 90 | 78 | 96 | 96 | 72 | 91 | 82 | 88 | 77 | 91 | 88 | 96 | 97 | 84 | 86 | 90 | **87.0** |
| Abandoned OBJECT BIOGRAPHIES | 83 | 91 | 78 | 96 | 96 | 70 | 88 | 80 | 92 | 75 | 94 | 93 | 95 | 97 | 87 | 81 | 94 | **86.7** |
| FIELD SHIFT counterfactual | 95 | 82 | 85 | 95 | 90 | 83 | 94 | 78 | 79 | 86 | 82 | 82 | 91 | 86 | 90 | 94 | 80 | **86.6** |
| SPHEREx MOTION PRISM | 86 | 91 | 84 | 95 | 94 | 91 | 98 | 85 | 68 | 84 | 80 | 74 | 92 | 83 | 88 | 89 | 70 | **86.1** |
| MARTIAN TRAVERSE EXPLAINER | 82 | 83 | 83 | 95 | 94 | 87 | 97 | 74 | 77 | 82 | 85 | 82 | 94 | 85 | 85 | 88 | 80 | **85.2** |
| JUNIOR FAILURE CHAIN | 87 | 82 | 75 | 95 | 94 | 73 | 85 | 70 | 84 | 76 | 90 | 88 | 95 | 94 | 78 | 86 | 88 | **83.8** |
| FLAME EVIDENCE LADDER | 84 | 87 | 82 | 95 | 90 | 88 | 90 | 83 | 71 | 80 | 72 | 74 | 87 | 79 | 91 | 84 | 76 | **83.6** |
| MISSION TRADESPACE TUTOR | 82 | 84 | 78 | 94 | 95 | 80 | 88 | 69 | 76 | 79 | 82 | 80 | 96 | 91 | 81 | 85 | 82 | **83.0** |
| ASTRONAUT ESCALATION TRACE | 93 | 78 | 72 | 94 | 86 | 82 | 83 | 72 | 65 | 67 | 64 | 70 | 84 | 82 | 90 | 91 | 68 | **78.8** |

These are comparative planning scores, not predictions of judges’ votes. A failed hard gate caps a concept below 70 regardless of its weighted total.

## Five adversarial passes

### Pass 1 — Official-rubric opportunity

The strongest concepts do not merely display data. They convert NASA data into a consequential, legible decision. NISAR, lunar, fire harmonization, and Earth trends lead. Health drops because validity is disproportionately hard. Games drop because presentation can be strong while NASA-data relevance remains weak.

### Pass 2 — Incumbent collision

Generic lunar visualization collapses. Moon Trek, NASA’s Celestial Mapping System, MMGIS Sightline, Cesium Moon, STK, FreeFlyer, and multiple 2026 repositories already cover 3D terrain, line of sight, sunlight, Earth visibility, communications, route analysis, or uncertainty. Only the **“what observation would resolve this decision?”** interaction remains plausibly distinctive.

SPHEREx also faces a growing field: public team pages already describe astrophysics-led tools and prebuilt backends. NISAR’s quality-aware evidence workflow has less obvious direct overlap than a before/after slider or automatic change detector.

### Pass 3 — Two-person/time attack

NISAR nearly fails. SAR files are large, Earthdata authentication is required, and an 8 GB device is unsuitable for processing. It survives only as a **one-area, one-claim, precomputed evidence product**, with data work on the Apple-silicon Mac and static web assets for the demo.

Lunar survives because data and methods are mature, but broad scope is fatal. The 3D globe, rover routing, power simulation, communications budget, AI agent, and many landing sites must be cut.

### Pass 4 — Scientific falsification

NISAR survives only if the interface can say **“not comparable”** and distinguish observed radar change from a causal claim. It must expose maturity/CRID, acquisition geometry, relevant masks, and a control. No model-generated confidence percentage is allowed without calibration.

Lunar survives only if it can reproduce simple analytic cases, cross-check ephemeris, quantify timestep/horizon convergence, and show that terrain-model choice can change—or does not change—the decision. Pixel size must not be presented as measurement certainty.

### Pass 5 — Judge-memory test

The memorable NISAR sentence is: **“Most maps show change; ours shows whether the change claim survives a challenge.”**

The memorable lunar sentence is: **“Other tools rank landing sites; ours shows what unknown terrain could reverse the choice—and what NASA should measure next.”**

Both are stronger than a feature list. NISAR has the fresher global story; lunar has the safer live demo.

## Primary product: NISAR WITNESS

### Product thesis

Radar change maps are powerful, but a bright difference is not automatically a real-world event, and even a real surface change does not establish its cause. NISAR WITNESS makes the **evidence boundary** the product.

The user sees one location and one bounded claim, for example: “This area changed between acquisition A and B.” The system then reveals a short evidence ladder:

1. Are the products comparable in maturity and processing release?
2. Are acquisition mode, geometry, polarization, and resolution compatible?
3. Is the location valid, or affected by water, shadow/layover, nodata, or other masks?
4. Does the change persist across a second channel or reasonable threshold?
5. Does a nearby control region remain stable?
6. Does any independent source support the interpretation?
7. What is observed, what is inferred, and what remains unknown?

Output is deliberately categorical:

- **Supported:** the change signal survives the implemented checks.
- **Ambiguous:** evidence conflicts or quality is insufficient.
- **Not comparable:** the selected products cannot support the claim.

It never automatically labels a cause such as landslide, deforestation, flood, or damage unless an external authoritative source supports that interpretation.

### Why now

The [ASF NISAR Data User Guide](https://nisar-docs.asf.alaska.edu/availability-overview/) says fully calibrated and validated Level 0–2 L-band products were released on **6 November 2026** for acquisitions starting **21 October 2026**. The [product guide](https://nisar-docs.asf.alaska.edu/products-overview/) provides map-ready Level 2 products and warns that differences across maturity levels can arise from processing changes rather than landscape change. That warning is precisely the kind of evidence boundary WITNESS should make visible.

The validated archive is also young. A long validated trend history does not yet exist, and validated Level 3 soil-moisture products are not yet available. Therefore the MVP should make a **pairwise, bounded claim**, not claim trend forecasting.

### Minimal architecture

This is an architecture plan, not pre-event implementation.

```text
NISAR Level-2 product(s) + metadata
             │
             ├─ small-area extraction and precomputation on M-series Mac
             │    ├─ display raster(s)
             │    ├─ difference/change layer
             │    ├─ quality/mask layer(s)
             │    └─ compact metadata/evidence JSON
             │
             └─ deterministic evidence rules
                  ├─ comparability checks
                  ├─ control-region check
                  ├─ cross-channel/threshold check
                  └─ supported / ambiguous / not comparable
                              │
                              └─ static, offline-capable web demo
                                   ├─ map and before/after view
                                   ├─ “Challenge this claim” interaction
                                   └─ downloadable evidence card
```

Use a browser map or simple canvas, not a server-heavy platform. The scientific result is precomputed for one area so the live interaction is instant and offline. The evidence engine must be deterministic. Local Ollama is optional only for turning the structured evidence card into plain language; if used, it must cite the fields it paraphrases and must not produce the verdict.

### Kickoff data gate

Continue only if all are true by hour 3:

- Earthdata/ASF access works.
- A small area has two appropriate products or one pair product with compatible dates.
- The same maturity and processing lineage can be demonstrated, or the mismatch itself is the intentionally demonstrated “not comparable” case.
- At least one quality layer—such as coherence, mask, number of looks, connected component, or uncertainty appropriate to the selected product—is available and understood.
- One stable control area can be identified.
- A compact raster and metadata bundle can run without the venue network.

Recommended product choice:

- Prefer a map-ready **GCOV** amplitude/backscatter comparison for the simplest credible MVP, or an existing **GUNW/GOFF** pair only if the relevant quality fields and interpretation are understood.
- Do not generate a full interferometric product from raw data during the hackathon.
- Do not mix BETA, PROVISIONAL, and VALIDATED products in a claimed physical comparison unless the entire point is to demonstrate why the comparison is invalid.

### Validation plan

1. **Metadata validation:** product maturity, CRID, date, mode, orbit direction, polarization, projection, and pixel spacing are recorded.
2. **No-change control:** a nearby stable area should remain below the chosen change criterion. If it does not, the result becomes ambiguous.
3. **Threshold sensitivity:** show whether the conclusion survives at least three defensible thresholds; do not hide a threshold chosen after seeing the answer.
4. **Cross-channel check:** where available, test whether the signal persists in another polarization or compatible layer.
5. **Mask test:** verify that excluded water/shadow/layover/nodata pixels cannot become evidence.
6. **Synthetic test:** inject a known artificial patch into a copy of the raster to confirm the pipeline detects what it says it detects. Label this as a software test, not scientific validation.
7. **External interpretation:** if claiming an event type, cite an authoritative event record or independent dataset. Otherwise say only “surface/radar response changed.”
8. **Reproducibility:** export source identifiers, timestamps, rule version, thresholds, and result.

### Originality benchmark

The mathematical ingredients—SAR change detection, coherence, quality masks, confidence, and provenance—are prior art. Do not claim invention of them. The distinctive contribution is the **judge-visible workflow that tries to falsify a specific change claim before presenting it as knowledge**.

During the event, benchmark the finished tool against ASF Vertex, NASA Worldview, a standard before/after slider, and at least one public SAR-change notebook. Score each on this seven-part test:

1. Processing maturity/release is visible.
2. Acquisition comparability is checked.
3. Quality/mask evidence is shown next to the claim.
4. A control region is tested.
5. A second channel or sensitivity test can challenge the result.
6. Observation is separated from causal interpretation.
7. A reproducible evidence record can be exported.

Target: WITNESS must achieve **7/7**. If an incumbent already achieves six or seven, narrow or change the differentiation claim. Do not publish guessed incumbent scores as facts.

### What to cut

- Global coverage
- Live processing of arbitrary uploads
- Deep neural change detection
- Event forecasting
- Automated disaster classification
- Accounts, collaboration, and cloud infrastructure
- A conversational AI as the main interface
- More than one primary case and one control

## Lunar fallback: EVIDENCE FRONTIER

### Product thesis

At the lunar south pole, the key uncertainty is often not the Sun or Earth ephemeris; it is the local and distant terrain that defines the horizon. EVIDENCE FRONTIER asks:

> Does the site/date decision survive plausible terrain alternatives, and which unresolved horizon sector is worth measuring next?

The product compares only two sites and one mission interval. It shows:

- Sun and Earth clearance above the terrain horizon over time.
- The decision under at least two terrain representations or an uncertainty ensemble.
- The first counterexample interval that violates a mission rule.
- A polar **decision-critical observation map** showing which azimuth/range sector contributes most to uncertainty in the site ranking.
- A compact evidence certificate with DEM, frame, ephemeris, timestep, assumptions, and limitations.

### Why the novelty bar is high

The following capabilities already exist:

| Incumbent | Observed or claimed capability | Consequence for the entry |
|---|---|---|
| [NASA MMGIS Sightline](https://nasa-ammos.github.io/MMGIS/tools/sightline) | Terrain ray casting, visibility over time, Sun/Earth tracking, SPICE support, 360-degree horizon functions | A sightline timeline is not novel. Screen extent and DEM handling must be understood. |
| [NASA Moon Trek](https://trek.nasa.gov/moon/) | Thousands of lunar layers, 3D, lighting, slope, line-of-sight and mission-analysis functions | A generic lunar map is not novel. |
| [NASA Celestial Mapping System](https://celestial.arc.nasa.gov/) | 3D terrain, sunlight, LOS, equipment placement, traverse planning | Equipment/terrain views are professional prior art. |
| [Cesium Moon](https://cesium.com/platform/cesium-ion/content/cesium-moon/) | High-quality global 3D lunar terrain tiles, especially polar detail | Use only as a visualization substrate; 3D itself earns little uniqueness. |
| [STK](https://www.ansys.com/content/dam/amp/2023/november/asset-creation/stk-capabilities.pdf) | Access, obstruction, coverage, figures of merit | Do not imitate a broad mission-analysis suite. |
| [FreeFlyer](https://ai-solutions.com/_help_Files/working_with_terrain.htm) | Terrain-aware line of sight, visibility periods, optimization and mission analysis | Same conclusion: focus on an unanswered decision, not feature breadth. |
| [NAIF SPICE](https://naif.jpl.nasa.gov/naif/) | Authoritative observation geometry and event finding | SPICE is an engine, not a differentiated product. |
| [LUNAR//OPS](https://github.com/RootVandal/lunar-ops) | 1,440-bin horizons, multiple sites, constraint margins, landing windows, robustness analysis | “Robust windows” and per-constraint margins are already claimed. README states it was built before the hackathon and is not a submission. |
| [lunar-horizon-wheel](https://github.com/NetRunnerXD/lunar-horizon-wheel) | Finite Sun, DSN, power/link ideas, DEM sensitivity, extensive method/validation presentation | Horizon wheels and DEM sensitivity are already claimed and demonstrated. |
| [PolarWindow](https://github.com/MdAhbab/PolarWindow) | Large multi-service lunar mission-planning scope, uncertainty, tests, CLPS validation | Feature count and test count cannot be the differentiator. |
| [LunaMission](https://github.com/Softsasi/LunaMission) | “Aerospace-grade” architecture, many tests, multi-resolution terrain and Cesium claims | Treat as prior-art claims until independently run. |
| [CLPS Moon Browser/Lunar Horizon](https://github.com/localizedprojects/CLPS-MOON-BROWSER) | Whole-Moon browser and mobile-oriented experience | Whole-Moon reach is not a useful two-person goal. |

All five independent 2026 lunar repositories inspected use permissive Apache-2.0 or MIT licenses. Their GitHub issue trackers showed zero open issues when checked; that is not evidence of correctness. MMGIS is Apache-2.0 and had an active mature issue/PR history.

Commit history shows several “2026 Space Apps” repositories contain substantial work dated before the official start. The GO Team’s current rule says project work should not begin before 14 November. Therefore these repositories are best treated as **prior art and technical benchmarks**, not presumed eligible entries. This report does not accuse any team or decide eligibility.

### Directly verified repository checks

- `lunar-horizon-wheel`: package install completed; **49/49 frontend tests passed** and a production build succeeded. The build warned that one 3D chunk exceeded 500 kB. This verifies the checked software tests/build only—not the published NASA-data numerical comparisons.
- `lunar-ops`: **4 solver tests passed**. Its scientific validation suite could not be collected in the available environment because optional `tifffile` and `spiceypy` dependencies were absent. Its astronomy/terrain claims remain unreplicated here.
- `PolarWindow`: documentation explicitly preserves a failed scientific gate: a 500 m Griffin-1 viewshed comparison reports **87.70% agreement** against a 99% requirement, with 31 conflicting targets and unresolved cause. Its handoff also reports a recent end-to-end run with failures. This is unusually honest documentation and proves why raw test totals are misleading.
- `LunaMission`: the requested Bun runtime was not installed, so its claimed 1,500+ tests were not run.

### Data plan

- [PGDA product 78](https://pgda.gsfc.nasa.gov/products/78): 5 m LOLA DEM products, uncertainty layers, and terrain clones for selected regions.
- [PGDA product 104](https://pgda.gsfc.nasa.gov/products/104): enhanced 5 m/pixel shape-from-shading terrain over the original Artemis III regions, with coverage and quality context.
- [PGDA product 90](https://pgda.gsfc.nasa.gov/products/90): south-polar cloud-optimized GeoTIFF products in a documented lunar frame.
- [PGDA product 106](https://pgda.gsfc.nasa.gov/products/106): a new diffusion/Schrödinger-bridge topography research product. Use only as an experimental comparison, never as unquestioned ground truth.
- [JPL Horizons](https://ssd.jpl.nasa.gov/horizons/) and [NAIF SPICE](https://naif.jpl.nasa.gov/naif/) for independent geometry cross-checks.
- [NASA SVS polar illumination](https://svs.gsfc.nasa.gov/5027/) for visual/epoch spot checks.
- [NASA Moon GLB models](https://svs.gsfc.nasa.gov/14959/) only for a lightweight visual, with their documented pole artifact acknowledged.

### Validation plan

1. Flat surface and single-ridge analytic controls.
2. SPICE position/elevation compared with Horizons at several timestamps.
3. Timestep convergence: demonstrate the decision is stable when the step is reduced.
4. Horizon-bin convergence: demonstrate stability as angular sampling changes.
5. Terrain sensitivity: compare LOLA and SfS/clone alternatives without calling either perfect truth.
6. Frame/projection audit: record MOON_ME frame/version and coordinates explicitly.
7. One SVS image/time spot check, labeled as a visual check rather than independent numerical proof.
8. No uncalibrated “probability of success.” Report bounds, scenarios, or decision flips.

### True differentiator and prior-art boundary

Robust optimization, sensitivity analysis, value-of-information, and active measurement planning all exist in engineering and research. The project should **not** claim to invent those methods. The defensible originality claim is narrower:

> EVIDENCE FRONTIER applies decision-focused value-of-information to lunar horizon uncertainty in a judge-visible workflow: it identifies the terrain sector whose improved measurement is most likely to settle a specific landing-site/date choice.

Benchmark against the lunar incumbents with five measurable questions:

1. Can the tool show that a ranking flips under an alternate terrain model?
2. Can it identify the first decision-violating counterexample interval?
3. Can it rank terrain sectors by expected decision relevance?
4. Can it export the assumptions and data lineage?
5. Can a nonexpert explain the result in one sentence?

If sector ranking is not working by hour 12, the lunar entry loses its competitive uniqueness. Cut 3D and all secondary features before cutting this interaction.

## Why not lead with SPHEREx?

SPHEREx is the most serious alternative after NISAR and lunar. [IRSA released DR1 in November 2026](https://irsa.ipac.caltech.edu/data/SPHEREx/docs/overview_dr1.html), including reprocessed spectral images and a 102-channel all-sky cube. NASA/IRSA also provides weekly quick releases, programmatic access, notebooks, mosaic tools, calibration documentation, and provenance fields.

That creates an excellent frontier story—but a difficult weekend:

- Motion must be distinguished from PSF, alignment, detector, cadence, and processing differences.
- Infrared FITS/WCS data and 102 channels raise preprocessing and explanation cost.
- Public team pages already include astrophysics specialists and teams claiming completed backends before the event.
- A simple blink comparator is likely common; a credible motion detector needs known-object validation and artifact rejection.

If the team already has strong Astropy/FITS/WCS experience and can access a clean moving-object sequence immediately after kickoff, SPHEREx can replace MODIS/VIIRS as the third choice. Otherwise it is too risky for two people.

## 2025 winner pattern

NASA’s [2025 global-winner announcement](https://www.nasa.gov/learning-resources/stem-engagement-at-nasa/nasa-announces-2025-international-space-apps-challenge-global-winners/) and [winner gallery](https://www.spaceappschallenge.org/2025/awards/global-winners/) show a recurring pattern across projects such as SpaceGenes+, Resonant Exoplanets, SkySense, Astro Sweepers, PureFlow, HerCode Space, Gaia+LEO, Zumorroda-X, and QUEÑARIS:

- A concrete beneficiary and decision are visible.
- NASA data is central, but the story is understandable without technical jargon.
- The project has one strong interaction or causal story, not only a dashboard.
- Systems thinking and real-world impact matter as much as algorithmic novelty.
- A polished explanation can win alongside substantial technical depth.

The [45 global finalists](https://www.spaceappschallenge.org/2025/awards/global-finalists/) also show that multiple strong projects can emerge from the same challenge. Popularity alone does not eliminate a challenge; sameness does.

This is why WITNESS is framed around a decision—whether evidence supports a change claim—and why the lunar fallback is framed around what measurement resolves a decision.

## Two-person, three-device operating plan

### Device allocation

| Device | Primary role | Avoid |
|---|---|---|
| Apple-silicon MacBook | Data extraction, scientific checks, build, local service if unavoidable, final integration | Running a large local model while processing rasters; uncontrolled multi-gigabyte workflows |
| 2017 Intel MacBook Pro, 16 GB | UI work, source control, slides/video, independent browser and accessibility QA | Heavy SAR or high-resolution terrain computation |
| Surface Pro 8, 8 GB | Offline demo mirror, touchscreen/pitch rehearsal, Windows compatibility, submission backup | Development server, large datasets, model inference |

Ollama is a liability unless it serves a narrow, optional role. The MVP must remain complete with Ollama turned off. If used, choose a small model and generate only a constrained plain-language summary from structured evidence. Record the model/version and disclose it.

### 39-hour priorities

The global web window is approximately 39 hours. Greensboro’s physical venue hours are shorter and not yet published, so assume that late-night work happens elsewhere and keep all data local.

| Time | Person A: science/data | Person B: product/story | Shared gate |
|---|---|---|---|
| H0–H1 | Re-read official challenge/resource tab; verify data definitions | Confirm local rules, submission fields, pitch deadline | Challenge and rule lock |
| H1–H3 | Run NISAR data gate on one area/pair | Sketch one-screen interaction and evidence card | **Continue NISAR or pivot lunar** |
| H3–H8 | Produce one truthful end-to-end result and control | Build the thinnest visible flow with static placeholders | One-click “aha” works |
| H8–H14 | Add comparability, quality, sensitivity rules | Implement “Challenge this claim”; provenance display | Core differentiator works |
| H14–H20 | Run validation tests; freeze scientific claims | Improve map, state transitions, keyboard/contrast | Validity gate passed |
| H20–H27 | Prepare offline data bundle and limitations | Polish responsive UI; create diagrams/captions | Demo works on all three devices |
| H27–H31 | Write methods/data citations | Draft provisional seven slides or 30-second demo | Story says problem → evidence → impact |
| H31–H35 | Re-run checks from clean start | Record/rehearse; verify every public link privately | Submission candidate frozen |
| H35–H37 | Fix only critical defects | Submit local materials and global draft | No new features |
| H37–H39 | Independent link/device check | Final submission and screenshots | Submit early; preserve receipt |

### Kill criteria

**NISAR:**

- No compatible data pair or pair product by H3 → pivot.
- No interpretable signal **and** stable control by H6 → pivot.
- Core interaction takes more than a few seconds without network by H8 → precompute or pivot.
- Quality layer cannot be explained accurately by H10 → simplify product choice or pivot.
- Event cause lacks an authoritative source by H12 → remove the cause; show only observed change.
- Evidence workflow scores below 6/7 on the originality benchmark by H14 → narrow differentiation or pivot.

**Lunar:**

- DEM/frame alignment unresolved by H4 → use one documented dataset or stop.
- No independent ephemeris check by H8 → do not make precision claims.
- No decision flip, stable no-flip result, or meaningful sector ranking by H12 → drop 3D and focus solely on the falsification result.
- Core result cannot be reproduced from a clean start by H20 → replace live computation with a transparent precomputed case.

**Universal:**

- No end-to-end demo by H8 → cut scope in half.
- No defensible validation result by H20 → stop adding features.
- Submission package not frozen by H35 → submit the stable version; do not risk deadline failure.

## Hard gates that override scores

1. **Rules gate:** no pre-start project implementation; all sources and AI tools disclosed.
2. **Data gate:** actual NASA data, identifiers, and lineage are present; no invented demo output.
3. **Validity gate:** the main result has a control or independent check and can return “unknown/ambiguous.”
4. **Novelty gate:** the product’s defining interaction is absent from the benchmarked incumbents or materially improves it.
5. **Demo gate:** a judge reaches the differentiating result in under 60 seconds on the offline Surface.
6. **Submission gate:** all public links work in a private browser and the required fields are complete before the deadline.

A failed rules, data, or validity gate is disqualifying for this strategy. A failed novelty or demo gate caps the likely global score regardless of technical effort.

## Judge narrative

### NISAR WITNESS: 30-second narrative

> A satellite difference map can look certain even when its products, geometry, or quality do not support the claim. NISAR WITNESS lets a responder challenge one apparent surface change. It checks comparable NISAR data, masks and quality evidence, a control area, and sensitivity—then says supported, ambiguous, or not comparable. We do not ask AI to guess what happened. We show exactly what the NASA data proves, what it suggests, and what remains unknown.

### Provisional seven-slide structure

Use this only if the official 2026 guide confirms the seven-slide option.

1. **The costly mistake:** a confident-looking change map can mix observation, processing difference, and interpretation.
2. **The user:** an analyst or local responder needs to know whether a claim is ready to act on.
3. **The moment:** one location, two dates, one apparent change.
4. **The challenge:** press “Challenge this claim”; reveal comparability, mask/quality, control, and sensitivity.
5. **The verdict:** supported/ambiguous/not comparable, with an evidence record.
6. **Validity:** NASA product lineage, control test, sensitivity test, limitation, and independent interpretation source.
7. **Impact and frontier:** turn new NISAR data from imagery into accountable evidence; extend later to other regions and sensors.

### Lunar fallback: 30-second narrative

> At the lunar south pole, a few meters of uncertain terrain can change months of sunlight and Earth visibility. Existing tools predict windows; EVIDENCE FRONTIER tries to break the decision. It compares terrain evidence, finds the first interval that overturns a site choice, and points to the horizon sector NASA should measure next. The result is not just the best-looking site—it is a decision that shows what could make it wrong.

### Live-pitch rule

Do not open with architecture, AI, 3D, or the number of datasets. Open with the wrong decision, perform the defining interaction, show one validation result, then explain impact. If the local pitch is three minutes, spend roughly half on the live evidence interaction. If the format differs, preserve the same order.

## Source-linked research appendix

### Official event and judging context

- [NASA Space Apps 2026 home and submission window](https://www.spaceappschallenge.org/2026/)
- [Official 2026 challenge index](https://www.spaceappschallenge.org/2026/challenges/)
- [Greensboro event page](https://www.spaceappschallenge.org/2026/local-events/greensboro/)
- [Official terms](https://www.spaceappschallenge.org/legal/)
- [GO Team answer on start restriction and submission fields](https://github.com/nasa/spaceapps/discussions/1858)
- [Current community answer on demo format](https://github.com/nasa/spaceapps/discussions/1973)
- [2025 global winners](https://www.spaceappschallenge.org/2025/awards/global-winners/)
- [NASA summary of 2025 winners](https://www.nasa.gov/learning-resources/stem-engagement-at-nasa/nasa-announces-2025-international-space-apps-challenge-global-winners/)
- [2025 global finalists](https://www.spaceappschallenge.org/2025/awards/global-finalists/)

### NISAR

- [Available NISAR data and release timeline](https://nisar-docs.asf.alaska.edu/availability-overview/)
- [NISAR product levels, fields, and maturity warning](https://nisar-docs.asf.alaska.edu/products-overview/)
- [Current validated-product known issues](https://nisar-docs.asf.alaska.edu/nisar-known-issues/)
- [NISAR data access overview](https://nisar-docs.asf.alaska.edu/access-overview/)
- [ASF Vertex search](https://search.asf.alaska.edu/)

### SPHEREx

- [SPHEREx DR1 overview](https://irsa.ipac.caltech.edu/data/SPHEREx/docs/overview_dr1.html)
- [IRSA SPHEREx mission archive](https://irsa.ipac.caltech.edu/Missions/spherex.html)
- [SPHEREx archive user guide](https://irsa.ipac.caltech.edu/spherex-archive-documentation/)
- [NASA explanation of weekly public data and 102 wavelengths](https://science.nasa.gov/open-science/spherex-universe-map/)
- [Documented corrected PSF header issue](https://irsa.ipac.caltech.edu/data/SPHEREx/docs/psfhdrerr.html)

### Lunar data and mission software

- [PGDA product 78: high-resolution LOLA, uncertainty and clones](https://pgda.gsfc.nasa.gov/products/78)
- [PGDA product 104: enhanced shape-from-shading terrain](https://pgda.gsfc.nasa.gov/products/104)
- [PGDA product 90: south-polar cloud-optimized products](https://pgda.gsfc.nasa.gov/products/90)
- [PGDA product 106: deep-learning topography research product](https://pgda.gsfc.nasa.gov/products/106)
- [NASA SVS lunar south-pole illumination 2025–2028](https://svs.gsfc.nasa.gov/5027/)
- [NASA Moon GLB models](https://svs.gsfc.nasa.gov/14959/)
- [JPL Horizons](https://ssd.jpl.nasa.gov/horizons/)
- [NAIF SPICE](https://naif.jpl.nasa.gov/naif/)
- [NASA Moon Trek](https://trek.nasa.gov/moon/)
- [NASA Celestial Mapping System](https://celestial.arc.nasa.gov/)
- [NASA MMGIS Sightline documentation](https://nasa-ammos.github.io/MMGIS/tools/sightline)
- [MMGIS source, Apache-2.0](https://github.com/NASA-AMMOS/MMGIS)
- [Cesium Moon](https://cesium.com/platform/cesium-ion/content/cesium-moon/)
- [STK capability overview](https://www.ansys.com/content/dam/amp/2023/november/asset-creation/stk-capabilities.pdf)
- [FreeFlyer terrain visibility documentation](https://ai-solutions.com/_help_Files/working_with_terrain.htm)

### Lunar prior-art repositories inspected

- [LUNAR//OPS](https://github.com/RootVandal/lunar-ops) — Apache-2.0
- [PolarWindow](https://github.com/MdAhbab/PolarWindow) — Apache-2.0
- [lunar-horizon-wheel](https://github.com/NetRunnerXD/lunar-horizon-wheel) — MIT
- [LunaMission](https://github.com/Softsasi/LunaMission) — MIT
- [CLPS Moon Browser/Lunar Horizon](https://github.com/localizedprojects/CLPS-MOON-BROWSER) — MIT
- [MMGIS Sightline pull request](https://github.com/NASA-AMMOS/MMGIS/pull/993) and [multi-DEM/native-resolution update](https://github.com/NASA-AMMOS/MMGIS/pull/1016)

## Unresolved questions before kickoff

1. Where are the official 2026 Project Submission and Judging Guides, and do they confirm 30 seconds/seven slides and the five criteria without new requirements?
2. What are Greensboro’s exact opening hours, local pitch time/length, local submission cutoff, and judging weights?
3. Does the local event require a parent/guardian to remain on site continuously for an under-18 participant, and are there separate Guilford College forms?
4. Which NISAR location has two compatible, reasonably sized products that can support one clear claim at 9:00 AM without prior project work?
5. Does the team already have working Earthdata credentials, enough free disk space, adapters/chargers, and a local copy of needed general-purpose tools?
6. What exact Apple-silicon model, RAM, and free storage are available?
7. Will the local organizers interpret generic preexisting personal libraries/templates differently from project work? Obtain a written answer before reuse.
8. Can the missing source files and prior POLARIS PDFs be attached after the event starts for an additional audit without contaminating pre-start compliance?

## Final recommendation in one line

**At 9:00 AM, give NISAR WITNESS three hours to prove it has comparable data, one truthful change, one control, and visible quality evidence; if it does, pursue the highest-upside global entry—if it does not, pivot immediately to lunar EVIDENCE FRONTIER and win on decision falsification rather than another horizon dashboard.**
