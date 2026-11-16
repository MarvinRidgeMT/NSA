"""Tests for the science-limits results (data/science_limits/*). Each test can fail: it re-derives a
number from a committed bundle, checks an ordering that must hold, or a convergence threshold."""
import json
import math
from pathlib import Path

import numpy as np
import pytest

from science import crossings as X

ROOT = Path(__file__).resolve().parents[2]
SL = ROOT / 'data' / 'science_limits'
B04 = ROOT / 'data' / 'bundles' / 'site04_roi3_2026-11-14_14d_mast1m.json'


def _res(item):
    p = SL / item / 'result.json'
    if not p.exists():
        pytest.skip(f'{item} not generated')
    return json.loads(p.read_text())


def _manifest_ok(item):
    m = json.loads((SL / item / 'manifest.json').read_text())
    assert m['label'] == 'PILOT · SOURCE-BASED · UNVALIDATED'
    assert (SL / item / 'README.md').exists()
    for i in m['inputs']:
        p = ROOT / i['path']
        if p.is_file() and len(i.get('sha256', '')) == 64:
            from science.limits.common import sha256_file
            assert sha256_file(p) == i['sha256'], f'{i["path"]} changed since {item} was generated'


# ------------------------------------------------------------------ L1
def test_l1_centre_reproduces_bundle():
    r = _res('L1_disc_visibility'); _manifest_ok('L1_disc_visibility')
    s = r['sites']['site04_roi3']
    assert s['nominal']['centre']['sun_pct'] == pytest.approx(94.362, abs=1e-3)
    assert s['nominal']['centre']['sun_and_earth_pct'] == pytest.approx(72.107, abs=1e-3)
    assert s['clone_range']['centre']['sun_pct'] == pytest.approx([87.537, 97.329], abs=1e-3)
    assert sorted(s['reproduction']['bundle_clone_sun_pct'])[0] == pytest.approx(87.537, abs=1e-3)


def test_l1_variant_ordering():
    r = _res('L1_disc_visibility')
    for site, s in r['sites'].items():
        for blk in [s['nominal']] + list(s['clones'].values()):
            assert blk['any']['sun_pct'] >= blk['centre']['sun_pct'] >= blk['full']['sun_pct']
            assert blk['any']['longest_sun_gap_h_hourly'] <= blk['centre']['longest_sun_gap_h_hourly'] <= blk['full']['longest_sun_gap_h_hourly']


def test_disc_fraction_half_at_centre_rule():
    # disc fraction >= 0.5 is identical to the centre rule for a straight horizon
    for r in (0.267, 0.95):
        for s in (0.0, 0.3):
            assert X.disk_fraction_visible(0.0, r, s) == pytest.approx(0.5)
            assert X.disk_fraction_visible(1e-6, r, s) > 0.5 > X.disk_fraction_visible(-1e-6, r, s)
    assert X.disk_fraction_visible(0.27, 0.267) == 1.0 and X.disk_fraction_visible(-0.27, 0.267) == 0.0


def test_l1_nac_offset_shrinks_only_for_full_disc():
    r = _res('L1_disc_visibility')
    for a in r['nac_v2_rescore'].values():
        assert a['offset_disc_fraction_ge_0p5_deg'] == a['crossing_centre_margin_deg']
        assert abs(a['offset_full_disc_rule_deg'][1]) < abs(a['crossing_centre_margin_deg'])
