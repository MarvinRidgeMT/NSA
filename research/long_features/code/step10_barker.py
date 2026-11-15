"""Barker et al. 2021 (PSS 203, 105119) Table 2 comparison: Site01 RoIs 1-7, average Sun illumination
(visible disc fraction, hourly, 2024-01-01 .. 2026-01-01), RoI-averaged per DEM (case A), at 5 m (and 1 m at the centroid)."""
import json, math, numpy as np
from pathlib import Path
from polaris_batch import core
from build_data import transfer_azel, interp
W=Path("work"); J=W/"jobs"
A1_5=[89.26,88.51,84.53,88.12,85.71,87.35,82.79]; A1_1=[68.03,70.32,67.51,69.61,70.38,71.15,67.36]
e=np.load(W/"eph_barker_roi4.npz"); lon0,lat0=float(e["lon"]),float(e["lat"]); rs=e["diam"]/7200.0
jobs={j["out"]:j for f in ("jobs_C.json","jobs_C2.json","jobs_S.json") for j in json.load(open(W/f))}
dems=["nominal"]+[f"clone_{n:04d}" for n in range(1,21) if (J/f"barker_roi1_p0_clone_{n:04d}_m5.npz").exists()]
cache={}
def ill(j):
    k=(round(j["lon"],7),round(j["lat"],7))
    if k not in cache: cache[k]=transfer_azel(e["az"],e["el"],lon0,lat0,j["lon"],j["lat"])
    az,el=cache[k]; z=np.load(J/f"{j['out']}.npz")
    return 100*float(core.disc_fraction_above(el,interp(z["elev"],az),rs).mean())
rows=[]
for roi in range(1,8):
    r={"roi":roi,"barker_A1_5m":A1_5[roi-1],"barker_A1_1m":A1_1[roi-1]}
    v5={d:np.mean([ill(jobs[f"barker_roi{roi}_p{k}_{d}_m5"]) for k in range(5)]) for d in dems}
    cl=[v5[d] for d in dems[1:]]
    r.update(ours5_nom=round(v5["nominal"],2),ours5_cl_min=round(min(cl),2),ours5_cl_median=round(float(np.median(cl)),2))
    if all(f"barker_roi{roi}_p{k}_sfs_m5" in jobs and (J/f"barker_roi{roi}_p{k}_sfs_m5.npz").exists() for k in range(5)):
        r["ours5_sfs"]=round(float(np.mean([ill(jobs[f"barker_roi{roi}_p{k}_sfs_m5"]) for k in range(5)])),2)
    v1={d:ill(jobs[f"barker_roi{roi}_p0_{d}_m1"]) for d in dems}
    r.update(ours1_centroid_nom=round(v1["nominal"],2),ours1_centroid_cl_min=round(min(v1[d] for d in dems[1:]),2))
    rows.append(r); print(r,flush=True)
d=[x["ours5_cl_min"]-x["barker_A1_5m"] for x in rows]; dn=[x["ours5_nom"]-x["barker_A1_5m"] for x in rows]
rk=lambda a: list(np.argsort(np.argsort(a)))
from scipy.stats import spearmanr
rho=spearmanr([x["ours5_cl_min"] for x in rows],A1_5).correlation
note=(f"5 m above the surface, 1 Jan 2024 – 1 Jan 2026 hourly, visible Sun-disc fraction averaged over 5 sampled pixels per RoI. "
      f"Our worst-of-{len(dems)-1}-clones minus Barker's 1st percentile of 100: mean {np.mean(d):+.2f}, range {min(d):+.2f} to {max(d):+.2f} pts; "
      f"nominal minus Barker: mean {np.mean(dn):+.2f} pts; rank correlation {rho:.2f}. RoI 4 (Barker's 88.1 %): nominal {rows[3]['ours5_nom']:.1f} %, worst clone {rows[3]['ours5_cl_min']:.1f} %. "
      f"Differences: 5 pixels not the full RoI, {len(dems)-1} not 100 clones, our 720-bin horizon vs Barker's method.")
sf=[x["ours5_sfs"]-x["barker_A1_5m"] for x in rows if "ours5_sfs" in x]
if sf: note+=f" On the NASA GSFC SfS terrain instead of LOLA: mean {np.mean(sf):+.2f} pts vs Barker (range {min(sf):+.2f} to {max(sf):+.2f})."
json.dump({"rows":rows,"sfs_mean_diff":float(np.mean(sf)) if sf else None,"note":note,"mean_diff_clmin":float(np.mean(d)),"mean_diff_nom":float(np.mean(dn)),"spearman":float(rho)},open(W/"barker_result.json","w"),indent=1)
print(note)
