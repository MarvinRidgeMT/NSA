"""Full-ray-march test of the clone-error greedy plan (first 5 and all 10 cells), same protocol as step4 (20 clones, 12 months)."""
import json, sys, numpy as np
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
import step4_hotspots as s4
from build_data import interp
W=Path("work")
key=sys.argv[1]
hc=json.load(open(W/"hot_corr.json"))
plan=[p for p in hc[key]["plan_clone_errors"] if p["k"]>0]
sets={"clone_greedy_5":[tuple(p["cell_rc"]) for p in plan[:5]],"clone_greedy_10":[tuple(p["cell_rc"]) for p in plan[:10]]}
jobs=[(key,n,cells,tag) for tag,cells in sets.items() for n in range(1,21)]
res={}
with ProcessPoolExecutor(2) as ex:
    for k,n,tag,elev in ex.map(s4._march,jobs): res[(tag,n)]=elev
e=np.load(W/f"eph_{key}.npz"); az,el=e["sun_az"][312:312+8761],e["sun_el"][312:312+8761]
truth=np.array([el>interp(np.load(W/f"hz/{key}_clone_{n:04d}_m1.npz")["elev"],az) for n in range(1,21)])
out={tag:int((np.array([el>interp(res[(tag,n)],az) for n in range(1,21)])!=truth).sum()) for tag in sets}
print(key,out)
hc[key]["full_ray_test"]=out; json.dump(hc,open(W/"hot_corr.json","w"),indent=1)
