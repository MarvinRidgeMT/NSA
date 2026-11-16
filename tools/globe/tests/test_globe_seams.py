"""Seam QA: fails when a product pair's height jump in the seam band exceeds the documented tolerance
(tools/globe/seams.py TOLERANCES, plan §7)."""
import json
import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from globe_fixtures import SP, grid_centres, plane, write_raster  # noqa: E402

from tools.globe import pyramid_products as PP  # noqa: E402
from tools.globe import seams  # noqa: E402

REPO = Path(__file__).resolve().parents[3]


def _pair(tmp_path, offset):
    cl, ct, cpx, cn = -20000.0, 20000.0, 80.0, 500
    Xc, Yc = grid_centres(cl, ct, cpx, cn, cn)
    fc = write_raster(tmp_path / f'c{offset}.tif', plane(Xc, Yc), cl, ct, cpx, SP)
    fl, ft, fpx, fn = 1000.0, 9000.0, 5.0, 1600
    Xf, Yf = grid_centres(fl, ft, fpx, fn, fn)
    ff = write_raster(tmp_path / f'f{offset}.tif', plane(Xf, Yf) + offset, fl, ft, fpx, SP)
    return PP.ProductSpec(f'fine{offset}', 3, ff, 5.0), PP.ProductSpec(f'coarse{offset}', 5, fc, 80.0)


def test_consistent_pair_passes(tmp_path):
    hi, lo = _pair(tmp_path, 0.0)
    st = seams.pair_seam(hi, lo, 'sp')
    assert st is not None and st['judged'] and st['n'] > 100
    assert st['p99_abs_m'] < 0.01 and st['pass']
    assert st['level'] == 4                              # compared at the coarser (80 m) posting


def test_offset_pair_fails(tmp_path):
    hi, lo = _pair(tmp_path, 50.0)
    st = seams.pair_seam(hi, lo, 'sp')
    assert st['median_signed_m'] == pytest.approx(50.0, abs=0.01)
    assert not st['pass']                                # 50 m >> lola/lola tolerance (2 m median, 20 m p99)


def test_intermediate_product_excludes_band(tmp_path):
    hi, lo = _pair(tmp_path, 0.0)
    mid = PP.ProductSpec('mid', 4, lo.path, 80.0)       # covers the whole band
    assert seams.pair_seam(hi, lo, 'sp', between=[mid]) is None


def test_tolerance_table_is_documented():
    for k, v in seams.TOLERANCES.items():
        assert set(v) == {'median_abs_m', 'p99_abs_m'} and v['median_abs_m'] < v['p99_abs_m']
    assert seams.tolerance(3, 5)[0] == ('lola', 'lola') and seams.tolerance(6, 8)[0] == ('lola', 'sldem')


def _real_pairs():
    specs = {s.product_id: s for s in PP.local_products()}
    p90 = specs.get('pgda90_ldem_80s_80m')
    sites = [s for s in specs.values() if s.source_id == 3]
    return p90, sites


@pytest.mark.skipif(_real_pairs()[0] is None, reason='PGDA 90 / PGDA 78 not on disk')
def test_real_pgda78_over_pgda90_within_tolerance():
    p90, sites = _real_pairs()
    order = sorted(sites, key=lambda s: s.priority)
    judged = 0
    for i, s in enumerate(order):
        st = seams.pair_seam(s, p90, 'sp', between=order[i + 1:])
        if st is None:
            continue
        judged += st['judged']
        assert st['pass'], st
    assert judged >= 1


QA = REPO / 'docs' / 'v2' / 'PYRAMID_QA.json'


@pytest.mark.skipif(not QA.exists(), reason='seam QA not run yet')
def test_committed_seam_qa_passes():
    doc = json.loads(QA.read_text())
    sec = doc.get('seams')
    if sec is None:
        pytest.skip('no seams section')
    bad = [(p['hi'], p['lo'], p['zone'], p['median_abs_m'], p['p99_abs_m']) for p in sec['pairs'] + sec['zone_seams']
           if not p['pass']]
    assert not bad, bad
