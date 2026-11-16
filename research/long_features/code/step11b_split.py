import json, numpy as np, dataclasses
from pathlib import Path
from polaris_batch import core
from build_data import interp, longest
D=Path("data/external"); W=Path("work")
lat,lon=-89.47409,-137.3813
lola=core.Dem.open(core.site_files("Site01",D)["surf"][1]); sfs=core.Dem.open(D/"sfs/Site01_sfs_merged_5mpp.tif"); far=core.Dem.open(D/"pgda90/LDEM_80S_80MPP_ADJ.TIF")
x0,y0=lola.to_grid.transform(lon,lat); c0,r0=lola.inv*(x0,y0)
rr,cc=np.mgrid[0:lola.z.shape[0],0:lola.z.shape[1]]; dist=np.hypot((cc+0.5-c0)*5,(rr+0.5-r0)*5)
w=np.clip((dist-100)/50,0,1)   # 0 inside 100 m (local), 1 beyond 150 m
e=np.load(W/"eph_Site01_ROI6.npz"); out={}
for name,z in (("LOLA within 100 m, SfS beyond",w*sfs.z+(1-w)*lola.z),("SfS within 100 m, LOLA beyond",w*lola.z+(1-w)*sfs.z)):
    hz=core.compute_horizon(lon,lat,dataclasses.replace(lola,z=z),far,1.0,near_step=1.0)
    sun=e["sun_el"]>interp(hz.elev,e["sun_az"])
    out[name]={"ground_m":round(hz.h0-1,2),"sun_demo":round(100*sun[312:649].mean(),2),"year":round(100*sun[312:312+8761].mean(),2)}; print(name,out[name])
r=json.load(open(W/"sfs_result.json")); r["Site01_ROI6"].pop("sfs_terrain_lola_ground",None); r["Site01_ROI6"]["split"]=out
json.dump(r,open(W/"sfs_result.json","w"),indent=1,default=bool)
