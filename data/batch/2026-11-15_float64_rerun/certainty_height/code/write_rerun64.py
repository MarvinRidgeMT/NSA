import json, csv, hashlib, numpy as np, datetime, shutil
from pathlib import Path
V=Path('/home/claude/val'); O=Path('/mnt/user-data/outputs/rerun64/certainty_height')
sha=lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()
def st(v): v=np.array(v); return dict(min=v.min(),p10=np.percentile(v,10),median=np.median(v),p90=np.percentile(v,90),max=v.max(),std=v.std())
rows=[]; runs=[]
for site,roi,f in [('Site01',6,'certainty_site01_roi6_f64.json'),('Site04',3,'certainty_f64.json')]:
    d=json.load(open(V/f))
    for m in sorted({r['mast_m'] for r in d['rows']}):
        rr=[r for r in d['rows'] if r['mast_m']==m]; nom=[r for r in rr if r['dem']=='nominal'][0]; cl=[r for r in rr if r['dem']!='nominal']
        row={'site':site,'roi':roi,'mast_m':m,'n_clones':len(cl)}
        for met in ['sun_centre_pct','both_centre_pct']:
            s=st([r[met] for r in cl]); row[f'{met}_nominal']=round(nom[met],3)
            for k in ['min','p10','median','p90','max','std']: row[f'{met}_{k}']=round(float(s[k]),3)
        for met,thr in [('sun_centre_pct',70),('both_centre_pct',40)]:
            k=sum(r[met]>=thr for r in cl); row[f'pass_{met}>={thr}']=f'{k}/{len(cl)}'
            row[f'verdict_{met}']='robust pass' if k==len(cl) else ('robust fail' if k==0 else 'fragile')
        rows.append(row)
        for r in rr: runs.append({'site':site,'roi':roi,'mast_m':m,'dem':r['dem'],'z0_m':round(r['z0'],4),'sun_centre_pct':round(r['sun_centre_pct'],3),'both_centre_pct':round(r['both_centre_pct'],3),'sun_samples':r['sun_samples'],'both_samples':r['both_samples']})
for name,data in [('clone_sweep_summary.csv',rows),('clone_sweep_runs.csv',runs)]:
    with open(O/name,'w',newline='') as fh:
        w=csv.DictWriter(fh,fieldnames=list(data[0].keys())); w.writeheader(); w.writerows(data)
(O/'code').mkdir(exist_ok=True)
shutil.copy(V/'certainty_f64.py',O/'code/certainty_f64.py'); shutil.copy(V/'write_rerun64.py',O/'code/write_rerun64.py')
inputs={'pgda78_nominal_Site04':sha(V/'pgda78/Site04_final_adj_5mpp_surf.tif'),'pgda78_nominal_Site01':sha(V/'pgda78/Site01_final_adj_5mpp_surf.tif'),
 'pgda90_80mpp':sha(V/'pgda90/LDEM_80S_80MPP_ADJ.TIF'),'ephemeris_bundle_polaris-x5d-roi-2026-11-14-v2.json':sha('/home/claude/px/web/public/bundles/polaris-x5d-roi-2026-11-14-v2.json'),
 'clones_Site04':{f'{n:04d}':sha(V/f'pgda78/clones/Site04_final_adj_5mpp_{n:04d}_err.tif') for n in range(1,21)},
 'clones_Site01':{f'{n:04d}':sha(V/f'pgda78/clones01/Site01_final_adj_5mpp_{n:04d}_err.tif') for n in range(1,21)}}
man={'created_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(timespec='seconds'),
 'command':'SITE=site04_roi3 python3 code/certainty_f64.py f64 ; SITE=site01_roi6 python3 code/certainty_f64.py f64 ; python3 code/write_rerun64.py',
 'label':'SOURCE-BASED, UNVALIDATED (corrected precision; not an external validation)',
 'note':('Float64 re-run of data/batch/2026-11-14 certainty_height + certainty_height_fine (polaris_batch v2). The original run held terrain heights '
  'in float32, so R + h (R = 1,737,400 m) was rounded to about 0.125 m and the ray elevation angles carried that error (LONG_FEATURES_2026-11-15 section 0). '
  'Run with float32 heights, this script reproduces the original summary to within 0.001 points (same definitions: 720 bins at (k+0.5)*0.5 deg, '
  'linear interpolation between bins, near 1 m steps to 25 km, far 80 m to 280 km, h0 = z0 + mast, Sun/Earth centre vs horizon, the bundle\'s 337 '
  'hourly Horizons samples 2026-11-14 00:00 to 2026-11-28 00:00 UTC). Only the precision changes. Site01 ROI6: identical to the original. '
  'Site04 ROI3: masts 1-1.75 m change (1 m Sun nominal 93.769 -> 94.362 = the repo bundle\'s 318/337; clone values shift by up to 1.8 points); 2 m and above identical. '
  'Certainty Height, agreement mast and pass counts are unchanged. Columns: only the two metrics the viewer reads (sun_centre_pct, both_centre_pct); '
  'sun_disc, earth_any and gap metrics were not re-run. The original folder is untouched.'),
 'author':'Claude (Penumbra session), 15 Nov 2026','inputs_sha256':inputs,
 'outputs_sha256':{n:sha(O/n) for n in ['clone_sweep_summary.csv','clone_sweep_runs.csv','code/certainty_f64.py','code/write_rerun64.py']}}
json.dump(man,open(O/'manifest.json','w'),indent=1)
