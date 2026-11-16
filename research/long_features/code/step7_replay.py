"""Failure Replay data: every Sun-blocked or near-critical hour (|margin| < 0.5 deg) in the demo window, 1 m mast."""
import json, numpy as np
from pathlib import Path
from polaris_batch import core, ext
D=Path("data/external"); W=Path("work")
from sites import selected, merge_dump
R=selected()
out={}
for key,(site,lat,lon) in R.items():
    near=core.Dem.open(core.site_files(site,D)["surf"][1]); far=core.Dem.open(D/"pgda90/LDEM_80S_80MPP_ADJ.TIF")
    nom=np.load(W/f"hz/{key}_nominal_m1.npz"); e=np.load(W/f"eph_{key}.npz"); rq=np.load(W/f"rq2_{key}.npz")
    sl=slice(312,312+337)
    t=e["time"][sl]; az=e["sun_az"][sl]; el=e["sun_el"][sl]
    hz=core.Horizon(nom["az"],nom["elev"],nom["dist"],np.ones(720,bool),float(nom["h0"]))
    H=hz.at(az); m=el-H; stc=rq["stc"][:,sl]
    ib=ext.nearest_bin(az)
    rows=[]
    for i in np.where((m<=0)|(np.abs(m)<0.5))[0]:
        b=ib[i]; dctl=float(nom["dist"][b]); dmax=min(max(60.0,2.2*dctl),400.0)
        d=np.arange(0.0,dmax+0.01,1.0 if dmax<=100 else 2.0)
        lo,la=core.destination(lon,lat,np.array([az[i]]),np.maximum(d,1e-3)); h=near.sample_lonlat(lo,la)[0]
        rows.append({"i":int(i),"time":str(t[i]),"sun_az":round(float(az[i]),3),"sun_el":round(float(el[i]),4),"horizon_el":round(float(H[i]),4),
            "margin_deg":round(float(m[i]),4),"visible":bool(m[i]>0),"ctrl_dist_m":dctl,"ctrl_in_5m_tile":bool(nom["in_near"][b]),
            "clones_visible":int(stc[:,i].sum()),"profile_d":d.round(1).tolist(),"profile_h":np.round(h-float(nom["z0"]),3).tolist()})
    # intervals of blocked hours
    blk=m<=0; ints=[]; s=None
    for i,bv in enumerate(blk):
        if bv and s is None: s=i
        if (not bv or i==len(blk)-1) and s is not None:
            e_=i if bv else i-1; ints.append({"start":str(t[s]),"end":str(t[e_]),"hours":e_-s+1,"min_margin":round(float(m[s:e_+1].min()),3)}); s=None
    out[key]={"mast_m":1.0,"z0":float(nom["z0"]),"n_samples":337,"blocked_hours":int(blk.sum()),"intervals":ints,"hours":rows,
              "clone_blocked_hours":[int((~stc[k]).sum()) for k in range(20)]}
    print(key,"blocked",int(blk.sum()),"near/blocked rows",len(rows),ints)
merge_dump(W/"replay.json",out)
