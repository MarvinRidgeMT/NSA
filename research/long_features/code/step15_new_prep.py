import json, numpy as np
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from polaris_batch import core
from sites import R, NEW
D=Path("data/external"); W=Path("work")
jobs=[]
for k in NEW:
    s=R[k][0]; jobs.append(core.site_files(s,D)["toterr"]); jobs+= [core.clone_file(s,n,D) for n in range(1,21)]
with ThreadPoolExecutor(6) as ex: list(ex.map(lambda j: core.download(*j), jobs))
print("downloads ok",flush=True)
meta=json.load(open(W/"eph_meta.json"))
for k in NEW:
    s,lat,lon,_=R[k]; near=core.Dem.open(core.site_files(s,D)["surf"][1]); z0=float(near.sample_lonlat(np.array([lon]),np.array([lat]))[0])
    eph={n:core.horizons_observer(b,lon,lat,z0,"2026-11-01 00:00","2027-12-31 00:00","1h",D/"horizons_cache") for b,n in (("10","sun"),("399","earth"))}
    np.savez(W/f"eph_{k}.npz",time=np.array(eph["sun"]["time"]),**{f"{n}_{q}":eph[n][q] for n in eph for q in ("az","el","ang_diam_arcsec")})
    meta[k]={"z0":z0,"n":len(eph["sun"]["time"]),"raw":{n:eph[n]["raw"] for n in eph}}
    o={n:core.horizons_observer(b,lon,lat,z0,"2024-01-01 00:00","2042-09-01 00:00","6h",D/"horizons_cache") for b,n in (("10","sun"),("399","earth"))}
    np.savez(W/f"eph186_{k}.npz",time=np.array(o["sun"]["time"]),**{f"{n}_{q}":o[n][q] for n in o for q in ("az","el","ang_diam_arcsec")})
    print(k,z0,flush=True)
json.dump(meta,open(W/"eph_meta.json","w"),indent=1)
