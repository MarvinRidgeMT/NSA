import numpy as np, time, sys
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor
from functools import lru_cache
from polaris_batch import core, ext
D=Path("data/external"); OUT=Path("work/hz"); OUT.mkdir(parents=True, exist_ok=True)
from sites import R as _R, NEW
R={k:v[:3] for k,v in _R.items() if k in NEW}
@lru_cache(2)
def dem(p): return core.Dem.open(Path(p))
def job(a):
    key,dem_id,mast=a; site,lat,lon=R[key]
    p=core.site_files(site,D)["surf"][1] if dem_id=="nominal" else core.clone_file(site,int(dem_id[-4:]),D)[1]
    f=OUT/f"{key}_{dem_id}_m{mast:g}.npz"
    if dem_id=="nominal" and f.exists() and "cand_elev" not in np.load(f).files: f.unlink()
    if f.exists(): return f.name
    hx=ext.compute_horizon_x(lon,lat,dem(str(p)),dem(str(D/"pgda90/LDEM_80S_80MPP_ADJ.TIF")),mast)
    np.savez(f,**{k:v for k,v in hx.__dict__.items()})
    return f.name
jobs=[(k,d,m) for k in R for d in ["nominal"]+[f"clone_{n:04d}" for n in range(1,21)] for m in (1.0,)]
t=time.time()
with ProcessPoolExecutor(2) as ex:
    for i,r in enumerate(ex.map(job,jobs),1): print(i,r,round(time.time()-t),flush=True)
