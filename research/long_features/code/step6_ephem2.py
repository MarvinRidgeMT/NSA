import numpy as np, json
from pathlib import Path
from polaris_batch import core
D=Path("data/external"); W=Path("work")
R={"Site04_ROI3":("Site04",-89.78012,-156.32023),"Site01_ROI6":("Site01",-89.47409,-137.3813)}
for key,(site,lat,lon) in R.items():
    z0=json.load(open(W/"eph_meta.json"))[key]["z0"]
    o={n:core.horizons_observer(b,lon,lat,z0,"2024-01-01 00:00","2042-09-01 00:00","6h",D/"horizons_cache") for b,n in (("10","sun"),("399","earth"))}
    np.savez(W/f"eph186_{key}.npz",time=np.array(o["sun"]["time"]),**{f"{n}_{q}":o[n][q] for n in o for q in ("az","el","ang_diam_arcsec")})
    print(key,len(o["sun"]["time"]),flush=True)
# Barker: Site01 RoI4 centroid, hourly 2024-01-01 .. 2026-01-01
near=core.Dem.open(core.site_files("Site01",D)["surf"][1])
cx,cy=json.load(open(W/"barker_rois.json"))["4"]["centroid"]
lo,la=near.to_grid.transform(cx,cy,direction="INVERSE"); z=float(near.sample_xy(np.array([cx]),np.array([cy]))[0])
s=core.horizons_observer("10",float(lo),float(la),z,"2024-01-01 00:00","2026-01-01 00:00","1h",D/"horizons_cache")
np.savez(W/"eph_barker_roi4.npz",time=np.array(s["time"]),az=s["az"],el=s["el"],diam=s["ang_diam_arcsec"],lon=lo,lat=la)
print("barker",len(s["time"]),lo,la)
