"""Merge NASA GSFC SfS (Bertone et al. 2026, Zenodo 10.5281/zenodo.17954508, CC-BY-4.0) region 6 into PGDA 78 5 m tiles.
Same 5 m polar-stereographic lattice. SfS where valid, LOLA elsewhere, linear 200 m feather at the SfS edge."""
import json, numpy as np, rasterio
from scipy.ndimage import distance_transform_edt
from pathlib import Path
from polaris_batch import core
D=Path("data/external"); S=Path("/home/claude/dl/sfs/A3CLR22_6_Connecting_Ridge")
with rasterio.open(S/"A306_GLDELEV_005.tif") as d:
    sfs=d.read(1).astype(np.float64); sfs[sfs<-1e30]=np.nan; T=d.transform
meta={}
for site in ("Site01","Site04"):
    p=core.site_files(site,D)["surf"][1]
    with rasterio.open(p) as d:
        lola=d.read(1).astype(np.float64); prof=d.profile; t=d.transform
        if d.nodata is not None: lola[lola==d.nodata]=np.nan
    c0=int(round((t.c-T.c)/5)); r0=int(round((T.f-t.f)/5))   # tile origin inside the SfS grid
    s=np.full_like(lola,np.nan)
    rs=slice(max(0,r0),min(3200,r0+3200)); cs=slice(max(0,c0),min(3200,c0+3200))
    s[rs.start-r0:rs.stop-r0, cs.start-c0:cs.stop-c0]=sfs[rs,cs]
    valid=np.isfinite(s)
    w=np.clip(distance_transform_edt(valid)*5.0/200.0,0,1)   # 0 at edge -> 1 at 200 m inside
    out=np.where(valid, w*s+(1-w)*lola, lola)
    prof.update(dtype="float32",nodata=None)
    f=D/f"sfs/{site}_sfs_merged_5mpp.tif"; f.parent.mkdir(exist_ok=True,parents=True)
    with rasterio.open(f,"w",**prof) as d: d.write(out.astype(np.float32),1)
    diff=(s-lola)[valid]
    meta[site]={"file":str(f),"sfs_cover_frac":float(valid.mean()),"sfs_minus_lola_rms":float(np.sqrt(np.nanmean(diff**2))) if valid.any() else None}
    print(site,meta[site])
json.dump(meta,open("work/sfs_meta.json","w"),indent=1)
