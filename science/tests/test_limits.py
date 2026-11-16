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


# ------------------------------------------------------------------ L2
def test_l2_spline_matches_horizons_bisection():
    r = _res('L2_event_timing'); _manifest_ok('L2_event_timing')
    for s in r['sites'].values():
        assert s['validation_vs_horizons_bisection']
        assert max(abs(e['diff_s']) for e in s['validation_vs_horizons_bisection']) < 60.0


def test_l2_nominal_reproduces_bundle_continuous():
    r = _res('L2_event_timing')['sites']['site04_roi3']
    assert r['maps']['nominal']['centre']['sun_pct'] == pytest.approx(r['bundle_reference']['sun_center_visible_pct'], abs=0.01)
    assert r['maps']['nominal']['centre']['longest_sun_gap_h'] == pytest.approx(r['bundle_reference']['longest_sun_center_hidden_h'], abs=0.01)


def test_l2_refined_transitions_inside_hourly_bracket():
    r = _res('L2_event_timing')
    for s in r['sites'].values():
        for m in s['maps'].values():
            for v in m.values():
                for k in ('sun_bracket_check', 'earth_bracket_check'):
                    c = v[k]
                    assert c['n_inside_bracket'] == c['n_events'] - c['n_subhour_blinks']
                    # every hourly sign change is matched by one refined event inside it
                    assert c['n_inside_bracket'] >= c['n_hourly_sign_changes']


def test_l2_no_extrapolation():
    from science.limits.l2_timing import Ephem
    from science.limits.common import load_bundle
    e = Ephem(load_bundle('site04_roi3'), 'sun')
    with pytest.raises(ValueError):
        e(e.t1 + 60)


# ------------------------------------------------------------------ L7
def test_l7_uniform_shift_monotone_and_critical_delta():
    r = _res('L7_knife_edge'); _manifest_ok('L7_knife_edge')
    for site, s in r['sites'].items():
        u = s['uniform_horizon_error']
        seq = [u[k]['sun_pct'] for k in ('-0.50', '-0.25', '-0.10', '-0.05')] + [u['nominal']['sun_pct']] + \
              [u[k]['sun_pct'] for k in ('+0.05', '+0.10', '+0.25', '+0.50')]
        assert all(a >= b - 1e-9 for a, b in zip(seq, seq[1:])), site
        d = s['critical_uniform_raise_deg']['sun_70pct']
        assert d is not None and d > 0.5          # the 70 % verdict does not flip within +-0.5 deg
    w = r['sites']['site04_roi3']['margin_distribution']['within_nominal']
    assert w['0.1'] <= w['0.25'] <= w['0.5'] <= w['1.0'] and 25 <= w['0.5'] <= 40


def test_l7_jacobian_matches_small_angle():
    c = _res('L7_knife_edge')['sites']['site04_roi3']['controlling_cell']
    assert c['dE_dh_deg_per_m'] == pytest.approx(math.degrees(1.0 / c['distance_m']), rel=0.05)


# ------------------------------------------------------------------ L8 calibration
def test_l8_calibration_reproduces_rq2_and_varies_by_site():
    r = _res('L8_calibration'); _manifest_ok('L8_calibration')
    s = r['sites']
    assert s['Site04_ROI3']['year']['B_toterr_rho_emp']['over_prediction_exp_over_obs'] == pytest.approx(10240.7 / 7261, abs=1e-3)
    over = [s[k]['year']['B_toterr_rho_emp']['over_prediction_exp_over_obs'] for k in ('Site04_ROI3', 'Site01_ROI6')]
    under = [s[k]['year']['B_toterr_rho_emp']['over_prediction_exp_over_obs'] for k in ('Site07_ROI1', 'Site11_ROI4')]
    assert min(over) > 1.2 and max(under) < 0.8   # no single calibration factor


# ------------------------------------------------------------------ L3 analytic
def test_l3_far_bound_geometry_and_result():
    from science.limits.l3_far_bound import e_of, h_needed, R
    r0 = R + 1738.5
    for d in (280e3, 600e3):
        for e in (-3.0, -1.0):
            assert e_of(r0, d, h_needed(r0, d, e)) == pytest.approx(e, abs=1e-9)
    r = _res('L3_far_bound'); _manifest_ok('L3_far_bound')
    for s in r['sites'].values():
        for body in ('sun', 'earth'):
            assert s[body]['hours_affected_by_bound'] == 0 and s[body]['min_per_hour_slack_deg'] > 0


# ------------------------------------------------------------------ L6
def test_l6_protocols_frozen_and_point_unchecked():
    from science.limits.common import sha256_file
    h = ROOT / 'tools' / 'validation' / 'hero'
    for doc in ('HERO_PROTOCOL', 'HERO_PROTOCOL_A1'):
        assert sha256_file(h / f'{doc}.md') == (h / f'{doc}.sha256').read_text().split()[0], f'{doc} changed since freeze'
    r = _res('L6_hero_observation'); _manifest_ok('L6_hero_observation')
    assert r['gsfc_sfs_regions']['regions_containing_p0'] == []
    assert 'UNCHECKED' in r['status']
