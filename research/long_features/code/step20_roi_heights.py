import csv, json, numpy as np, rasterio
from pathlib import Path
from polaris_batch import core
D=Path("data/external"); S=Path("/home/claude/dl/sfs")
reg={"Site01":"A3CLR22_6_Connecting_Ridge","Site11":"A3CLR22_9_deGerlache_Rim","Site07":"A3CLR22_8_Peak_Near_Shackleton"}
rows=[]
for r in csv.DictReader(open("data/polaris_roi_sites.csv")):
    if r["site"] not in reg: continue
    f=next((S/reg[r["site"]]).glob("*GLDELEV_005.tif")); x,y=float(r["x_m"]),float(r["y_m"])
    with rasterio.open(f) as d: a=d.read(1).astype(float); a[a<-1e30]=np.nan; inv=~d.transform
    sfs=core.Dem(f,a,inv,None,5.0); lola=core.Dem.open(core.site_files(r["site"],D)["surf"][1]); err=core.Dem.open(core.site_files(r["site"],D)["toterr"][1])
    pts=np.array([(x+dx,y+dy) for dx in range(-50,51,5) for dy in range(-50,51,5)])
    ds=sfs.sample_xy(pts[:,0],pts[:,1])-lola.sample_xy(pts[:,0],pts[:,1])
    cs=float(sfs.sample_xy(np.array([x]),np.array([y]))[0]); cl=float(lola.sample_xy(np.array([x]),np.array([y]))[0]); sg=float(err.sample_xy(np.array([x]),np.array([y]))[0])
    rows.append({"site":r["site"],"roi":int(r["roi"]),"sfs_minus_lola_at_centroid_m":round(cs-cl,2),"toterr_m":round(sg,3),"z_sigma":round((cs-cl)/sg,1),"sfs_minus_lola_median_100m_m":round(float(np.nanmedian(ds)),2)})
d=np.array([x["sfs_minus_lola_at_centroid_m"] for x in rows]); m=np.array([x["sfs_minus_lola_median_100m_m"] for x in rows])
summ={"n":len(rows),"centroid_diff_mean":round(float(d.mean()),2),"centroid_diff_min":float(d.min()),"centroid_diff_max":float(d.max()),"n_positive":int((d>0).sum()),"median_100m_diff_mean":round(float(m.mean()),2),"rows":rows}
for x in rows: print(x)
print({k:v for k,v in summ.items() if k!="rows"})
o=json.load(open("work/sfs_result.json")); o["_roi_heights"]=summ; json.dump(o,open("work/sfs_result.json","w"),indent=1,default=bool)
