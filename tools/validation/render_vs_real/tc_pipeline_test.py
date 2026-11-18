"""A11.4 pipeline test: settle the Kaguya TC start-time convention and sample axis on dev rows.

    python -m tools.validation.render_vs_real.tc_pipeline_test

For each pipeline-test row (selection.json pipelineTestImages) and each convention (start isis | label x flip no | yes;
orbit = the label's RISE solution): geometry -> render (PGDA 78, Hapke) -> one rigid registration over +- PT_RADIUS_M of
the render's Sobel gradients to the real image's. Writes results_tc/pipeline_test.json with every offset and the A11.4
decision. Scores from this test are not used for anything else.
Decision rule (A11.4): an option is adopted when its median |offset| is below ADOPT_BELOW_M and the other option's median
is at least SEPARATION x larger; the flip is decided per satellite moving direction; an unsettled start keeps 'isis', an
unsettled moving direction is gated.
"""
from __future__ import annotations

import json
import math
import statistics

import numpy as np

from . import score as S
from . import tc_geometry as TG
from .common import read_catalogue
from .run import AU, TSI, ground_offset
from .tc_common import TC_GEOM_DIR, TC_RENDER_DIR, TC_RESULTS, guard
from .tc_run import load_real, render_row, row_context, square_and_gsd

PT_RADIUS_M = 2000.0
ADOPT_BELOW_M, SEPARATION = 600.0, 2.0


def offset(G):
    out = TC_RENDER_DIR / G['tag']
    real, special, sat = load_real(G)
    R = dict(np.load(out / 'pgda78_5m.npz'))
    M, P0, Psc = row_context(G)
    in_sq, gsd = square_and_gsd(G, R, M, P0, Psc)
    E = TSI / (G['sunDistM'] / AU) ** 2
    rend = np.where(R['hit'], math.pi * R['beauty'].astype(np.float64) / E, np.nan)
    window = S.analysis_window(in_sq, special) & np.isfinite(real) & np.isfinite(rend)
    if window.sum() < 500:
        return {'status': 'window too small'}
    nsm = window & ~sat
    med = float(np.median(real[nsm]))
    rn = np.where(np.isfinite(real) & ~special, real / med, 1.0)
    mm = float(np.median(rend[nsm]))
    mn = np.where(np.isfinite(rend), rend / (mm if mm > 0 else med), 0.0)
    gm = float(np.median(gsd[window]))
    reg = S.register(rn, mn, nsm, PT_RADIUS_M / gm, refine=0.5, step=0.5)
    al, ac = ground_offset(R['pos'].astype(np.float64), reg['dy'], reg['dx'], np.asarray(G['sunEnu']))
    return {'status': 'ok', 'dyPx': reg['dy'], 'dxPx': reg['dx'], 'offsetM': math.hypot(reg['dy'], reg['dx']) * gm,
            'alongSunM': al, 'acrossSunM': ac, 'ncc': reg['ncc'], 'atBound': reg['atBound'], 'pxM': gm}


def decide(meds):
    """meds: {option: (median, n)} for two options -> (adopted option or None, resolved)."""
    have = {k: v for k, v in meds.items() if v[1]}
    if len(have) < 2:
        return None, False
    best = min(have, key=lambda k: have[k][0])
    other = next(k for k in have if k != best)
    ok = have[best][0] < ADOPT_BELOW_M and have[other][0] >= SEPARATION * have[best][0]
    return (best if ok else None), ok


def main():
    sel = json.loads((TC_RESULTS / 'selection.json').read_text())
    cat = {(r['product_id'], r['site']): r for r in read_catalogue()}
    rows = [(im, s) for im in sel['pipelineTestImages'] for s in im['sites']
            if any(p['product_id'] == im['product_id'] and p['site'] == s for p in sel['pipelineTest'])]
    guard([im['product_id'] for im, _ in rows])
    res = []
    for im, site in rows:
        for start in ('isis', 'label'):
            for flip in (False, True):
                try:
                    rec = TG.one(im, site, cat[(im['product_id'], site)], start=start, flip=flip, orbit='label')
                except Exception as e:
                    rec = {'status': 'failed', 'reason': f'{type(e).__name__}: {str(e)[:200]}'}
                entry = {'product_id': im['product_id'], 'site': site, 'start': start, 'flip': flip,
                         'camera': rec.get('camera'), 'movingDirection': rec.get('moving_direction'),
                         'cornersVsLabelMaxM': rec.get('corners_vs_label_max_m'), 'geometry': rec['status'],
                         'reason': rec.get('reason', '')}
                if rec['status'] == 'ok':
                    gp = TC_GEOM_DIR / f"{rec['tag']}.json"
                    G = render_row(gp, 16, products=['pgda78_5m'], variants=False)
                    G['tag'] = rec['tag']
                    try:
                        entry.update(offset(G))
                    except Exception as e:
                        entry.update({'status': 'failed', 'reason': f'{type(e).__name__}: {str(e)[:200]}'})
                res.append(entry)
                print(json.dumps(entry, default=str), flush=True)

    def med(filt):
        v = [e['offsetM'] for e in res if e.get('status') == 'ok' and filt(e)]
        return (statistics.median(v), len(v)) if v else (float('nan'), 0)
    dec = {}
    a = {k: med(lambda e, k=k: e['start'] == k and not e['flip']) for k in ('isis', 'label')}
    st, ok = decide(a)
    dec['start'] = {'medians_m': a, 'adopted': st or 'isis', 'resolved': ok}
    st = dec['start']['adopted']
    dec['flip'] = {}
    for mdir in sorted({e['movingDirection'] for e in res if e.get('movingDirection') is not None}):
        b = {f: med(lambda e, f=f, m=mdir: e['start'] == st and e['flip'] is f and e['movingDirection'] == m) for f in (False, True)}
        f, ok = decide(b)
        dec['flip'][str(mdir)] = {'medians_m': {str(k): v for k, v in b.items()}, 'flip': f, 'resolved': ok}
    adopted = [e['offsetM'] for e in res if e.get('status') == 'ok' and e['start'] == st and
               dec['flip'].get(str(e['movingDirection']), {}).get('resolved') and
               e['flip'] is dec['flip'][str(e['movingDirection'])]['flip']]
    dec['registrationRadiusM'] = max(150.0, 3 * statistics.median(adopted)) if adopted else None
    (TC_RESULTS / 'pipeline_test.json').write_text(json.dumps({'rule': 'A11.4', 'radiusM': PT_RADIUS_M, 'rows': res,
                                                                'decision': dec}, indent=1, default=str) + '\n')
    print(json.dumps(dec, default=str))


if __name__ == '__main__':
    main()
