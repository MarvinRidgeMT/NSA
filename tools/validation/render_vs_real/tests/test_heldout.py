"""Amendment A5: the held-out run's frozen analysis (claim rule, near-total-shadow stratum) and its split wall."""
import json
import math
import os
import subprocess
import sys

from tools.validation.render_vs_real import common, heldout as H


def rec(pid, site, product, iou, edge, gsd=5.0, pred=0.5, orbit='grgm900c'):
    return {'product_id': pid, 'site': site, 'product': product, 'photometry': 'hapke', 'registered': True, 'orbit': orbit,
            'status': 'scored', 'iouShadow': iou, 'edgeMedianM': edge, 'gsdMedianM': gsd, 'predShadowFrac': pred}


def test_claim_rule_passes_and_names_each_failed_condition():
    good = [rec(f'M{i}', 's1', 'pgda78_5m', 0.9, 6.0) for i in range(10)]
    flat = [rec(f'M{i}', 's1', 'flat', 0.0, float('nan')) for i in range(10)]
    nat = {(f'M{i}', 's1'): 1.0 for i in range(10)}
    out = H.claim_rule(good + flat, nat)['s1']
    assert out['claim'] and out['failed'] == [] and out['fracBeatsControlEdge'] == 1.0
    assert out['edgeLimitM'] == 10.0 and out['edgeWithinNative2px'] is False      # 6 m > 2 x 1 m native: reported, not the rule
    low = [rec(f'M{i}', 's1', 'pgda78_5m', 0.7, 12.0) for i in range(10)]
    out = H.claim_rule(low + flat, nat)['s1']
    assert not out['claim'] and out['failed'] == ['iou', 'edge']


def test_claim_rule_control_wins_and_undefined_edges():
    P = [rec(f'M{i}', 's1', 'pgda78_5m', 0.9, 4.0 if i < 7 else float('nan')) for i in range(10)]
    F = [rec(f'M{i}', 's1', 'flat', 0.1, 50.0 if i >= 7 else float('nan')) for i in range(10)]
    out = H.claim_rule(P + F, {})['s1']
    assert math.isclose(out['fracBeatsControlEdge'], 0.7) and out['failed'] == ['beatsControl']
    # FDF-orbit rows and other photometry never enter the claim
    extra = [rec('X', 's1', 'pgda78_5m', 0.0, 900.0, orbit='fdf')]
    assert H.claim_rule(P + F + extra, {})['s1']['n'] == 10
    assert H.claim_rule([], {}, sites=['s9'])['s9'] == {'n': 0, 'claim': False, 'failed': ['no scored rows']}


def test_near_total_shadow_stratum():
    rs = [rec('A', 's', 'pgda78_5m', 0.5, 1, pred=0.98), rec('B', 's', 'pgda78_5m', 0.5, 1, pred=0.979),
          rec('C', 's', 'flat', 0.5, 1, pred=1.0)]
    assert H.near_total_shadow(rs) == {('A', 's')}


def test_dev_mode_paths_are_unchanged():
    assert common.SPLIT == 'dev'
    assert common.RESULTS.name == 'results' and common.GEOM_DIR == common.WORK / 'geometry'
    assert common.RENDER_DIR == common.WORK / 'renders'


def test_heldout_mode_wall():
    """In a child with POLARIS_RVR_SPLIT=heldout: paths move, a dev id is refused, a held-out NAC id passes (only because
    A5 and the frozen code are registered and unchanged), a held-out id of another instrument is refused."""
    rows = common.read_catalogue()
    dev = next(r['product_id'] for r in rows if r['split'] == 'dev' and r['instrument'] == 'LROC_NAC')
    held = next(r['product_id'] for r in rows if r['split'] == 'heldout' and r['instrument'] == 'LROC_NAC')
    other = next(r['product_id'] for r in rows if r['split'] == 'heldout' and r['instrument'] != 'LROC_NAC')
    code = f'''
import json
from tools.validation.render_vs_real import common as C
out = {{'results': C.RESULTS.name, 'geom': str(C.GEOM_DIR.relative_to(C.WORK)), 'renders': str(C.RENDER_DIR.relative_to(C.WORK))}}
for k, i in (('dev', {dev!r}), ('held', {held!r}), ('other', {other!r})):
    try:
        C.assert_dev([i]); out[k] = 'pass'
    except C.HeldOutError:
        out[k] = 'refused'
print(json.dumps(out))
'''
    r = subprocess.run([sys.executable, '-c', code], env={**os.environ, 'POLARIS_RVR_SPLIT': 'heldout'}, cwd=common.ROOT,
                       capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    out = json.loads(r.stdout.strip().splitlines()[-1])
    assert out == {'results': 'results_heldout', 'geom': 'heldout/geometry', 'renders': 'heldout/renders',
                   'dev': 'refused', 'held': 'pass', 'other': 'refused'}


def test_frozen_code_is_registered():
    reg = {p for p, _ in common.preregistered()}
    assert common.HELDOUT_AMENDMENT in reg
    assert set(H.FROZEN_CODE) <= reg
