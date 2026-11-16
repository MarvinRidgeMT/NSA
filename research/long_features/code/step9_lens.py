"""Model Disagreement Lens pilot: the same 1 m-mast decision on four NASA terrain products."""
import json, numpy as np, pyproj, rasterio
from rasterio.windows import from_bounds
from pathlib import Path
from polaris_batch import core
D=Path("data/external"); W=Path("work")
from sites import selected
R=selected()
def window_dem(path,lon,lat,half=30000.0):
    with rasterio.open(path) as ds:
        tr=pyproj.Transformer.from_crs(core.LONLAT,ds.crs,always_xy=True); x,y=tr.transform(lon,lat)
        win=from_bounds(x-half,y-half,x+half,y+half,ds.transform).round_offsets().round_lengths()
        z=ds.read(1,window=win).astype(np.float64)
        if ds.nodata is not None: z[z==ds.nodata]=np.nan
        z[~np.isfinite(z)]=np.nan
        return core.Dem(Path(path),z,~ds.window_transform(win),tr,float(abs(ds.res[0])))
def interp(elev,az):
    n=len(elev);st=360/n;a=np.mod(az-st/2,360)/st;i0=np.floor(a).astype(int)%n;i1=(i0+1)%n;f=a-np.floor(a);return elev[i0]*(1-f)+elev[i1]*f
far=core.Dem.open(D/"pgda90/LDEM_80S_80MPP_ADJ.TIF")
for key,(site,lat,lon) in R.items():
    e=np.load(W/f"eph_{key}.npz"); out=[]
    prods=[("PGDA 78 5 m + PGDA 90 80 m (POLARIS)",None),("PGDA 90 20 m + 80 m","LDEM_80S_20MPP_ADJ.TIF"),("PGDA 90 40 m + 80 m","LDEM_80S_40MPP_ADJ.TIF"),("PGDA 90 80 m only","80")]
    for label,f in prods:
        if f is None: elev=np.load(W/f"hz/{key}_nominal_m1.npz")["elev"]; h0=float(np.load(W/f"hz/{key}_nominal_m1.npz")["h0"])
        else:
            near=far if f=="80" else window_dem(D/"pgda90"/f,lon,lat)
            hz=core.compute_horizon(lon,lat,near,far,1.0,near_step=1.0); elev=hz.elev; h0=hz.h0
        def m(sl,both=False):
            s=e["sun_el"][sl]>interp(elev,e["sun_az"][sl])
            if both: s=s&(e["earth_el"][sl]>interp(elev,e["earth_az"][sl]))
            return round(100*float(s.mean()),2)
        rec={"label":label,"ground_m":round(h0-1.0,2),"sun":m(slice(312,649)),"both":m(slice(312,649),True),"year":m(slice(312,312+8761)),"max_horizon_deg":round(float(np.nanmax(elev)),3)}
        out.append(rec); print(key,rec,flush=True)
    sp=[p["sun"] for p in out]
    note=(f"Same 1 m mast, same ephemeris, four NASA terrain products. Sun (14 days) ranges {min(sp):.1f}–{max(sp):.1f} %. "
          "The coarser products smooth away the small rise that controls the horizon here, so they read higher; this is resolution, not error.")
    json.dump({"products":out,"note":note},open(W/f"lens_{key}.json","w"),indent=1)
