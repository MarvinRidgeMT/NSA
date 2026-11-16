"""Phase 9.3 calendar, Decision Card summary rows and the Phase 8 cylinder-shadow geometry."""
import gzip
import json
import math
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


@pytest.mark.parametrize('site', ['site04_roi3', 'site01_roi6'])
def test_calendar_is_a_reindexing_of_k_of_n(site):
    cal = _load(site, 'launch_calendar.json.gz'); cm = _load(site, 'centre_mast_schedule.json.gz')
    k = np.array(cal['metrics']['k_pass']['values']).reshape(10, 3, 365, 24)
    src = np.array(cm['derived']['k_of_N']['metrics']['k_pass']['values']).reshape(3, 10, -1)
    rng = np.random.default_rng(2)
    for _ in range(200):
        m, r, d, h = rng.integers(10), rng.integers(3), rng.integers(365), rng.integers(24)
        assert k[m, r, d, h] == src[r, m, 24 * d + h]
    assert cal['dims'][2]['values'][0] == '2026-11-14' and cal['dims'][2]['values'][-1] == '2027-11-13'


@pytest.mark.parametrize('site', ['site04_roi3', 'site01_roi6'])
def test_summary_rows_match_cubes(site):
    s = _load(site, 'decision_summary.json')
    axes = [r['axis'] for r in s['rows']]
    for a in ('T', 'M', 'D', 'S', 'R', 'link', 'energy', 'safety'):
        assert a in axes
    for r in s['rows']:
        assert r['source'] and r['label'] and 'probability' not in r['answer'].replace('not a probability', '')
    cm = _load(site, 'centre_mast_schedule.json.gz')
    sun0 = cm['metrics']['sun_pct']['values'][0] * 100 / 337
    t = next(r for r in s['rows'] if r['axis'] == 'T')
    assert t['value'].startswith(f'{sun0:.2f} %')
    if site == 'site04_roi3':
        assert '87.54–97.33' in t['value']


def test_body_horizon_synthetic_cylinder():
    """A 4 m tall, 2 m radius cylinder 5 m due grid-north of a 2 m antenna blocks a sector of half-width
    asin(2/5) up to atan((4-2)/(5-2)), and nothing elsewhere."""
    from science import frames
    from science.cube import build_assets as A
    from science.cube import compute as C
    site = 'site04_roi3'
    sky = {'bins': 720, 'elevation_deg': [-1.0] * 720}
    body = {'name': 'b', 'xy': (0.0, 5.0), 'r': 2.0, 'top': 4.0}
    out = A.body_horizon(sky, site, (0, 0), 2.0, 100.0, [body], lambda p: 100.0)
    el = np.array(out['elevation_deg'])
    lon = C.sites.SITES[site]['lon']
    brg = float(frames.grid_az_to_local_az(0.0, lon)) % 360
    az = np.arange(720) * 0.5
    d = np.abs((az - brg + 180) % 360 - 180)
    half = math.degrees(math.asin(2 / 5)); top = math.degrees(math.atan2(2.0, 3.0))
    assert np.allclose(el[d <= half - 0.5], top) and np.allclose(el[d > half + 0.5], -1.0)
    # an asset standing on the body is not blocked by it
    same = A.body_horizon(sky, site, (0, 5), 4.5, 100.0, [body], lambda p: 100.0)
    assert same['elevation_deg'] == sky['elevation_deg']
