# POLARIS X — more datasets, live feeds and AI APIs (research note, Claude, 15 Nov 2026, 22:20 ET)
*Post-submission roadmap. Check each source's licence or terms and current availability before building on it. All live feeds are display-and-context only; the solver's NASA/JPL pipeline stays the numerical authority.*

## A. Datasets that would directly improve the science

| Dataset | What it adds to POLARIS | Fixes which limit | Access |
|---|---|---|---|
| **LOLA RDR (raw laser shots)** | Where LOLA actually measured vs where the 5 m DEM interpolates; shot density near each RoI and crest | **LOLA vs SfS crest difference** (test "interpolation flattens crests"); per-point error model for far-field uncertainty | PDS Geosciences ODE "LOLA RDR Query" tool (lat/lon/time search, CSV/shapefile/binned output) and the ODE REST/GDS API (oderest.rsl.wustl.edu) |
| **LROC NAC DTMs + NAC images** (PDS; ODE footprint search) | Independent stereo terrain at ~2–5 m where it exists; more NAC frames for the observation check | Hero-point observation check; a third terrain product besides LOLA and SfS | ODE product search / REST; LROC RDR site |
| **ShadowCam (KPLO)** | Images inside permanently shadowed regions at ~1.7 m/px; derived mosaics and DTMs | PSR context, ice-access science and traverse targets; shadowed-terrain DTMs where LOLA is sparse | PDS releases every ~3 months (latest Aug 2026); COG products; ODE "KPLO ShadowCam" bundle `urn:nasa:pds:kplo-shadowcam` |
| **SLDEM2015 (LOLA + Kaguya)** | Independent regional DEM for the far field | Structural member of the far-field envelope | ODE / LOLA GDR pages |
| **LOLA roughness and Hurst-exponent maps (RMHE)** | Sub-pixel roughness | Terrain-safety layer; footprint uncertainty | LOLA PDS (LRO-L-LOLA-8-GDR) |
| **Diviner (temperature, rock abundance)** | Observed surface temperatures; rock abundance for hazard | Thermal model validation; landing hazard | ODE Diviner RDR query tool; PDS Geosciences |
| **M3 surface-ice detections (Li et al. 2018, PNAS)**, LAMP UV ratio, LEND hydrogen | Where ice is: science value and traverse destination | "Distance to ice" criterion; Pareto science axis | Published data products (PDS / paper supplements) |
| **Chandrayaan-2 (OHRC ~30 cm, DFSAR, TMC-2 DEM)** | Very high-resolution images and DEMs; radar of PSRs | Boulder/hazard mapping; another DEM | ISRO PRADAN portal (ISSDC), PDS4 format; registration required |
| **LCRNS Reference Constellation 3.1 states** | Relay satellite positions | Link availability beyond direct-to-Earth (5D prompt Phase 4) | NASA NTRS 20250002698 white paper |
| **NASA Moon Trek WMTS** | Ready map tiles (mosaics, slope, illumination layers) for the polar map and 3D view | Display only: richer basemaps without hosting rasters | Trek WMTS (catalog at trek.nasa.gov/tiles/apidoc, south-polar projection) |
| **Artemis III candidate regions** | Official region outlines to overlay | Relevance to the challenge | NASA (13 → 9 regions; LPSC 2026 update) |

**Highest value first:**
1. LOLA RDR shot density. It cheaply tests the open LOLA-vs-SfS question.
2. ShadowCam and NAC DTMs. They are independent terrain and imagery near the hero point.
3. Diviner. It validates a thermal model if we build one.
4. Moon Trek WMTS. It is a quick visual win.

## B. Live and near-real-time feeds (a "Now" mode)

| Feed | What "Now" would show | Notes |
|---|---|---|
| **JPL Horizons API** (have) | Sun and Earth az/el at each site *right now*, against the stored horizon mask: "Site04 RoI 3 is lit and has Earth in view at this moment" | Our own pipeline; just call it for the current time |
| **NOAA SWPC JSON** (`services.swpc.noaa.gov/json/goes/`) | GOES ≥10/≥100 MeV proton flux and alert status: "solar radiation storm in progress: no EVA" | 5-minute data; SWPC's proton event threshold is 10 pfu at ≥10 MeV. Relevant to crew EVA planning, the only truly live hazard for a surface mission |
| **NASA DONKI** (CCMC) | Recent CMEs, solar flares, SEP events and notifications | Webservice at kauai.ccmc.gsfc.nasa.gov/DONKI/WS needs no key; api.nasa.gov needs a free key and has been reported flaky |
| **DSN Now** (eyes.nasa.gov/apps/dsn-now) | Which DSN dishes are tracking what right now, next to our "which complex sees the Moon" computation | Real-time feed updated every ~5 s. JPL currently says the site is being updated and is unavailable, so build with a fallback |
| **LRO / ShadowCam PDS release calendars** | "New data available" badges | Quarterly; not real time |

Rule for live data: show it in a separate, clearly labelled **LIVE · CONTEXT** panel with the fetch time and source. Never let it change a stored result. Cache the last good value and say "stale" when the feed is down (DSN Now has outages).

## C. AI APIs (Google $300 credit, Gemini free tier, others)

**What the Google credit actually covers**
- The $300 Google Cloud Free Trial credit is for new customers and valid 90 days. Google's documentation says it **cannot** pay for the Gemini Developer API in AI Studio; it does work through **Vertex AI** (aiplatform.googleapis.com). It also can't pay for partner "model-as-a-service" APIs.
- The Gemini API (AI Studio) has a separate free tier with rate limits shown per project in AI Studio. Google restricted the free tier during 2026 (Pro models are paid-only), so check current limits before relying on them.
- Practical setup:
  - call Gemini through Vertex AI with the trial project (`GOOGLE_GENAI_USE_VERTEXAI=True` in the google-genai SDK);
  - set a billing budget alert;
  - keep the key server-side, on Cloud Run (always-free tier) or a local proxy;
  - never ship a key in the static site.
- Alternatives: the Anthropic API (Claude) or OpenAI for the same patterns.

**AI uses that fit POLARIS's rules** (numbers come only from the solver; every AI output labelled AI-GENERATED; disclosed under the Space Apps "Use of AI" rules)
1. **Mission-planner chat with tool use** (highest value).
   - Gemini or Claude function calling over the existing `tools/polaris_solver --tool-spec` and the scenario-cube slicer. For example: "Which of the four sites keeps a 1 m mast lit for a Dec 2026 start on at least 18 of 20 maps?" The model calls tools, and the answer quotes only tool outputs.
   - Add a **number-grounding check**: every number in the reply must appear in that turn's tool results, or the reply is blocked or flagged. This keeps "AI" from becoming a source of numbers.
2. **Literature-grounded evidence panel.** Retrieval over NTRS/PDS papers (Barker 2021, Mazarico 2011, Gläser 2014/2018, LCRNS docs) with citations, so "why should I trust this?" answers link to the paper paragraph. Use Vertex AI Search (covered by the trial credit) or embeddings plus your own index.
3. **Vision pre-screening, never as truth.**
   - Gemini vision to *suggest* candidate NAC or ShadowCam frames that cover a site, or to flag boulders or hazards for a human to check.
   - Outputs are candidates feeding the pre-registered validation protocol, labelled AI-SUGGESTED, with precision and recall measured on a hand-labelled set before any use.
4. **Accessibility and outreach.**
   - Alt text, captions and translations, generated from the fixed-template narrator (which stays the authority).
   - Plain-language explainers on request.
5. **Ops assistant for the team.** Summarise DONKI/SWPC alerts into "what this means for an EVA today", with the raw alert linked.

**Do not**
- let a model produce or "estimate" visibility percentages;
- use generated imagery as terrain or as evidence;
- put API keys in the browser.

AI images or video need a visible watermark under the Space Apps rules.

## D. Suggested order (after submission)
1. LOLA RDR shot-density test (1 day). Biggest science payoff.
2. "Now" mode: Horizons current time + SWPC proton status + DONKI (1 day).
3. Mission-planner chat over the solver tool-spec with the number-grounding check, on Vertex AI (2 days).
4. ShadowCam / NAC DTM search for the hero point (1–2 days).
5. Moon Trek WMTS basemaps (0.5 day).
6. Diviner + M3 ice layers for the Pareto and traverse work (2–3 days).

## Sources
- LOLA RDR Query / ODE REST: https://ode.rsl.wustl.edu/moon/lrololadataPointSearch.aspx ; https://ode.rsl.wustl.edu/mars/pagehelp/Content/Additional_Resources/ODE_REST_API.htm ; LOLA product list (SLDEM, RMHE): https://ode.rsl.wustl.edu/mars/pagehelp/Content/Missions_Instruments/LRO/LOLA/Intro.htm
- ShadowCam: https://shadowcam.im-ldi.com/ ; https://ode.rsl.wustl.edu/Moon/pagehelp/Content/Missions_Instruments/Korea%20Pathfinder%20Lunar%20Orbiter%20(KPLO)/SHADOWCAM/Intro.htm
- Moon Trek WMTS: https://trek.nasa.gov/tiles/apidoc/trekAPI.html?body=moon
- M3 ice (Li et al. 2018): https://escholarship.org/content/qt2s7392x8/qt2s7392x8.pdf
- Chandrayaan-2 data (PRADAN/ISSDC): https://www.isro.gov.in/CHANDRAAYAN.html
- NOAA SWPC GOES proton flux + JSON: https://www.spaceweather.gov/products/goes-proton-flux ; https://services.swpc.noaa.gov/json/goes/
- DONKI: https://ccmc.gsfc.nasa.gov/tools/DONKI
- DSN Now: https://eyes.nasa.gov/apps/dsn-now/dsn.html
- Google Cloud Free Trial terms: https://docs.cloud.google.com/free ; Gemini API pricing/free tier: https://ai.google.dev/gemini-api/docs/pricing
