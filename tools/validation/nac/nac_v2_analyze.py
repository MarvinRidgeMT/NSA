"""Analysis for NAC protocol v2 (+A1). Metrics exactly as the frozen protocol states."""
import json, numpy as np
D = json.load(open('nac_v2_results.json'))
out = {'protocol_sha256': D['protocol_sha256'], 'missing': D['missing'], 'areas': {}}
for area in ['C_site07_roi1', 'D_site11_roi1']:
    keys = [k for k in D['images'] if k.startswith(area + '|')]
    obs = np.concatenate([np.array(D['images'][k]['obs']) for k in keys]) if keys else np.array([])
    mar = np.concatenate([np.array(D['images'][k]['margin']) for k in keys]) if keys else np.array([])
    el = np.concatenate([np.array(D['images'][k]['el']) for k in keys]) if keys else np.array([])
    ets = sorted(D['meta'][k]['et'] for k in keys)
    lit = obs == 'L'
    def metrics(m):
        o, p = lit[m], mar[m] > 0
        tp, tn, fp, fn = int(np.sum(o & p)), int(np.sum(~o & ~p)), int(np.sum(~o & p)), int(np.sum(o & ~p))
        n = tp + tn + fp + fn
        tpr = tp / (tp + fn) if tp + fn else float('nan'); tnr = tn / (tn + fp) if tn + fp else float('nan')
        po = (tp + tn) / n; pe = ((tp + fp) * (tp + fn) + (tn + fn) * (tn + fp)) / n**2
        return dict(n=n, obs_lit=int(o.sum()), obs_shadow=int((~o).sum()), tp=tp, tn=tn, fp=fp, fn=fn, agreement=po, lit_recall=tpr, shadow_recall=tnr,
                    balanced_accuracy=(tpr + tnr) / 2, kappa=(po - pe) / (1 - pe) if pe < 1 else float('nan'))
    allm = np.ones(len(obs), bool); exc = np.abs(mar) >= 0.5
    edges = np.arange(np.floor(mar.min() / 0.25) * 0.25, np.ceil(mar.max() / 0.25) * 0.25 + 0.25, 0.25)
    idx = np.digitize(mar, edges) - 1
    bins = []
    for b in range(len(edges) - 1):
        s = idx == b
        if s.sum(): bins.append(dict(centre=float(edges[b] + 0.125), n=int(s.sum()), lit_frac=float(lit[s].mean())))
    cross = None
    for i, b in enumerate(bins):
        if b['lit_frac'] >= 0.5:
            if i == 0: cross = b['centre']
            else:
                a = bins[i - 1]; cross = a['centre'] + (0.5 - a['lit_frac']) * (b['centre'] - a['centre']) / (b['lit_frac'] - a['lit_frac'])
            break
    me, ma = metrics(exc), metrics(allm)
    verdict = 'PASS' if (me['obs_shadow'] >= 200 and me['balanced_accuracy'] >= 0.90 and cross is not None and abs(cross) <= 0.5) else 'NOT PASS'
    out['areas'][area] = dict(images=len(keys), dates_utc_et=[ets[0], ets[-1]] if ets else None, sun_el_range=[float(el.min()), float(el.max())] if len(el) else None,
                              all=ma, excl_near_critical=me, crossing_deg=cross, bins=bins, verdict=verdict)
v = [a['verdict'] for a in out['areas'].values()]
out['verdict'] = 'INCOMPLETE' if D['missing'] else ('PASS' if all(x == 'PASS' for x in v) else 'NOT PASS')
json.dump(out, open('nac_v2_summary.json', 'w'), indent=1)
for k, a in out['areas'].items():
    e = a['excl_near_critical']
    print(k, 'images', a['images'], 'points', a['all']['n'], '| excl n', e['n'], 'shadow', e['obs_shadow'], 'agree %.3f balacc %.3f kappa %.3f litrec %.3f shrec %.3f' % (e['agreement'], e['balanced_accuracy'], e['kappa'], e['lit_recall'], e['shadow_recall']),
          '| all balacc %.3f' % a['all']['balanced_accuracy'], '| crossing', None if a['crossing_deg'] is None else round(a['crossing_deg'], 3), a['verdict'], 'sunEl', a['sun_el_range'])
print('OVERALL', out['verdict'])
