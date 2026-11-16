# HERO_PROTOCOL amendment A1 (frozen before any pixel was read)

Written 15 Nov 2026 ~22:20 EST, after the L6 search found (metadata only, via PDS ODE and the Zenodo archive listing)
that observations of the lander point exist in **raw / non-GSFC** form, and **before any pixel or height value** of them
was downloaded or read. Base protocol: `HERO_PROTOCOL.md` (SHA-256 81d12824…770684). Hash of this file in
`HERO_PROTOCOL_A1.sha256`. Nothing in the base protocol is changed; A1 adds one test and pins the image list.

## What the search found (metadata only)
- No NASA GSFC orthorectified NAC map or SfS DEM (Bertone et al. 2026, 13 regions) contains P0; the nearest, region 6
  "Connecting Ridge", ends 322 m from P0 (its x-extent stops at −3000 m; P0 is at x = −2677.8 m).
- PDS ODE: 234 LROC NAC CDR frames (CDRNAC4) whose footprints intersect a ~90 m box around P0, 2009–2024, incidence
  86.7°–92.8° at frame centre. These need orthorectification (qualifying observation 2 of the base protocol). The list is
  pinned in `data/science_limits/L6_hero_observation/ode_cdrnac_p0.json`.
- PDS ODE: one LROC NAC stereo DTM, `NAC_DTM_ESALL_SR12.TIF` (Arizona State University, 2 m/px, "Shackleton Crater
  Rim Potential Landing Site for ESA Lunar Lander"), extent −89.84° to −89.63°, 180.8°–226.6° E, which contains P0.

## Added test T (terrain, not illumination)
The 70 % Sun verdict flips if the controlling rise is ~0.56 m higher relative to P0 than PGDA 78 says (L7). A1 tests
that relative height with the NAC DTM.
1. Read `NAC_DTM_ESALL_SR12` with its own CRS; reproject P0 and the rise cell centre (−2687.5, −6092.5 m) to it.
2. Co-register: median of (NAC − PGDA 78) over all 5 m PGDA 78 cell centres 200–500 m from P0 with PGDA 78 slope < 10°;
   subtract that constant. Report it, and a fitted plane (tilt) over the same points.
3. Metric: Δrel = [h_NAC(rise) − h_NAC(P0)] − [h_78(rise) − h_78(P0)], NAC heights bilinear at 2 m; also the same for the 9
   cells 14–18 m from P0 along azimuths 225°–260° local (the bins the rise controls).
4. Pass rule: |Δrel| ≤ 0.56 m at the rise cell **and** median |Δrel| ≤ 0.56 m over the 9 cells. Otherwise FAIL.
   If the DTM has nodata at P0 or the rise, or its stated vertical precision (label) exceeds 1 m, INCOMPLETE.
5. Independence caveat (stated now): LROC NAC DTMs are usually tied to LOLA tracks for absolute control, so a PASS tests
   the *relative* shape of the rise at 2 m, not absolute heights; it is not an illumination observation and does not
   replace Sets A–C of the base protocol.

## Not done tonight
Downloading the DTM (size unknown until the label is read) and the 234 frames is held until the submission is pushed.
