"""LROC WAC observed illumination (time-weighted, Feb 2010 - Feb 2011, 100 m, PDS WAC_POLE_ILL_TWI_SOUTH_100M) vs POLARIS model
(same period, 2 h, 0.5 m above ground, 5 points over +-25 m) and vs PGDA 69 (18.6-yr model, 60 m) at the 17 PGDA 78 RoIs."""
import csv, json, numpy as np
from pathlib import Path
from scipy.stats import spearmanr
from scipy.ndimage import map_coordinates
from polaris_batch import core
from build_data import interp, transfer_azel
W=Path("work"); J=W/"jobs"
a=np.load("/home/claude/dl/wac/twi.npy")
R=list(csv.DictReader(open("data/polaris_roi_sites.csv"))); jobs=json.load(open(W/"jobs_W.json"))
rows=[]
for r in R:
    s=r["site"]; e=np.load(W/f"eph_wac_{s}.npz"); rs=e["diam"]/7200
    vals_any=[];vals_c=[]
    for j in jobs:
        if j["site"]!=s or j["roi"]!=int(r["roi"]): continue
        az,el=transfer_azel(e["az"],e["el"],float(e["lon"]),float(e["lat"]),j["lon"],j["lat"])
        h=interp(np.load(J/f"{j['out']}.npz")["elev"],az)
        vals_any.append(100*float((el+rs>h).mean())); vals_c.append(100*float((el>h).mean()))
    x,y=float(r["x_m"]),float(r["y_m"])
    wac=float(map_coordinates(a,[[606.5-y/100],[606.5+x/100]],order=1)[0])
    win=a[int(606.5-y/100)-1:int(606.5-y/100)+2,int(606.5+x/100)-1:int(606.5+x/100)+2]
    rows.append({"site":s,"roi":int(r["roi"]),"wac_twi_pct":round(wac,2),"wac_3x3_max":round(float(np.nanmax(win)),2),"pgda69_pct":float(r["avg_sun_pct_18p6yr"]),
                 "ours_any_pct":round(float(np.mean(vals_any)),2),"ours_centre_pct":round(float(np.mean(vals_c)),2)})
w=np.array([x["wac_twi_pct"] for x in rows]); o=np.array([x["ours_any_pct"] for x in rows]); p=np.array([x["pgda69_pct"] for x in rows]); oc=np.array([x["ours_centre_pct"] for x in rows])
st=lambda u,v: {"spearman":round(float(spearmanr(u,v).correlation),3),"bias":round(float(np.mean(u-v)),2),"rmse":round(float(np.sqrt(np.mean((u-v)**2))),2)}
res={"rows":rows,"ours_any_vs_wac":st(o,w),"ours_centre_vs_wac":st(oc,w),"pgda69_vs_wac":st(p,w),"ours_any_vs_pgda69":st(o,p),
     "note":"WAC TWI = fraction of time-weighted WAC observations in which the 100 m pixel was lit, one lunar year (15 Feb 2010 - 5 Feb 2011, 3807 images). Ours: same period, 2 h, 0.5 m above ground, any part of the Sun disc visible, mean of 5 points within 25 m. PGDA 69: 18.6-yr modelled average, 60 m."}
for x in rows: print(x)
print({k:v for k,v in res.items() if k not in("rows","note")})
json.dump(res,open(W/"wac_result.json","w"),indent=1)
