import sys
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from polaris_batch import core
D = Path("data/external")
jobs = [(core.PGDA90_80M, D/"pgda90/LDEM_80S_80MPP_ADJ.TIF")]
for s in ("Site04","Site01"):
    for k in ("surf","toterr"): jobs.append(core.site_files(s, D)[k])
    for n in range(1, 21): jobs.append(core.clone_file(s, n, D))
def go(j):
    try: core.download(*j); return j[1].name, j[1].stat().st_size
    except Exception as e: return j[1].name, repr(e)
with ThreadPoolExecutor(6) as ex:
    for r in ex.map(go, jobs): print(*r, flush=True)
