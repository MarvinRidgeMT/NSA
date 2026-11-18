"""A8.4 pipeline test: settle the ShadowCam start-time convention and the TDI-B sample axis on dev rows.

    python -m tools.validation.render_vs_real.shc_pipeline_test

For each pipeline-test row (selection.json pipelineTestImages) and each convention (start isis | label; for TDI B also
flip yes | no): geometry -> render (PGDA 78, Hapke) -> one rigid registration over +- PT_RADIUS_M of the render's Sobel
gradients to the real image's. Writes results_shc/pipeline_test.json with every offset and the A8.4 decision.
Scores from this test are not used for anything else.
"""
from __future__ import annotations

import json
import math
import statistics

import numpy as np

from . import score as S
from . import shc_geometry as SG
from .run import AU, TSI
from .shc_common import SHC_GEOM_DIR, SHC_RESULTS, guard, read_v2
from .shc_run import load_real, render_row, row_context, square_and_gsd

PT_RADIUS_M = 2000.0
ADOPT_BELOW_M, REJECT_ABOVE_M = 150.0, 600.0


def offset(G):
    out = SHC_GEOM_DIR.parent / 'renders' / G['tag']
    real, special, _sat = load_real(G)
    R = dict(np.load(out / 'pgda78_5m.npz'))
    M, P0, Psc = row_context(G)
    in_sq, gsd = square_and_gsd(G, R, M, P0, Psc)
    E = TSI / (G['sunDistM'] / AU) ** 2
    rend = np.where(R['hit'], math.pi * R['beauty'].astype(np.float64) / E, np.nan)
    window = S.analysis_window(in_sq, special) & np.isfinite(real) & np.isfinite(rend)
    if window.sum() < 500:
        return {'status': 'window too small'}
    med = float(np.median(real[window]))
    rn = np.where(np.isfinite(real) & ~special, real / med, 1.0)
    mm = float(np.median(rend[window]))
    mn = np.where(np.isfinite(rend), rend / (mm if mm > 0 else med), 0.0)
    gm = float(np.median(gsd[window]))
    reg = S.register(rn, mn, window, PT_RADIUS_M / gm, refine=0.5, step=0.5)
    from .run import ground_offset
    al, ac = ground_offset(R['pos'].astype(np.float64), reg['dy'], reg['dx'], np.asarray(G['sunEnu']))
    return {'status': 'ok', 'dyPx': reg['dy'], 'dxPx': reg['dx'], 'offsetM': math.hypot(reg['dy'], reg['dx']) * gm,
            'alongSunM': al, 'acrossSunM': ac, 'ncc': reg['ncc'], 'atBound': reg['atBound'], 'binnedPxM': gm}


def main():
    sel = json.loads((SHC_RESULTS / 'selection.json').read_text())
    cat = {(r['product_id'], r['site']): r for r in read_v2()}
    rows = [(im, s) for im in sel['pipelineTestImages'] for s in im['sites']
            if any(p['product_id'] == im['product_id'] and p['site'] == s for p in sel['pipelineTest'])]
    guard([im['product_id'] for im, _ in rows])
    res = []
    for im, site in rows:
        tdi = next(p['tdi'] for p in sel['pipelineTest'] if p['product_id'] == im['product_id'] and p['site'] == site)
        for start in ('isis', 'label'):
            for flip in ((None,) if tdi == 'A' else (False, True)):
                rec = SG.one(im, site, cat[(im['product_id'], site)], start=start, flip_b=flip)
                entry = {'product_id': im['product_id'], 'site': site, 'tdi': tdi, 'start': start, 'flip': flip,
                         'geometry': rec['status'], 'reason': rec.get('reason', '')}
                if rec['status'] == 'ok':
                    gp = SHC_GEOM_DIR / f"{rec['tag']}.json"
                    G = render_row(gp, 16, products=['pgda78_5m'], variants=False)
                    G['tag'] = rec['tag']
                    entry.update(offset(G))
                res.append(entry)
                print(json.dumps(entry), flush=True)

    def med(filt):
        v = [e['offsetM'] for e in res if e.get('status') == 'ok' and filt(e)]
        return (statistics.median(v), len(v)) if v else (float('nan'), 0)
    dec = {}
    a = {k: med(lambda e, k=k: e['start'] == k and e['tdi'] == 'A') for k in ('isis', 'label')}
    best = min(a, key=lambda k: a[k][0] if a[k][1] else math.inf)
    other = 'label' if best == 'isis' else 'isis'
    dec['start'] = {'medians_m': a, 'adopted': best if (a[best][0] < ADOPT_BELOW_M and a[other][0] > REJECT_ABOVE_M) else 'isis',
                    'resolved': bool(a[best][0] < ADOPT_BELOW_M and a[other][0] > REJECT_ABOVE_M)}
    st = dec['start']['adopted']
    b = {f: med(lambda e, f=f: e['tdi'] == 'B' and e['start'] == st and e['flip'] is f) for f in (False, True)}
    if b[False][1] or b[True][1]:
        bf = min(b, key=lambda f: b[f][0] if b[f][1] else math.inf)
        ok = b[bf][0] < ADOPT_BELOW_M and b[not bf][0] > REJECT_ABOVE_M
        dec['tdiB'] = {'medians_m': {str(k): v for k, v in b.items()}, 'flip': bf if ok else None, 'resolved': ok}
    else:
        dec['tdiB'] = {'resolved': False, 'flip': None, 'note': 'no TDI-B pipeline-test row'}
    (SHC_RESULTS / 'pipeline_test.json').write_text(json.dumps({'rule': 'A8.4', 'radiusM': PT_RADIUS_M, 'rows': res,
                                                                 'decision': dec}, indent=1, default=str) + '\n')
    print(json.dumps(dec, default=str))


if __name__ == '__main__':
    main()
