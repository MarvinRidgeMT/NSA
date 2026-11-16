"""SfS vs LOLA for any site covered by a GSFC SfS region (Bertone et al. 2026, CC-BY-4.0). Usage: step19_sfs_site.py KEY REGION_DIR"""
import sys, json, dataclasses, numpy as np, rasterio
from pathlib import Path
from scipy.ndimage import distance_transform_edt
from polaris_batch import core
from build_data import interp, longest
from sites import R
D=Path("data/external"); W=Path("work")
key, rdir = sys.argv[1], Path(sys.argv[2]); site, lat, lon, _ = R[key]
ef = next(rdir.glob("*GLDELEV_005.tif"))
with rasterio.open(ef) as d: sfs=d.read(1).astype(np.float64); sfs[sfs<-1e30]=np.nan; T=d.transform
lola_d=core.Dem.open(core.site_files(site,D)["surf"][1]); lola=lola_d.z; t=~lola_d.inv
c0=int(round((t.c-T.c)/5)); r0=int(round((T.f-t.f)/5)); n=lola.shape[0]
s=np.full_like(lola,np.nan); H,Wd=sfs.shape
rs=slice(max(0,r0),min(H,r0+n)); cs=slice(max(0,c0),min(Wd,c0+n))
s[rs.start-r0:rs.stop-r0, cs.start-c0:cs.stop-c0]=sfs[rs,cs]
valid=np.isfinite(s); w=np.clip(distance_transform_edt(valid)*5/200,0,1)
merged=np.where(valid,w*s+(1-w)*lola,lola)
far=core.Dem.open(D/"pgda90/LDEM_80S_80MPP_ADJ.TIF"); e=np.load(W/f"eph_{key}.npz")
def met(el_):
    sun=e["sun_el"]>interp(el_,e["sun_az"]); both=sun&(e["earth_el"]>interp(el_,e["earth_az"]))
    return {"sun":round(100*sun[312:649].mean(),2),"both":round(100*both[312:649].mean(),2),"gap":int(longest((~sun[312:649])[None,:])[0]),"year":round(100*sun[312:312+8761].mean(),2)}, sun
vd=json.load(open(W/"viewer_data.json"))["sites"][key]["masts"]
x0,y0=lola_d.to_grid.transform(lon,lat); cc,rr=lola_d.inv*(x0,y0)
rows=[]; sun1=None
for m in (1,1.25,1.5,2,3,5,10):
    hz=core.compute_horizon(lon,lat,dataclasses.replace(lola_d,z=merged),far,m,near_step=1.0)
    r,sn=met(hz.elev); i=vd["masts"].index(float(m))
    r.update(mast=m,ground_m=round(hz.h0-m,2),lola_sun=vd["demo_sun"][i][0],lola_sun_clones=[min(vd["demo_sun"][i][1:]),max(vd["demo_sun"][i][1:])],
             lola_year=vd["year_sun"][i][0],lola_year_clones=[min(vd["year_sun"][i][1:]),max(vd["year_sun"][i][1:])])
    r["year_inside_clone_range"]=bool(r["lola_year_clones"][0]<=r["year"]<=r["lola_year_clones"][1]); rows.append(r)
    if m==1: sun1=sn
    print(key,r,flush=True)
_,s_nom=met(np.load(W/f"hz/{key}_nominal_m1.npz")["elev"])
cl=np.array([met(np.load(W/f"hz/{key}_clone_{k:04d}_m1.npz")["elev"])[1] for k in range(1,21)])
Y=slice(312,312+8761); dis=(sun1!=s_nom)[Y]; clf=(cl!=s_nom).any(0)[Y]
rec={"region":rdir.name,"cover_frac":round(float(valid.mean()),3),"sfs_minus_lola_rms":round(float(np.sqrt(np.nanmean((s-lola)[valid]**2))),3),
     "masts":rows,"hours":{"sfs_vs_lola_disagree_h":int(dis.sum()),"of_which_clones_also_flip_h":int((dis&clf).sum())}}
rr_,cc_=np.mgrid[0:n,0:n]; dist=np.hypot((cc_+0.5-cc)*5,(rr_+0.5-rr)*5); w2=np.clip((dist-100)/50,0,1); split={}
for name,z in (("LOLA within 100 m, SfS beyond",w2*merged+(1-w2)*lola),("SfS within 100 m, LOLA beyond",w2*lola+(1-w2)*merged)):
    hz=core.compute_horizon(lon,lat,dataclasses.replace(lola_d,z=z),far,1.0,near_step=1.0); r,_=met(hz.elev); split[name]={"ground_m":round(hz.h0-1,2),"year":r["year"],"sun_demo":r["sun"]}
rec["split"]=split; print(key,rec["hours"],split,rec["cover_frac"],rec["sfs_minus_lola_rms"])
out=json.load(open(W/"sfs_result.json")); out[key]=rec; json.dump(out,open(W/"sfs_result.json","w"),indent=1,default=bool)
