"""Out-of-sample test: plan on clones 1-10 (hot_corr_train.json), test with full ray marches on clones 11-20."""
import json, sys, numpy as np
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
import step4_hotspots as s4
from build_data import interp
W=Path("work"); key=sys.argv[1]; TEST=range(11,21)
plan=[p for p in json.load(open(W/"hot_corr_train.json"))[key]["plan_clone_errors"] if p["k"]>0]
st=json.load(open(W/"hotspots_report.json"))["strategies"][key]
sets={"none":[],"lander_only":[tuple(c) for c in st["observer_only"]],"toterr_top10+lander":[tuple(c) for c in st["hotspots_top10+observer"]],
      "nearest10+lander":[tuple(c) for c in st["nearest10+observer"]],"clone_plan_5":[tuple(p["cell_rc"]) for p in plan[:5]],"clone_plan_10":[tuple(p["cell_rc"]) for p in plan[:10]]}
jobs=[(key,n,cells,tag) for tag,cells in sets.items() for n in TEST]
res={}
with ProcessPoolExecutor(2) as ex:
    for k,n,tag,elev in ex.map(s4._march,jobs): res[(tag,n)]=elev
e=np.load(W/f"eph_{key}.npz"); az,el=e["sun_az"][312:312+8761],e["sun_el"][312:312+8761]
truth=np.array([el>interp(np.load(W/f"hz/{key}_clone_{n:04d}_m1.npz")["elev"],az) for n in TEST])
out={tag:{"cells":len(c),"clone_hours_wrong":int((np.array([el>interp(res[(tag,n)],az) for n in TEST])!=truth).sum())} for tag,c in sets.items()}
print(key,out)
hc=json.load(open(W/"hot_corr.json")) if (W/"hot_corr.json").exists() else {}
hc.setdefault(key,{})["out_of_sample"]={"train_clones":"1-10","test_clones":"11-20","results":out,"plan_train":plan}
json.dump(hc,open(W/"hot_corr.json","w"),indent=1)
