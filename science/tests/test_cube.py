"""Scenario cube (Phase 1). Each test can fail: schema validation, round-trip identity with the committed
bundle, slicing against independent recomputation, robust-output identities, and the solver equivalence.
Tests that need git-ignored caches (NASA rasters, skylines, Horizons) skip when those are absent."""
import gzip
import json
import random
from pathlib import Path

import numpy as np
import pytest

from science import crossings as X

ROOT = Path(__file__).resolve().parents[2]
CUBES = ROOT / 'data' / 'cubes'
SCHEMA = ROOT / 'schemas' / 'scenario-cube-v1.schema.json'
B04 = ROOT / 'data' / 'bundles' / 'site04_roi3_2026-11-14_14d_mast1m.json'


def _cube(site, name):
    p = CUBES / site / name
    if not p.exists():
        pytest.skip(f'{p} not built')
    raw = p.read_bytes()
    return json.loads(gzip.decompress(raw) if raw[:2] == b'\x1f\x8b' else raw)


def _flat(dims, at):
    i = 0
    for d in dims:
        i = i * len(d['values']) + at[d['name']]
    return i


def _val(c, metric, at):
    m = c['metrics'][metric]
    v = m['values'][_flat(c['dims'], at)]
    return None if v is None else v * m.get('scale', 1.0)


def _derived(c, key, metric, at):
    d = c['derived'][key]
    dims = [x if isinstance(x, dict) else next(y for y in c['dims'] if y['name'] == x) for x in d['dims']]
    m = d['metrics'][metric]
    v = m['values'][_flat(dims, at)]
    return v * m.get('scale', 1.0) if isinstance(v, (int, float)) and not isinstance(v, bool) else v


# ------------------------------------------------------------------ schema
@pytest.mark.parametrize('site', ['site04_roi3', 'site01_roi6'])
@pytest.mark.parametrize('name', ['centre_mast_schedule.json.gz', 'position_schedule.json.gz', 'products.json'])
def test_schema_valid(site, name):
    jsonschema = pytest.importorskip('jsonschema')
    c = _cube(site, name)
    jsonschema.validate(c, json.loads(SCHEMA.read_text()))
    n = int(np.prod([len(d['values']) for d in c['dims']]))
    for k, m in c['metrics'].items():
        assert len(m['values']) == n, k
        nulls = {i for i, v in enumerate(m['values']) if v is None}
        assert nulls == set(c['missing']['by_metric'].get(k, [])), f'{k}: nulls and missing mask differ'
    assert c['label'] == 'SOURCE-BASED · UNVALIDATED'
    for i in c['provenance']['inputs']:
        p = ROOT / i['path']
        if p.is_file() and '*' not in i['path']:
            from science.limits.common import sha256_file
            assert sha256_file(p) == i['sha256'], f'{i["path"]} changed since the cube was built'


def test_schema_rejects_bad_kind():
    jsonschema = pytest.importorskip('jsonschema')
    bad = {'schema': 'scenario-cube-v1', 'cube_id': 'x', 'site_id': 'x', 'label': 'x', 'generated_utc': 'x',
           'dims': [{'name': 'Q', 'kind': 'probability', 'values': [1], 'units': '', 'label': ''}],
           'metrics': {'a': {'units': '', 'label': '', 'dtype': 'int32', 'values': [1], 'provenance': ''}},
           'missing': {'encoding': 'sparse-flat-index', 'by_metric': {}},
           'provenance': {'inputs': [], 'command': '', 'code_commit': ''}}
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(bad, json.loads(SCHEMA.read_text()))


def test_browser_payload_under_20mb():
    for site_dir in CUBES.glob('*'):
        total = sum(p.stat().st_size for p in site_dir.glob('*') if p.is_file())
        assert total < 20e6, f'{site_dir.name}: {total / 1e6:.1f} MB'


# ------------------------------------------------------------------ round trip / baseline
@pytest.mark.parametrize('site', ['site04_roi3', 'site01_roi6'])
def test_round_trip_bundle_metrics(site):
    """Every value the bundle already holds for a cube cell must come back from the cube identically."""
    c = _cube(site, 'centre_mast_schedule.json.gz')
    b = json.loads((ROOT / 'data' / 'bundles' / f'{site}_2026-11-14_14d_mast1m.json').read_text())
    at = {'T': 0, 'D_mast': 0, 'S': 0}
    m = b['metrics']
    assert round(_val(c, 'sun_pct', at), 3) == m['sun_center_visible_pct_hourly_samples']
    assert round(_val(c, 'sun_earth_pct', at), 3) == m['sun_and_earth_center_visible_pct_hourly_samples']
    assert round(_val(c, 'earth_pct', at), 3) == m['earth_center_visible_pct_hourly_samples']
    ms = b['derived']['margin_series']
    for ci, cid in enumerate(ms['clone_ids']):
        k = cid if isinstance(cid, int) else int(''.join(ch for ch in str(cid) if ch.isdigit()))
        at = {'T': k, 'D_mast': 0, 'S': 0}
        assert round(_val(c, 'sun_pct', at), 3) == pytest.approx(ms['sun_center_visible_pct_hourly_by_clone'][ci], abs=1e-3), cid
        assert round(_val(c, 'earth_pct', at), 3) == pytest.approx(ms['earth_center_visible_pct_hourly_by_clone'][ci], abs=1e-3), cid
    # the 10 m bundle (where present) is the D_mast = 10 cell
    b10 = ROOT / 'data' / 'bundles' / f'{site}_2026-11-14_14d_mast10m.json'
    if b10.exists():
        m10 = json.loads(b10.read_text())['metrics']
        at = {'T': 0, 'D_mast': 9, 'S': 0}
        assert round(_val(c, 'sun_pct', at), 3) == m10['sun_center_visible_pct_hourly_samples']
        assert round(_val(c, 'sun_earth_pct', at), 3) == m10['sun_and_earth_center_visible_pct_hourly_samples']


def test_site04_baseline_numbers():
    c = _cube('site04_roi3', 'centre_mast_schedule.json.gz')
    at = {'T': 0, 'D_mast': 0, 'S': 0}
    assert _val(c, 'sun_pct', at) == pytest.approx(94.36, abs=0.005)
    assert _val(c, 'sun_earth_pct', at) == pytest.approx(72.11, abs=0.005)
    assert _val(c, 'sun_gap_h', at) == 19
    clones = [_val(c, 'sun_pct', {'T': k, 'D_mast': 0, 'S': 0}) for k in range(1, 21)]
    assert min(clones) == pytest.approx(87.54, abs=0.005) and max(clones) == pytest.approx(97.33, abs=0.005)
    assert _derived(c, 'band_over_T', 'sun_pct_min', {'D_mast': 0, 'S': 0}) == pytest.approx(87.54, abs=0.005)
    idx = json.loads((CUBES / 'site04_roi3' / 'index.json').read_text())
    assert idx['baseline']['sun_pct']['cube'] == idx['baseline']['sun_pct']['bundle']
    # position cube centre cell (daily start 0 = 2026-11-14 00:00) is the same cell
    p = _cube('site04_roi3', 'position_schedule.json.gz')
    centre = next(d for d in p['dims'] if d['name'] == 'D_pos')['nominal_index']
    assert _val(p, 'sun_pct', {'T': 0, 'D_pos': centre, 'S': 0}) == _val(c, 'sun_pct', at)


# ------------------------------------------------------------------ robust outputs
@pytest.mark.parametrize('name,dd', [('centre_mast_schedule.json.gz', 'D_mast'), ('position_schedule.json.gz', 'D_pos')])
def test_band_k_regret_identities(name, dd):
    c = _cube('site04_roi3', name)
    nd = len(next(d for d in c['dims'] if d['name'] == dd)['values'])
    ns = len(next(d for d in c['dims'] if d['name'] == 'S')['values'])
    rng = random.Random(7)
    for _ in range(10):
        j, s = rng.randrange(nd), rng.randrange(ns)
        vals = [_val(c, 'sun_pct', {'T': t, dd: j, 'S': s}) for t in range(21)]
        assert _derived(c, 'band_over_T', 'sun_pct_min', {dd: j, 'S': s}) == pytest.approx(min(vals))
        assert _derived(c, 'band_over_T', 'sun_pct_max', {dd: j, 'S': s}) == pytest.approx(max(vals))
        ok = []
        for t in range(1, 21):
            a = {'T': t, dd: j, 'S': s}
            ok.append(_val(c, 'sun_pct', a) >= 70 - 1e-9 and _val(c, 'sun_earth_pct', a) >= 40 - 1e-9 and _val(c, 'sun_gap_h', a) <= 120)
        assert _derived(c, 'k_of_N', 'k_pass', {'R': 0, dd: j, 'S': s}) == sum(ok)
        both = np.array([[_val(c, 'sun_earth_pct', {'T': t, dd: jj, 'S': s}) for jj in range(nd)] for t in range(21)])
        dstar = int(np.argmax(both[0]))
        assert _derived(c, 'regret', 'chosen_index', {'S': s}) == dstar
        reg = max(both[t].max() - both[t, dstar] for t in range(1, 21))
        assert _derived(c, 'regret', 'regret_max_pct', {'S': s}) == pytest.approx(reg, abs=1e-3)
        assert reg >= 0


def test_strict_preset_never_passes_more_than_team():
    c = _cube('site04_roi3', 'centre_mast_schedule.json.gz')
    k = c['derived']['k_of_N']['metrics']['k_pass']['values']
    n = len(k) // 3
    team, strict, loose = k[:n], k[n:2 * n], k[2 * n:]
    assert all(s <= t <= l for s, t, l in zip(strict, team, loose))


def test_mast_monotone():
    """A taller mast on the same terrain lowers every terrain elevation angle, so Sun % per start cannot
    decrease with mast height on any map."""
    c = _cube('site04_roi3', 'centre_mast_schedule.json.gz')
    rng = random.Random(3)
    for _ in range(300):
        t, s = rng.randrange(21), rng.randrange(8761)
        v = [_val(c, 'sun_pct', {'T': t, 'D_mast': j, 'S': s}) for j in range(10)]
        assert all(b >= a - 1e-9 for a, b in zip(v, v[1:])), (t, s, v)


# ------------------------------------------------------------------ slicing vs independent recomputation
def _need_caches():
    from science.cube import compute as C
    from science.cube import ephem_year as E
    if not (E.RAW / 'site04_roi3_year.npz').exists() or not (C.SKY / 'site04_roi3_nominal_m1_x0_y0.json').exists():
        pytest.skip('cube caches not present')
    return C, E


def test_slices_match_recomputation():
    """10 random cells of each cube vs a fresh evaluation from the cached skylines with the scalar
    science/crossings.margins (independent of the vectorised path the builder uses)."""
    C, E = _need_caches()
    b = json.loads(B04.read_text())
    eph = E.load('site04_roi3', b['site']['lat_deg'], b['site']['lon_deg_east'], b['site']['height_m'])
    rng = random.Random(11)
    for name, dd, stride in (('centre_mast_schedule.json.gz', 'D_mast', 1), ('position_schedule.json.gz', 'D_pos', 24)):
        c = _cube('site04_roi3', name)
        dvals = next(d for d in c['dims'] if d['name'] == dd)['values']
        for _ in range(10):
            t, j = rng.randrange(21), rng.randrange(len(dvals))
            s = rng.randrange(len(c['dims'][2]['values']))
            if dd == 'D_mast':
                sky = C.skyline('site04_roi3', C.T_IDS[t], float(dvals[j])); xfer = None
            else:
                dx, dy = (int(q) for q in dvals[j].split(','))
                sky = C.skyline('site04_roi3', C.T_IDS[t], 1.0, dx, dy)
                s0 = C.sites.SITES['site04_roi3']; la, lo = C.offset_latlon('site04_roi3', dx, dy)
                xfer = (s0['lat'], s0['lon'], la, lo)
            i0 = s * stride
            sl = slice(i0, i0 + E.WINDOW_H + 1)
            vis = {}
            for body in ('sun', 'earth'):
                az, el = eph[f'{body}_az'][sl], eph[f'{body}_el'][sl]
                if xfer:
                    az, el = C.transfer_azel(az, el, *xfer)
                vis[body] = np.array([X.margins({'az_deg': a, 'el_deg': e, 'radius_deg': 0.27}, sky)['margin_perp_deg'] > 0
                                      for a, e in zip(az, el)])
            n = E.WINDOW_H + 1
            at = {'T': t, dd: j, 'S': s}
            assert _val(c, 'sun_pct', at) == pytest.approx(100 * vis['sun'].sum() / n)
            assert _val(c, 'sun_earth_pct', at) == pytest.approx(100 * (vis['sun'] & vis['earth']).sum() / n)
            run = best = 0
            for f in vis['sun']:
                run = 0 if f else run + 1; best = max(best, run)
            assert _val(c, 'sun_gap_h', at) == best


def test_ephemeris_first_window_equals_bundle():
    C, E = _need_caches()
    b = json.loads(B04.read_text())
    eph = E.load('site04_roi3', 0, 0, 0)
    assert eph['t'].size == E.N_STARTS + E.WINDOW_H
    for i, smp in enumerate(b['samples']):
        assert eph['t'][i] == smp['t_unix']
        assert eph['sun_az'][i] == smp['sun']['az_deg'] and eph['earth_el'][i] == smp['earth']['el_deg']


def test_multi_skyline_bit_identical():
    """The batched solver equals science/skyline.compute_skyline exactly (clone, offset, non-1 m mast)."""
    _need_caches()
    from science import frames, sites
    from science.cube import compute as C
    from science.skyline import compute_skyline
    try:
        far = sites.far_dem('site04_roi3'); nd = sites.near_dem('site04_roi3', clone=3)
    except Exception as e:  # noqa: BLE001
        pytest.skip(f'DEM cache unavailable: {e}')
    la, lo = C.offset_latlon('site04_roi3', -25, 50)
    r = C.multi_skyline(la, lo, {'clone03': nd}, far, {'clone03': [2.0]})[('clone03', 2.0)]
    x, y = frames.stereo_forward(la, lo)
    ref = compute_skyline(la, lo, float(nd.sample(x, y)), 2.0, near=nd, far=far, bins=720,
                          max_range_m=sites.MAX_RANGE_M, step_m=sites.NEAR_RAY_STEP_M)
    assert r['elevation_deg'] == ref['elevation_deg']
    assert r['status'] == ref['status'] and r['near_cut_m'] == ref['near_cut_m']


def test_margins_vec_equals_scalar():
    C, E = _need_caches()
    sky = C.skyline('site04_roi3', 'nominal', 1.0)
    rng = np.random.default_rng(1)
    az = rng.uniform(0, 360, 500); el = rng.uniform(-3, 3, 500)
    m, mp = C.margins_vec(az, el, sky)
    ref = np.array([X.margins({'az_deg': a, 'el_deg': e, 'radius_deg': 0.27}, sky)['margin_perp_deg'] for a, e in zip(az, el)])
    assert np.array_equal(mp, ref)


def test_window_metrics_synthetic():
    from science.cube.compute import window_metrics
    sun = np.array([1, 1, 0, 0, 0, 1, 0, 1, 1, 1], bool)
    earth = np.array([1, 0, 1, 1, 1, 1, 1, 1, 0, 0], bool)
    w = window_metrics(sun, earth, n_starts=6, window_h=4)
    assert w['sun_n'].tolist() == [2, 2, 1, 2, 3, 4]
    assert w['sun_gap_h'].tolist() == [3, 3, 3, 2, 1, 1]
    assert w['both_n'].tolist() == [1, 1, 1, 2, 2, 2]


def test_transfer_azel_identity_and_offset():
    from science.cube.compute import transfer_azel
    az = np.array([0.0, 90.0, 200.0]); el = np.array([1.0, -2.0, 5.0])
    a2, e2 = transfer_azel(az, el, -89.78, -156.3, -89.78, -156.3)
    assert np.allclose(a2, az, atol=1e-9) and np.allclose(e2, el, atol=1e-9)
    a3, e3 = transfer_azel(az, el, -89.78, -156.3, -89.781, -156.3)   # ~30 m away
    assert np.max(np.abs(e3 - el)) < 0.01
