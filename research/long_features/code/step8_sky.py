"""Sky Envelope: over one 18.6-yr cycle (2024-01-01 .. 2042-09-01, 6 h), min/max Sun and Earth elevation per 1-deg azimuth,
with the nominal skyline and the 20-clone skyline envelope (1 m mast). Also the long-run Sun/Earth visibility per azimuth."""
import json, numpy as np
from pathlib import Path
W=Path("work"); out={}
from sites import selected, merge_dump
for key in selected():
    e=np.load(W/f"eph186_{key}.npz")
    nom=np.load(W/f"hz/{key}_nominal_m1.npz")
    cl=np.array([np.load(W/f"hz/{key}_clone_{n:04d}_m1.npz")["elev"] for n in range(1,21)])
    rec={"az":list(range(360))}
    for b in ("sun","earth"):
        a=np.floor(np.mod(e[f"{b}_az"],360)).astype(int); el=e[f"{b}_el"]
        lo=np.full(360,np.nan); hi=np.full(360,np.nan); cnt=np.zeros(360,int)
        for k in range(360):
            s=el[a==k]
            if len(s): lo[k]=s.min(); hi[k]=s.max(); cnt[k]=len(s)
        rec[f"{b}_el_min"]=np.round(lo,3).tolist(); rec[f"{b}_el_max"]=np.round(hi,3).tolist(); rec[f"{b}_n"]=cnt.tolist()
        # long-run visible fraction (centre above nominal horizon), per body
        hb=np.interp(np.mod(e[f"{b}_az"],360),np.r_[nom["az"]-360,nom["az"],nom["az"]+360],np.r_[nom["elev"],nom["elev"],nom["elev"]])
        rec[f"{b}_visible_pct_18p6yr_nominal"]=round(100*float((el>hb).mean()),2)
    # skyline at 1-deg (mean of the two 0.5-deg bins), and clone envelope
    rec["sky_nom"]=np.round(nom["elev"].reshape(360,2).max(1),3).tolist()
    rec["sky_clone_min"]=np.round(cl.reshape(20,360,2).max(2).min(0),3).tolist()
    rec["sky_clone_max"]=np.round(cl.reshape(20,360,2).max(2).max(0),3).tolist()
    rec["sky_dist_m"]=np.round(nom["dist"][::2],0).tolist()
    rec["n_samples"]=int(len(e["time"])); rec["first"]=str(e["time"][0]); rec["last"]=str(e["time"][-1])
    # azimuths where the Sun can ever be blocked (horizon above the Sun's minimum) and the 'contested' azimuths (Sun range crosses skyline)
    sk=np.array(rec["sky_nom"]); smin=np.array(rec["sun_el_min"]); smax=np.array(rec["sun_el_max"])
    rec["contested_sun_az_deg"]=int(np.sum((smin<sk)&(smax>sk)))
    rec["always_blocked_sun_az_deg"]=int(np.sum(smax<=sk))
    out[key]=rec
    print(key,rec["n_samples"],"sun vis %",rec["sun_visible_pct_18p6yr_nominal"],"earth",rec["earth_visible_pct_18p6yr_nominal"],"contested",rec["contested_sun_az_deg"],"always blocked",rec["always_blocked_sun_az_deg"])
merge_dump(W/"sky.json",out)
