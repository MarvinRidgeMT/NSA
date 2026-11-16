# NAC protocol v2 — amendment 1 (image times for region 8)

Frozen 15 Nov 2026 ~18:10 EST, before any region 8 image was downloaded or compared. Author: Claude (Penumbra session).
Applies to `NAC_PROTOCOL_V2.md` (SHA-256 833adb90c41f697b07cd987e91850ac02e4e6542fda7c971606f2ea7ee8be49f), which is unchanged.

## Why
v2 takes image times from `LROC-NAC-adjust/*.json` `m_centerEphemerisTime`. The region 9 archive has these files
(193 images); the region 8 archive (A3CLR22_8_Peak_Near_Shackleton.zip) has none: its `LROC-NAC-adjust/` folder is empty.
Without an amendment, area C (Site07 ROI1) could not be run and the v2 result would be incomplete by its own rule.

## Amendment
For region 8 only, the image time is computed from the LROC product ID (`M<digits><L|R>E`) by the linear relation fitted
to every region 6 and region 9 camera file (515 images; outcome data of no region is used):
- 9-digit IDs: ET = 0.9999999698934682 · n + 198632811.7400536 s (472 images; max |residual| 8.95 s, sd 3.61 s)
- 10-digit IDs: ET = 0.9999999996511174 · n − 701367195.2147683 s (43 images; max |residual| 3.11 s, sd 1.78 s)

A 9 s time error moves the Sun by at most ~0.0013° in azimuth at the pole (0.51°/h) and less in elevation, far below the
0.5° crossing tolerance. Region 8 IDs: 172 images, 156 9-digit (101350392..), 16 10-digit (..1110497004), all inside or
within 0.11 Ms of the fitted ranges.

Everything else in v2 (areas, model, observation thresholds, crossing method, pass rule) is unchanged. Region 9 keeps
its camera-file times. The Sun vector is computed from ET with SPICE (MOON_ME, LT+S) in the parent process, as in v2.
