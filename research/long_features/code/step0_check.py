import time, numpy as np
from pathlib import Path
from polaris_batch import core, ext
D=Path("data/external")
near=core.Dem.open(core.site_files("Site04",D)["surf"][1]); far=core.Dem.open(D/"pgda90/LDEM_80S_80MPP_ADJ.TIF")
lat,lon=-89.78012,-156.32023
t=time.time(); hx=ext.compute_horizon_x(lon,lat,near,far,1.0); print("x",time.time()-t)
t=time.time(); h=core.compute_horizon(lon,lat,near,far,1.0,near_step=1.0); print("core",time.time()-t)
print("max |diff| elev", np.nanmax(np.abs(h.elev-hx.elev)), "dist", np.nanmax(np.abs(h.dist-hx.dist)))
e=np.load("work/eph_Site04_ROI3.npz"); w=slice(312,312+337); print(e["time"][312], e["time"][312+336])
sun={k:e["sun_"+k][w] for k in ("az","el","ang_diam_arcsec")}; earth={k:e["earth_"+k][w] for k in ("az","el","ang_diam_arcsec")}
print(core.visibility(h,sun,earth))
print("near frac",hx.in_near.mean(),"dist range",np.nanmin(hx.dist),np.nanmax(hx.dist))
