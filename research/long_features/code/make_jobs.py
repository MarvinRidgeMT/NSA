import json, numpy as np, shapefile
from pathlib import Path
from polaris_batch import core
D=Path("data/external")
R={"Site04_ROI3":("Site04",-89.78012,-156.32023),"Site01_ROI6":("Site01",-89.47409,-137.3813)}
DEMS=["nominal"]+[f"clone_{n:04d}" for n in range(1,21)]
A=[];B=[];C=[]
for key,(site,lat,lon) in R.items():
    for m in (1.25,1.5,1.75,2,3,5,10):
        for d in DEMS: A.append(dict(out=f"mast_{key}_{d}_m{m:g}",site=site,dem=d,lon=lon,lat=lat,mast=m))
    near=core.Dem.open(core.site_files(site,D)["surf"][1])
    x0,y0=near.to_grid.transform(lon,lat)
    for dx in range(-100,101,25):
        for dy in range(-100,101,25):
            lo,la=near.to_grid.transform(x0+dx,y0+dy,direction="INVERSE")
            dems=DEMS if (abs(dx)<=25 and abs(dy)<=25) else ["nominal"]
            for d in dems: B.append(dict(out=f"pos_{key}_{d}_x{dx}_y{dy}",site=site,dem=d,lon=float(lo),lat=float(la),mast=1.0,dx=dx,dy=dy))
# Barker 2021 Table 2: Site01 RoIs, pixels inside polygons
near=core.Dem.open(core.site_files("Site01",D)["surf"][1])
sf=shapefile.Reader(str(D/"pgda78/Site01/roi/Site01_ROIs.shp"))
from matplotlib.path import Path as MP
rng=np.random.default_rng(1); meta={}
print(sf.fields)
for i,shp in enumerate(sf.shapes()):
    rec=sf.record(i); pts=np.array(shp.points); poly=MP(pts)
    xs=np.arange(pts[:,0].min(),pts[:,0].max(),5.0); ys=np.arange(pts[:,1].min(),pts[:,1].max(),5.0)
    gx,gy=np.meshgrid(xs,ys); inside=poly.contains_points(np.c_[gx.ravel(),gy.ravel()])
    cand=np.c_[gx.ravel(),gy.ravel()][inside]
    cx,cy=pts[:-1].mean(0)
    sel=[(cx,cy)]+[tuple(cand[k]) for k in rng.choice(len(cand),4,replace=False)]
    roi=i+1
    meta[roi]={"record":list(rec),"n_inside_5m_px":int(inside.sum()),"area_m2":float(inside.sum()*25),"centroid":[float(cx),float(cy)],"pixels":[list(map(float,p)) for p in sel]}
    for k,(x,y) in enumerate(sel):
        lo,la=near.to_grid.transform(x,y,direction="INVERSE")
        for d in ["nominal"]+[f"clone_{n:04d}" for n in range(1,11)]:
            for m,ns in ((5.0,2.0),(1.0,1.0)):
                C.append(dict(out=f"barker_roi{roi}_p{k}_{d}_m{m:g}",site="Site01",dem=d,lon=float(lo),lat=float(la),mast=m,near_step=ns,roi=roi,px=k))
json.dump(meta,open("work/barker_rois.json","w"),indent=1)
for n,L in (("A",A),("B",B),("C",C)): json.dump(L,open(f"work/jobs_{n}.json","w")); print(n,len(L))
print({k:(v["area_m2"],v["centroid"]) for k,v in meta.items()})
