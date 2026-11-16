"""SfS vs LOLA: same solver, NASA GSFC SfS region 6 (merged into the PGDA 78 Site01 lattice) vs PGDA 78 LOLA + 20 clones."""
import json, numpy as np
from pathlib import Path
from polaris_batch import core, ext
from build_data import interp, longest, transfer_azel
D=Path("data/external"); W=Path("work"); J=W/"jobs"
DEMO=slice(312,649); YEAR=slice(312,312+8761)
out={}
def met(elev,e,ee=None):
    ee=ee or e
    sun=ee["sun_el"]>interp(elev,ee["sun_az"]); both=sun&(ee["earth_el"]>interp(elev,ee["earth_az"]))
    return {"sun":round(100*sun[DEMO].mean(),2),"both":round(100*both[DEMO].mean(),2),"gap":int(longest((~sun[DEMO])[None,:])[0]),
            "year":round(100*sun[YEAR].mean(),2)}, sun
vd=json.load(open(W/"viewer_data.json"))
for key,site,lat,lon in (("Site01_ROI6","Site01",-89.47409,-137.3813),("Site04_ROI3","Site04",-89.78012,-156.32023)):
    e=np.load(W/f"eph_{key}.npz"); m=vd["sites"][key]["masts"]
    rows=[]
    for mast in ((1,1.25,1.5,1.75,2,3,5,10) if key=="Site01_ROI6" else (1,10)):
        f=J/f"sfs_{key}_m{mast:g}.npz"
        if not f.exists(): continue
        r,_=met(np.load(f)["elev"],e); i=m["masts"].index(float(mast))
        r.update(mast=mast,ground_m=round(float(np.load(f)["z0"]),2),lola_sun=m["demo_sun"][i][0],lola_sun_clones=[min(m["demo_sun"][i][1:]),max(m["demo_sun"][i][1:])],
                 lola_year=m["year_sun"][i][0],lola_year_clones=[min(m["year_sun"][i][1:]),max(m["year_sun"][i][1:])])
        r["year_inside_clone_range"]=r["lola_year_clones"][0]<=r["year"]<=r["lola_year_clones"][1]
        rows.append(r)
    rec={"masts":rows}
    if key=="Site01_ROI6":
        # hour-level: are the hours where SfS disagrees with LOLA nominal among the hours where LOLA clones disagree?
        _,s_sfs=met(np.load(J/f"sfs_{key}_m1.npz")["elev"],e); _,s_nom=met(np.load(W/f"hz/{key}_nominal_m1.npz")["elev"],e)
        cl=np.array([met(np.load(W/f"hz/{key}_clone_{n:04d}_m1.npz")["elev"],e)[1] for n in range(1,21)])
        dis=(s_sfs!=s_nom)[YEAR]; clflip=(cl!=s_nom).any(0)[YEAR]
        inside=((s_sfs[YEAR]>=cl.min(0)[YEAR])&(s_sfs[YEAR]<=cl.max(0)[YEAR]))
        rec["hours"]={"sfs_vs_lola_disagree_h":int(dis.sum()),"of_which_clones_also_flip_h":int((dis&clflip).sum()),
                      "sfs_state_within_clone_set_pct":round(100*inside.mean(),2)}
        # lander-height vs terrain: SfS terrain with the LOLA ground height at the lander
        sfsdem=core.Dem.open(D/"sfs/Site01_sfs_merged_5mpp.tif"); far=core.Dem.open(D/"pgda90/LDEM_80S_80MPP_ADJ.TIF")
        lola=core.Dem.open(core.site_files("Site01",D)["surf"][1]); zl=float(lola.sample_lonlat(np.array([lon]),np.array([lat]))[0])
        hx=ext.compute_horizon_x(lon,lat,sfsdem,far,1.0,z_override=zl,k_cand=1)
        r2,_=met(hx.elev,e); rec["sfs_terrain_lola_ground"]=dict(r2,ground_m=round(zl,2))
        # position grid
        near=lola; x0,y0=near.to_grid.transform(lon,lat); g=[]
        for dx in range(-100,101,25):
            for dy in range(-100,101,25):
                f=W/f"hz/{key}_nominal_m1.npz"; fs=J/f"sfs_{key}_m1.npz" if dx==0 and dy==0 else J/f"sfspos_{key}_x{dx}_y{dy}.npz"
                fl=f if dx==0 and dy==0 else J/f"pos_{key}_nominal_x{dx}_y{dy}.npz"
                if not fs.exists(): continue
                lo,la=near.to_grid.transform(x0+dx,y0+dy,direction="INVERSE"); ee={}
                for b in ("sun","earth"): ee[f"{b}_az"],ee[f"{b}_el"]=transfer_azel(e[f"{b}_az"],e[f"{b}_el"],lon,lat,float(lo),float(la))
                a,_=met(np.load(fs)["elev"],e,ee); b_,_=met(np.load(fl)["elev"],e,ee)
                g.append({"dx":dx,"dy":dy,"sfs":a,"lola":b_})
        if g:
            ds=[x["sfs"]["sun"]-x["lola"]["sun"] for x in g]; dy_=[x["sfs"]["year"]-x["lola"]["year"] for x in g]
            ok=lambda r: r["sun"]>=70 and r["both"]>=40 and r["gap"]<=120
            rec["grid"]={"n":len(g),"demo_sun_diff_mean":round(float(np.mean(ds)),2),"demo_sun_absdiff_max":round(float(np.max(np.abs(ds))),2),
                         "year_sun_diff_mean":round(float(np.mean(dy_)),2),"year_sun_absdiff_median":round(float(np.median(np.abs(dy_))),2),
                         "pass_all3_sfs":sum(ok(x["sfs"]) for x in g),"pass_all3_lola":sum(ok(x["lola"]) for x in g),
                         "verdict_changes":sum(ok(x["sfs"])!=ok(x["lola"]) for x in g),"cells":g}
    out[key]=rec
    print(key,json.dumps({k:v for k,v in rec.items() if k!="grid"},default=str)[:1800]); 
    if "grid" in rec: print(" grid",{k:v for k,v in rec["grid"].items() if k!="cells"})
json.dump(out,open(W/"sfs_result.json","w"),indent=1,default=bool)
