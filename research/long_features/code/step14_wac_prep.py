import csv, json, numpy as np
from pathlib import Path
from polaris_batch import core
D=Path("data/external"); W=Path("work")
for s in ("Site07","Site11"):
    core.download(*core.site_files(s,D)["surf"])
R=list(csv.DictReader(open("data/polaris_roi_sites.csv")))
eph={}
for s in ("Site01","Site04","Site07","Site11"):
    r=next(x for x in R if x["site"]==s); lat,lon=float(r["lat_deg"]),float(r["lon_deg_east"])
    near=core.Dem.open(core.site_files(s,D)["surf"][1]); z=float(near.sample_lonlat(np.array([lon]),np.array([lat]))[0])
    o=core.horizons_observer("10",lon,lat,z,"2010-02-15 00:00","2011-02-05 00:00","2h",D/"horizons_cache")
    np.savez(W/f"eph_wac_{s}.npz",az=o["az"],el=o["el"],diam=o["ang_diam_arcsec"],lon=lon,lat=lat,time=np.array(o["time"])); print(s,len(o["time"]))
J=[]
for r in R:
    s=r["site"]; near=core.Dem.open(core.site_files(s,D)["surf"][1]); x0,y0=float(r["x_m"]),float(r["y_m"])
    for k,(dx,dy) in enumerate([(0,0),(25,0),(-25,0),(0,25),(0,-25)]):
        lo,la=near.to_grid.transform(x0+dx,y0+dy,direction="INVERSE")
        J.append(dict(out=f"wac_{s}_roi{r['roi']}_p{k}_m0.5",site=s,dem="nominal",lon=float(lo),lat=float(la),mast=0.5,roi=int(r["roi"]),px=k))
json.dump(J,open(W/"jobs_W.json","w")); print(len(J))
