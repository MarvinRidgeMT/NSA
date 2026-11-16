import json, numpy as np
from pathlib import Path
from step5_strip import interp_bins, longest_run, DEMS, HZ, W, L
from numpy.lib.stride_tricks import sliding_window_view
out={}
from sites import selected, merge_dump
for key in selected():
    e=np.load(W/f"eph_{key}.npz"); t=e["time"]
    i0=312-7*24; n=14*24+1  # starts from 2026-11-07 00:00 to 11-21 00:00
    sl=slice(i0,i0+n+L-1)
    rows={}
    for dem in DEMS:
        z=np.load(HZ/f"{key}_{dem}_m1.npz")
        sun=e["sun_el"][sl]>interp_bins(z["elev"],e["sun_az"][sl]); earth=e["earth_el"][sl]>interp_bins(z["elev"],e["earth_az"][sl])
        ws=sliding_window_view(sun,L); wb=sliding_window_view(sun&earth,L)
        rows[dem]=(100*ws.mean(1),100*wb.mean(1),longest_run(~ws))
    cl=np.array([rows[d][0] for d in DEMS[1:]]); clb=np.array([rows[d][1] for d in DEMS[1:]]); clg=np.array([rows[d][2] for d in DEMS[1:]])
    rec=[]
    for j in range(n):
        h=j-7*24
        rec.append({"slip_h":h,"start":str(t[i0+j]),"sun_nom":round(float(rows["nominal"][0][j]),2),"sun_min":round(float(cl[:,j].min()),2),"sun_max":round(float(cl[:,j].max()),2),
                    "pass_sun70":int((cl[:,j]>=70).sum()),"both_nom":round(float(rows["nominal"][1][j]),2),"both_min":round(float(clb[:,j].min()),2),
                    "pass_both40":int((clb[:,j]>=40).sum()),"gap_nom":int(rows["nominal"][2][j]),"gap_max":int(clg[:,j].max())})
    out[key]=rec
    for h in (-168,-72,-48,-24,-12,-6,0,6,12,24,48,72,168):
        r=rec[h+168]; print(key,f"{h:+5d}h",r)
    # largest slip with all 20 clones >=70 % Sun and nominal unchanged
    ok=[r["slip_h"] for r in rec if r["pass_sun70"]==20]
    lo=max([r["slip_h"] for r in rec if r["slip_h"]<=0 and r["pass_sun70"]<20], default=None); hi=min([r["slip_h"] for r in rec if r["slip_h"]>=0 and r["pass_sun70"]<20], default=None)
    print(key,"all-20-pass interval around demo start: first failing slip before",lo,"after",hi)
merge_dump(W/"strip/slip_pm7d.json",out)
