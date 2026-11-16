# Site01 ROI6: the +1.97 m SfS-minus-LOLA offset at the site point

15 Nov 2026, 21:10 EST, session A. Read-only analysis; **no reference, bundle, solver input or science value was changed.**
Release status unchanged: **SOURCE_BASED_UNVALIDATED**.

Script: `tmp/offset2m/analyse.py` (output `tmp/offset2m/result.json`). Inputs: the bundle's 5 m LOLA crop for `site01_roi6`
(`data/viewer/polaris-x5d-roi-2026-11-14-v2.json`, 401², 5 m) and the display surface `data/visual/terrain_context/site01_roi6/local_display_f32.bin`
(NASA GSFC SfS, Zenodo 10.5281/zenodo.17954508, full weight over the whole crop).

## Result

| Distance from site point | Mean SfS − LOLA | SD |
|---|---|---|
| 0–10 m | +1.94 m | 0.14 m |
| 10–25 m | +1.96 m | 0.23 m |
| 25–50 m | +1.84 m | 0.33 m |
| 50–100 m | +1.23 m | 0.55 m |
| 100–250 m | +0.75 m | 0.92 m |
| 250–500 m | +0.74 m | 0.97 m |
| 500–1000 m | +0.16 m | 1.20 m |
| whole crop (2 km) | mean +0.24 m, median +0.27 m, rms 1.20 m | |

- **It is local, not a datum bias.** The crop-wide bias is +0.24 m and a plane fit of the difference has a tilt of only 0.53 m/km. The +2 m sits in a
  ~2 m high, ~100 m wide rise centred on the site point that SfS shows and the LOLA 5 m product does not.
- **It is not a slope/registration effect at the point.** LOLA slope at the site is 0.96°; a horizontal offset of ~118 m would be needed to produce 1.97 m.
- **Co-registration hint (inner 500 m):** shifting SfS by 2 px (10 m) in grid x lowers the bias-removed rms from 0.96 m to 0.73 m. This suggests a
  possible ~10 m horizontal offset between the two products here; it does not explain the 2 m at the point.
- **Cannot be settled with the data in the repo.** Either SfS resolves a real low rise that LOLA's 5 m interpolation smooths, or it is an SfS
  shading/albedo artifact on near-flat ground. Deciding needs independent data (LOLA RDR shot points or NAC stereo at this point).

## Consequence for the display (not the science)

- The web and Blender display surfaces are shifted by a **constant −1.97 m** so the surface meets the bundle ground at the observer. Because the offset is
  local, the displayed SfS surface away from the site sits on average ~1.7 m below the LOLA crop (crop bias +0.24 m − 1.97 m). This affects display only;
  rays, states, margins and every number use the LOLA crop.
- Possible future change (not made, needs Sid/Anish): shift by the crop bias (−0.24 m) and blend the SfS surface into LOLA within ~100 m of the observer,
  so both the mast foot and the far terrain match. Visibility states would be unaffected either way.
