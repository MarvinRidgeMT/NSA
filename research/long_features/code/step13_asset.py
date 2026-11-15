"""Asset Layout Twin pilot: per-asset skylines + lander self-shadowing (illustrative geometry, not a real lander design).
Lander body = vertical cylinder radius 2 m, height 4 m above ground, centred on the RoI centroid."""
import json, math
from pathlib import Path
import numpy as np
from polaris_batch import core
from build_data import transfer_azel, interp, longest
D=Path("data/external"); W=Path("work")
R={"Site04_ROI3":("Site04",-89.78012,-156.32023),"Site01_ROI6":("Site01",-89.47409,-137.3813)}
BODY_R, BODY_H = 2.0, 4.0
ASSETS=[("Solar panel, ground mast",0.0,5.0,1.0,"sun"),("Solar panel, deck top",0.0,0.0,4.5,"sun"),("Antenna, away from Earth",0.0,-5.0,2.0,"earth"),("Antenna, Earth side",0.0,5.0,2.0,"earth")]
far=core.Dem.open(D/"pgda90/LDEM_80S_80MPP_ADJ.TIF"); out={}
for key,(site,lat,lon) in R.items():
    near=core.Dem.open(core.site_files(site,D)["surf"][1]); e=np.load(W/f"eph_{key}.npz")
    x0,y0=near.to_grid.transform(lon,lat); zc=float(near.sample_xy(np.array([x0]),np.array([y0]))[0])
    rec=[]; states={}
    for name,dx,dy,h,body in ASSETS:
        lo,la=near.to_grid.transform(x0+dx,y0+dy,direction="INVERSE"); lo,la=float(lo),float(la)
        hz=core.compute_horizon(lo,la,near,far,mast_m=h,near_step=1.0)
        elev=hz.elev.copy(); za=hz.h0-h
        d=math.hypot(dx,dy)
        if d>BODY_R:   # self-shadow sector: lander body seen from the asset
            p1,p2,dl=math.radians(la),math.radians(lat),math.radians(lon-lo)
            brg=math.degrees(math.atan2(math.sin(dl)*math.cos(p2),math.cos(p1)*math.sin(p2)-math.sin(p1)*math.cos(p2)*math.cos(dl)))%360
            half=math.degrees(math.asin(BODY_R/d)); top=math.degrees(math.atan2((zc+BODY_H)-(za+h),d-BODY_R))
            dd=np.abs((hz.az-brg+180)%360-180); sel=dd<=half
            elev[sel]=np.maximum(elev[sel],top); body_sector=[round(brg,1),round(half,1),round(top,2)]
        else: body_sector=None
        sa,se=transfer_azel(e["sun_az"],e["sun_el"],lon,lat,lo,la); ea,ee=transfer_azel(e["earth_az"],e["earth_el"],lon,lat,lo,la)
        sun_t=se>interp(hz.elev,sa); sun_b=se>interp(elev,sa); earth_t=ee>interp(hz.elev,ea); earth_b=ee>interp(elev,ea)
        D_,Y=slice(312,649),slice(312,312+8761)
        r={"asset":name,"offset_m":[dx,dy],"height_m":h,"body_sector_az_halfwidth_topel":body_sector,
           "sun_demo_terrain":round(100*sun_t[D_].mean(),2),"sun_demo_with_body":round(100*sun_b[D_].mean(),2),
           "sun_12mo_terrain":round(100*sun_t[Y].mean(),2),"sun_12mo_with_body":round(100*sun_b[Y].mean(),2),
           "earth_12mo_terrain":round(100*earth_t[Y].mean(),2),"earth_12mo_with_body":round(100*earth_b[Y].mean(),2),
           "self_shadow_hours_12mo":int((sun_t[Y]&~sun_b[Y]).sum())}
        rec.append(r); states[name]=(sun_b,earth_b); print(key,r,flush=True)
    Y=slice(312,312+8761)
    anyp=states[ASSETS[0][0]][0]|states[ASSETS[1][0]][0]
    out[key]={"assets":rec,"power_any_panel_12mo_pct":round(100*anyp[Y].mean(),2),"longest_no_panel_lit_12mo_h":int(longest((~anyp[Y])[None,:])[0]),
              "power_and_link_12mo_pct":round(100*(anyp&states[ASSETS[3][0]][1])[Y].mean(),2),"power_and_link_bad_layout_12mo_pct":round(100*(anyp&states[ASSETS[2][0]][1])[Y].mean(),2),
              "body":{"radius_m":BODY_R,"height_m":BODY_H,"note":"illustrative cylinder, not a lander design"}}
    print(key,{k:v for k,v in out[key].items() if k!="assets"})
json.dump(out,open(W/"asset.json","w"),indent=1)
