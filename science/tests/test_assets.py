"""Phases 8, 9.1, 9.2 — multi-asset layout, footprint, per-asset heights. Tests that can fail: the antenna behind
the lander loses Earth (reproduces the research 'far side sees Earth 0 %'); the single-point layout equals the
single-point cubes; a zero-size footprint is the point result; taller assets never see less Sun."""
import gzip
import json
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[2]
CUBES = ROOT / 'data' / 'cubes'


def _load(site, name):
    p = CUBES / site / name
    if not p.exists():
        pytest.skip(f'{p} not built')
    raw = p.read_bytes()
    return json.loads(gzip.decompress(raw) if raw[:2] == b'\x1f\x8b' else raw)


def _arr(c, k):
    return np.array(c['metrics'][k]['values'], float).reshape([len(d['values']) for d in c['dims']])


@pytest.mark.parametrize('site', ['site04_roi3', 'site01_roi6'])
def test_antenna_behind_lander_loses_earth(site):
    c = _load(site, 'asset_layout.json')
    L = c['dims'][1]['values']
    link = _arr(c, 'link_pct')
    assert np.all(link[:, L.index('bad')] == 0.0)
    assert np.all(link[:, L.index('research')] > 40)


@pytest.mark.parametrize('site', ['site04_roi3', 'site01_roi6'])
def test_single_layout_equals_single_point_cubes(site):
    lay = _load(site, 'asset_layout.json'); cm = _load(site, 'centre_mast_schedule.json.gz'); ln = _load(site, 'link.json.gz')
    L = lay['dims'][1]['values']
    power = _arr(lay, 'power_pct'); link = _arr(lay, 'link_pct')
    sun_demo = np.array(cm['metrics']['sun_pct']['values']).reshape(21, 10, -1)[:, 0, 0] * 100 / 337
    assert np.allclose(power[:, L.index('single'), 0], sun_demo, atol=1e-3)
    y = ln['derived']['year_summary']
    ys = np.array(y['metrics']['available_pct']['values']).reshape(21, 10, 10, 3)
    tg = ln['dims'][2]['values']
    assert np.allclose(link[:, L.index('single'), 1], ys[:, 0, tg.index('earth_dsn'), 0], atol=1e-3)


@pytest.mark.parametrize('site', ['site04_roi3', 'site01_roi6'])
def test_footprint_centre_is_point_result_and_range_brackets(site):
    f = _load(site, 'footprint.json'); cm = _load(site, 'centre_mast_schedule.json.gz')
    sun = _arr(f, 'sun_pct')
    sun_demo = np.array(cm['metrics']['sun_pct']['values']).reshape(21, 10, -1)[:, 0, 0] * 100 / 337
    assert np.allclose(sun[:, 0, 0], sun_demo, atol=1e-3)                     # D_pad 'centre' = point
    d = f['derived']['pad_range']['metrics']
    worst = np.array(d['sun_worst_pct']['values']).reshape(21, 2); best = np.array(d['sun_best_pct']['values']).reshape(21, 2)
    assert np.all(worst <= sun[:, 0] + 1e-9) and np.all(best >= sun[:, 0] - 1e-9)


def test_footprint_to_zero_reproduces_point():
    from science.cube import build_assets as A
    from science.cube import ephem_year as E
    if not (E.RAW / 'site04_roi3_year.npz').exists():
        pytest.skip('ephemeris cache not present')
    b = json.loads((ROOT / 'data' / 'bundles' / 'site04_roi3_2026-11-14_14d_mast1m.json').read_text())
    eph = E.load('site04_roi3', b['site']['lat_deg'], b['site']['lon_deg_east'], b['site']['height_m'])
    s0, e0 = A.flags('site04_roi3', eph, 'clone05', (0, 0), 1.0, [])
    s1, e1 = A.flags('site04_roi3', eph, 'clone05', (0.0, 0.0), 1.0, [])
    assert np.array_equal(s0, s1) and np.array_equal(e0, e1)


@pytest.mark.parametrize('site', ['site04_roi3', 'site01_roi6'])
def test_taller_asset_never_sees_less_sun(site):
    h = _load(site, 'asset_heights.json')
    sun = _arr(h, 'sun_pct')
    assert np.all(np.diff(sun, axis=1) >= -1e-9)
    cm = _load(site, 'centre_mast_schedule.json.gz')
    sun_demo2 = np.array(cm['metrics']['sun_pct']['values']).reshape(21, 10, -1)[:, 1, 0] * 100 / 337   # 2 m mast
    assert np.allclose(sun[:, h['dims'][1]['values'].index(2.0), 0], sun_demo2, atol=1e-3)
