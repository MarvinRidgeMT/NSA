import json, numpy as np
from pathlib import Path
from polaris_batch import core
D=Path("data/external"); OUT=Path("work"); OUT.mkdir(exist_ok=True)
rois={r["site"]+"_ROI"+str(r["roi"]):r for r in [
 {"site":"Site04","roi":3,"lat":-89.78012,"lon":-156.32023},
 {"site":"Site01","roi":6,"lat":-89.47409,"lon":-137.3813}]}
meta={}
for k,r in rois.items():
    near=core.Dem.open(core.site_files(r["site"],D)["surf"][1])
    z0=float(near.sample_lonlat(np.array([r["lon"]]),np.array([r["lat"]]))[0])
    eph={}
    for b,name in (("10","sun"),("399","earth")):
        o=core.horizons_observer(b,r["lon"],r["lat"],z0,"2026-11-01 00:00","2027-12-31 00:00","1h",D/"horizons_cache")
        eph[name]=o
    t=np.array(eph["sun"]["time"]); assert list(t)==eph["earth"]["time"]
    np.savez(OUT/f"eph_{k}.npz", time=t, **{f"{n}_{q}":eph[n][q] for n in ("sun","earth") for q in ("az","el","ang_diam_arcsec")})
    meta[k]={"z0":z0,"n":len(t),"first":t[0],"last":t[-1],"raw":{n:eph[n]["raw"] for n in eph}}
    print(k,z0,len(t),t[0],t[-1])
json.dump(meta,open(OUT/"eph_meta.json","w"),indent=1)
