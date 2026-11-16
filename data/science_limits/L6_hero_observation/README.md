# L6 — Observation check at the hero point (Site04 RoI 3 lander point)

**Label:** PILOT · SOURCE-BASED · UNVALIDATED. **The hero point stays UNCHECKED.**

**Question.** Is there any observation that covers the Site04 RoI 3 lander point (−89.78012°, −156.32023° E) and its
controlling rise 15–17 m away?

**Method (metadata only — no pixels read).** (1) Zenodo doi:10.5281/zenodo.17954508 (GSFC SfS + orthorectified NAC maps,
13 Artemis regions): central directories listed by HTTP range reads; each region's `GLDELEV_005.tif` bounds read from the
GeoTIFF header via `/vsizip//vsicurl/`; region 6 (nearest) NAC map bounds likewise. (2) PDS ODE REST (live2), footprint
intersection with a ~90 m box around the point, for LROC NAC CDRs (`CDRNAC4`), NAC DTMs (`SDNDTM`) and ROI mosaics.
`python -m science.limits.l6_search` summarises the committed listings.

**Result.**
- None of the 13 GSFC SfS regions contains the point. Nearest: region 6 "Connecting Ridge", whose extent ends **322 m**
  short (x = −3000 m vs −2677.8 m). So the GSFC orthorectified NAC product used by NAC v1/v2 does not cover it.
- PDS ODE lists **234 LROC NAC calibrated frames** (2009–2024, mostly 2010) whose footprints intersect the point's box,
  most with incidence 87–93° (Sun near the horizon). They are raw; using them needs orthorectification onto an
  independent DEM (base protocol, qualifying observation 2).
- PDS ODE lists **one LROC NAC stereo DTM**, `NAC_DTM_ESALL_SR12` (ASU, 2 m/px, Shackleton rim ESA lander site), whose
  extent contains the point. It can test the rise's height relative to the point (amendment A1, test T).

**Protocol.** `tools/validation/hero/HERO_PROTOCOL.md` (frozen, SHA-256 81d12824…) and `HERO_PROTOCOL_A1.md` (frozen before
any pixel, 9ab36bcc…). No result yet: running them needs the DTM and frame downloads, held until the submission is
pushed. Results from region 6, regions 8/9 or other areas are **not** used as a stand-in for this point.

**What it does not show.** Footprint intersection is ODE's polygon test; a frame may still have the point in shadow,
saturated or off the usable edge. Incidence is at the frame centre.
