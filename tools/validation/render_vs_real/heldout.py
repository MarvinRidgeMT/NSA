"""The pre-registered held-out run for LROC NAC (protocol §6, Amendment A5). Run once; resumable after a crash.

    python -m tools.validation.render_vs_real.heldout verify        # registration check only (no download)
    python -m tools.validation.render_vs_real.heldout all [--workers 4 --threads 4]

`all` = select (every held-out LROC NAC row of the frozen catalogue; metadata gates from §2) → SPICE kernels → geometry →
fetch + render + score, with exactly the dev pipeline (A1–A4) and the frozen parameters in A5. It refuses to start unless
every file registered in docs/v2/PREREGISTRATION.md matches its SHA-256 and A5 plus all of FROZEN_CODE are registered.
Stages run in a child process with POLARIS_RVR_SPLIT=heldout (common.py): outputs go to results_heldout/ and
$POLARIS_DATA/v2/render_vs_real/heldout/; the dev outputs are never touched.

`claim_rule` and `near_total_shadow` are the frozen analysis of A5.6 / A5.5; report_heldout.py only formats them.
"""
from __future__ import annotations

import argparse
import collections
import datetime as dt
import json
import math
import os
import subprocess
import sys

import numpy as np

from . import common as C

FROZEN_CODE = [f'tools/validation/render_vs_real/{m}.py' for m in
               ('common', 'fetch', 'geometry', 'nac_camera', 'realimage', 'score', 'run', 'blender_twin', 'terrain_products',
                'spice_kernels', 'heldout')] + \
              ['blender/v2/hapke.py', 'blender/v2/hapke_nodes.py', 'blender/v2/terrain.py', 'tools/imagery/sites.py']
HEADLINE_PRODUCT = 'pgda78_5m'
CONTROL = 'flat'
NEAR_TOTAL_SHADOW = 0.98          # A5.5: registered predicted shadow fraction (PGDA 78) at or above which a row is in the stratum
CLAIM_IOU, CLAIM_EDGE_PX, CLAIM_BEAT = 0.80, 2.0, 0.80     # protocol §8


def verify():
    C.check_frozen()
    C.verify_heldout_registration(FROZEN_CODE)


# ------------------------------------------------------------------------------------------------ selection (A5.2)
def select():
    rows = C.read_catalogue()
    held = [r for r in rows if r['split'] == 'heldout' and r['instrument'] == C.HELDOUT_INSTRUMENT]
    gated, by_img = [], collections.defaultdict(list)
    for r in held:
        ok, why = C.eligible_by_metadata(r)
        if ok:
            by_img[r['product_id']].append(r)
        else:
            gated.append({'product_id': r['product_id'], 'site': r['site'], 'reason': why})
    C.assert_dev(list(by_img), rows)
    images = []
    for pid in sorted(by_img):
        rs = sorted(by_img[pid], key=lambda r: -float(r['overlap_frac']))
        images.append({'product_id': pid, 'sites': [r['site'] for r in rs], 'obs_utc': rs[0]['obs_utc'],
                       'utc_start': rs[0]['utc_start'], 'utc_stop': rs[0]['utc_stop'],
                       'pixel_scale_m': float(rs[0]['pixel_scale_m']), 'data_file_url': rs[0]['data_file_url'],
                       'label_url': rs[0]['label_url'], 'strata': {r['site']: r['stratum'] for r in rs}})
    sel = {'rule': 'A5.2: every held-out LROC NAC row of the frozen catalogue; protocol §2 metadata gates; no sampling',
           'catalogueSha256': C.CATALOGUE_SHA256, 'heldoutRows': len(held), 'eligibleRows': sum(len(i['sites']) for i in images),
           'eligibleImages': len(images), 'nImages': len(images), 'nRows': sum(len(i['sites']) for i in images),
           'gatedByMetadata': gated, 'ckWindowsChosen': [], 'images': images}
    C.write_json(C.RESULTS / 'selection.json', sel)
    print(f"held-out NAC rows {len(held)}: eligible {sel['nRows']} rows / {sel['nImages']} images, gated by metadata {len(gated)}",
          flush=True)
    return sel


# ------------------------------------------------------------------------------------------------ frozen analysis
def _fin(x):
    return isinstance(x, (int, float)) and x is not None and math.isfinite(x)


def _med(v):
    v = [x for x in v if _fin(x)]
    return float(np.median(v)) if v else float('nan')


def headline_records(scores, product=HEADLINE_PRODUCT, phot='hapke', registered=True, orbit='grgm900c'):
    return [r for r in scores if r.get('status') == 'scored' and r.get('product') == product and r.get('photometry') == phot
            and r.get('registered') == registered and r.get('orbit') == orbit]


def claim_rule(scores, native_px_m, sites=None, product=HEADLINE_PRODUCT):
    """Protocol §8 per site for one terrain product (A5.6): registered, Hapke, GRGM900C-orbit rows.
    native_px_m: {(product_id, site): native ODE pixel scale m}. Edge errors that are undefined (no matched edge) count as
    worse than any finite error; a pair where both are undefined is not a win."""
    P = {(r['product_id'], r['site']): r for r in headline_records(scores, product)}
    F = {(r['product_id'], r['site']): r for r in headline_records(scores, CONTROL)}
    out = {}
    for site in sites or sorted({k[1] for k in P}):
        keys = sorted(k for k in P if k[1] == site)
        if not keys:
            out[site] = {'n': 0, 'claim': False, 'failed': ['no scored rows']}
            continue
        iou = _med([P[k]['iouShadow'] for k in keys])
        edge = _med([P[k]['edgeMedianM'] for k in keys])
        n_edge = sum(1 for k in keys if _fin(P[k].get('edgeMedianM')))
        gsd = _med([P[k]['gsdMedianM'] for k in keys])
        nat = _med([native_px_m.get(k) for k in keys])
        pairs = [k for k in keys if k in F]

        def e(r):
            x = r.get('edgeMedianM')
            return x if _fin(x) else math.inf
        beat_iou = [P[k]['iouShadow'] > F[k]['iouShadow'] if _fin(F[k].get('iouShadow')) else _fin(P[k]['iouShadow'])
                    for k in pairs]
        beat_edge = [e(P[k]) < e(F[k]) for k in pairs]
        f_iou = float(np.mean(beat_iou)) if pairs else float('nan')
        f_edge = float(np.mean(beat_edge)) if pairs else float('nan')
        c = {'iou': iou >= CLAIM_IOU, 'edge': edge <= CLAIM_EDGE_PX * gsd,
             'beatsControl': (f_iou >= CLAIM_BEAT) and (f_edge >= CLAIM_BEAT)}
        failed = [k for k, v in c.items() if not v]
        out[site] = {'n': len(keys), 'nEdge': n_edge, 'nPairs': len(pairs), 'medianIouShadow': iou, 'medianEdgeM': edge,
                     'medianAnalysisPxM': gsd, 'edgeLimitM': CLAIM_EDGE_PX * gsd, 'medianNativePxM': nat,
                     'edgeWithinNative2px': bool(edge <= CLAIM_EDGE_PX * nat), 'fracBeatsControlIou': f_iou,
                     'fracBeatsControlEdge': f_edge, 'conditions': c, 'claim': not failed, 'failed': failed}
    return out


def near_total_shadow(scores):
    """A5.5: keys of headline rows whose registered PGDA 78 predicted shadow fraction is >= NEAR_TOTAL_SHADOW."""
    return {(r['product_id'], r['site']) for r in headline_records(scores) if _fin(r.get('predShadowFrac'))
            and r['predShadowFrac'] >= NEAR_TOTAL_SHADOW}


# ------------------------------------------------------------------------------------------------ driver
def _log(event, **kw):
    C.RESULTS.mkdir(parents=True, exist_ok=True)
    rec = {'utc': dt.datetime.now(dt.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'), 'event': event, **kw}
    with open(C.RESULTS / 'RUN_LOG.jsonl', 'a') as f:
        f.write(json.dumps(rec) + '\n')
    print(json.dumps(rec), flush=True)


def _child(a):
    """Runs inside POLARIS_RVR_SPLIT=heldout."""
    assert C.SPLIT == 'heldout'
    verify()
    from science import gitinfo
    _log('start', stages=a.stage, commit=gitinfo.head(), workers=a.workers, threads=a.threads,
         resumed=(C.RESULTS / 'scores.jsonl').exists())
    if a.stage in ('select', 'all'):
        select()
    if a.stage in ('kernels', 'all'):
        from . import spice_kernels
        spice_kernels.main()
    if a.stage in ('geometry', 'all'):
        from . import geometry
        geometry.main([])
    if a.stage in ('run', 'all'):
        from . import run
        run.main(['--workers', str(a.workers), '--threads', str(a.threads)])
    _log('stop', stages=a.stage)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('stage', choices=['verify', 'select', 'kernels', 'geometry', 'run', 'all'])
    ap.add_argument('--workers', type=int, default=4)
    ap.add_argument('--threads', type=int, default=4)
    a = ap.parse_args(argv)
    if C.SPLIT == 'heldout':
        return _child(a)
    verify()
    print('pre-registration verified: protocol, catalogue, amendments A1-A5 and the frozen pipeline code match', flush=True)
    if a.stage == 'verify':
        return
    env = {**os.environ, 'POLARIS_RVR_SPLIT': 'heldout'}
    r = subprocess.run([sys.executable, '-m', 'tools.validation.render_vs_real.heldout', *(argv or sys.argv[1:])], env=env,
                       cwd=C.ROOT, close_fds=False)
    sys.exit(r.returncode)


if __name__ == '__main__':
    main()
