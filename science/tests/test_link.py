"""Phase 4 — link targets (DSN + LCRNS relays). Tests that can fail: monotonicity (a relay never reduces
availability, a bigger margin never increases it), the DSN gate, the paper's two tables agreeing through our frame,
and the site frame against Horizons' own LRO az/el (independent spacecraft) within 0.05 deg."""
import gzip
import json
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[2]
CUBES = ROOT / 'data' / 'cubes'
B04 = ROOT / 'data' / 'bundles' / 'site04_roi3_2026-11-14_14d_mast1m.json'


def _cube(site):
    p = CUBES / site / 'link.json.gz'
    if not p.exists():
        pytest.skip('link cube not built')
    return json.loads(gzip.decompress(p.read_bytes()))


def _arr(c, metric, derived=None):
    if derived:
        d = c['derived'][derived]
        dims = [x if isinstance(x, dict) else next(y for y in c['dims'] if y['name'] == x) for x in d['dims']]
        return np.array(d['metrics'][metric]['values'], float).reshape([len(x['values']) for x in dims])
    return np.array(c['metrics'][metric]['values'], float).reshape([len(x['values']) for x in c['dims']])


def _site_eph():
    from science.cube import ephem_year as E
    if not (E.RAW / 'site04_roi3_year.npz').exists():
        pytest.skip('ephemeris cache not present')
    b = json.loads(B04.read_text())
    loc = (b['site']['lat_deg'], b['site']['lon_deg_east'], b['site']['height_m'])
    return loc, E.load('site04_roi3', *loc)


@pytest.mark.parametrize('site', ['site04_roi3', 'site01_roi6'])
def test_adding_a_relay_never_reduces_availability(site):
    from science.cube.build_link import TARGETS
    c = _cube(site)
    for a in (_arr(c, 'available_pct'), _arr(c, 'available_pct', 'year_summary')):
        i = {k: TARGETS.index(k) for k in TARGETS}
        tk = lambda k: a[:, :, i[k]]
        assert np.all(tk('dte_plus_1_relay') >= tk('earth_dsn'))
        assert np.all(tk('dte_plus_2_relays') >= tk('dte_plus_1_relay'))
        assert np.all(tk('dte_or_relay') >= tk('dte_plus_2_relays'))
        assert np.all(tk('relay_any') >= np.maximum(tk('relay_1'), tk('relay_2')))
        assert np.all(tk('earth_centre') >= tk('earth_dsn'))
        assert np.all(tk('earth_any_limb') >= tk('earth_centre'))
        # a larger elevation margin can only remove hours (link targets)
        for k in TARGETS[1:]:
            assert np.all(np.diff(tk(k), axis=2) <= 1e-9), k
    gaps = _arr(c, 'longest_gap_h')
    k = TARGETS.index
    assert np.all(gaps[:, :, k('dte_plus_2_relays')] <= gaps[:, :, k('earth_dsn')])


def test_moon_below_station_mask_means_no_dsn_link():
    from science.cube import build_link as BL
    from science.cube import compute as C
    from science.cube import link_dsn as DSN
    loc, eph = _site_eph()
    sky = C.skyline('site04_roi3', 'nominal', 1.0)
    dsn, t, _ = DSN.complexes()
    geo, _, _ = BL.geometry('site04_roi3', eph)
    tg, relay = BL.hourly_targets(eph, sky, geo['full'], dsn['any'], 0.0, 0, (0, 1))
    off = ~dsn['any']
    assert off.sum() > 0, 'expected some hours with the Moon below 10 deg at all complexes'
    for k in ('earth_dsn', 'relay_1', 'relay_2', 'relay_any', 'dte_or_relay', 'dte_plus_1_relay', 'dte_plus_2_relays'):
        assert not tg[k][off].any(), k
    # synthetic: DSN never available -> no link at all, Earth geometry unchanged
    none = np.zeros_like(dsn['any'])
    tg0, _ = BL.hourly_targets(eph, sky, geo['full'], none, 0.0, 0, (0, 1))
    assert not tg0['dte_or_relay'].any() and np.array_equal(tg0['earth_centre'], tg['earth_centre'])
    # station mask: each Horizons series really is the Moon elevation from that station
    for st in ('DSS-14', 'DSS-63', 'DSS-43'):
        _, el, p = DSN.station_series(st)
        assert st in p['horizons_site_name'] and -90 <= el.min() and el.max() <= 90


def test_site_frame_against_horizons_lro_within_0p05deg():
    """Independent check: Horizons az/el of LRO at the site vs our frame applied to the Horizons LRO vector."""
    from science.cube import link_relay as LR
    loc, eph = _site_eph()
    for tag in ('site04_roi3_lro_azel_val', 'lro_vec_moon_val'):
        if not (LR.RAW / f'{tag}.txt').exists():
            pytest.skip('LRO validation responses not cached')
    R, _ = LR.site_frame('site04_roi3', loc, eph)
    st, sp = '2026-11-14 00:00', '2026-11-16 00:00'
    t1, az, el, _ = LR.azel('-85', loc, st, sp, '1 h', tag='site04_roi3_lro_azel_val')
    t2, v, _ = LR.vectors('-85', '500@301', corr='NONE', start=st, stop=sp, tag='lro_vec_moon_val')
    n = t1.size
    assert np.array_equal(t1, t2) and np.array_equal(t1, eph['t'][:n])
    r_site = (LR.R_MOON_KM + loc[2] / 1000) * R[:n, 2, :]
    a2, e2, rng = LR.relay_azel(R[:n], r_site, v[:, :3])
    ang = np.degrees(np.arccos(np.clip(np.einsum('ti,ti->t', LR.enu_from_azel(a2, e2), LR.enu_from_azel(az, el)), -1, 1)))
    assert ang.max() < 0.05 and rng.min() > 200


def test_frame_leave_one_out():
    from science.cube import link_relay as LR
    loc, eph = _site_eph()
    sub = {k: v for k, v in LR.FIT_BODIES.items() if k != 'jupiter'}
    R, _ = LR.site_frame('site04_roi3', loc, eph, sub)
    t, az, el, _ = LR.azel('599', loc, tag='site04_roi3_jupiter_azel_year_20261114')
    _, v, _ = LR.vectors('599', None, site=loc, corr='LT+S', tag='site04_roi3_jupiter_topovec_year_20261114')
    a2, e2 = LR.azel_from_enu(np.einsum('tij,tj->ti', R, v[:, :3]))
    ang = np.degrees(np.arccos(np.clip(np.einsum('ti,ti->t', LR.enu_from_azel(a2, e2), LR.enu_from_azel(az, el)), -1, 1)))
    assert ang.max() < 0.01


def test_paper_tables_agree_through_j2000_frame():
    """Table 2 (ICRF Cartesian) mapped with our Horizons-fitted Moon frame at J2000 reproduces Table 1 (PA Keplerian)."""
    from science import frames
    from science.cube import link_relay as LR
    loc, _ = _site_eph()
    tags = [f'j2000_{n}_{k}' for n in LR.FIT_BODIES for k in ('azel', 'topovec')]
    if not all((LR.RAW / f'{t}.txt').exists() for t in tags):
        pytest.skip('J2000 frame responses not cached')
    B, Rv = [], []
    for name, code in LR.FIT_BODIES.items():
        _, az, el, _ = LR.azel(code, loc, '2000-01-01 11:58', '2000-01-01 12:00', '1 m', tag=f'j2000_{name}_azel')
        _, v, _ = LR.vectors(code, None, site=loc, corr='LT+S', start='2000-01-01 11:58', stop='2000-01-01 12:00', step='1 m', tag=f'j2000_{name}_topovec')
        B.append(LR.enu_from_azel(az[1:2], el[1:2])); Rv.append(v[1:2, :3] / np.linalg.norm(v[1:2, :3]))
    R = LR.wahba(np.array(B), np.array(Rv))[0]
    e, n, u = frames.enu_basis(loc[0], loc[1])
    ME = np.array([e, n, u]).T @ R
    for sv, s in LR.PAPER['states'].items():
        k = LR.kepler(np.r_[ME @ np.array(s[:3]), ME @ np.array(s[3:])]); p = LR.PAPER['kepler_pa'][sv]
        assert k['sma'] == pytest.approx(p[0], abs=0.05) and k['ecc'] == pytest.approx(p[1], abs=1e-5)
        for got, want in ((k['inc'], p[2]), (k['raan'], p[3]), (k['aop'], p[4])):
            assert abs((got - want + 180) % 360 - 180) < 0.05, (sv, got, want)   # ME vs PA ~0.02 deg


def test_relay_az_el_round_trip_and_occultation():
    from science.cube import link_relay as LR
    rng = np.random.default_rng(4)
    az = rng.uniform(0, 360, 200); el = rng.uniform(-80, 80, 200)
    a2, e2 = LR.azel_from_enu(LR.enu_from_azel(az, el))
    assert np.allclose((a2 - az + 180) % 360 - 180, 0, atol=1e-9) and np.allclose(e2, el, atol=1e-9)
    p_from = np.array([[0, 0, 5000.0], [0, 0, 5000.0]]); p_to = np.array([[0, 0, -400000.0], [400000.0, 0, 5000.0]])
    assert LR.occulted_by_moon(p_from, p_to).tolist() == [True, False]


def test_nasa_sanity_ranges_recorded():
    """Two relays reach 100 % line of sight (as NASA); DTE at a 2-5 deg margin falls inside NASA's 17-43 %."""
    for site in ('site04_roi3', 'site01_roi6'):
        a = _arr(_cube(site), 'year_los_pct', 'nasa_sanity_check')     # R_margin x [dte, +1, +2]
        assert np.all(a[:, 2] == 100.0)
        assert 17 <= a[2, 0] <= 43
        assert np.all(a[:, 1] >= a[:, 0]) and np.all(a[:, 2] >= a[:, 1])
