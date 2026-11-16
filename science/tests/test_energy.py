"""Phase 5 energy margin (ENGINEERING ASSUMPTION): science/energy/model.py and data/cubes/<site>/energy.json.gz.

Synthetic tests run everywhere; tests against the built cube skip when it (or the git-ignored ephemeris cache) is absent."""
import copy
import gzip
import json
from pathlib import Path

import numpy as np
import pytest

from science.energy import model as M

ROOT = Path(__file__).resolve().parents[2]
SITES = ('site04_roi3', 'site01_roi6')


@pytest.fixture
def cfg():
    return M.load_config()


def _cfg(cfg, **battery):
    c = copy.deepcopy(cfg)
    c['battery'].update(battery)
    return c


def _profile(n=336, seed=0):
    """Day/night-like generation (W) and a varying load (W), 1 h steps."""
    rng = np.random.default_rng(seed)
    gen = np.where((np.arange(n) // 60) % 2 == 0, 900.0, 0.0) * rng.uniform(0.5, 1.0, n)
    load = 150.0 + 100.0 * ((np.arange(n) % 24) < 4)
    return gen, load


# ---------------------------------------------------------------- config

def test_yaml_subset_parser_matches_file(cfg):
    sub = M._parse_subset(M.DEFAULT_CONFIG.read_text())
    assert sub == cfg
    assert cfg['label'] == 'ENGINEERING ASSUMPTION'
    assert cfg['load']['scheduled'][0]['duration_h'] == 4


def test_config_rejects_bad_efficiency(tmp_path):
    p = tmp_path / 'bad.yaml'
    p.write_text(M.DEFAULT_CONFIG.read_text().replace('charge_efficiency: 0.95', 'charge_efficiency: 1.5'))
    with pytest.raises(ValueError):
        M.load_config(p)


# ---------------------------------------------------------------- power

def test_power_formula_and_inverse_square(cfg):
    p = M.power_w(cfg, 'vsat', 1.0, 0.0, 0.0, 1.0)
    assert p == pytest.approx(1361.0 * cfg['array']['area_m2'] * cfg['array']['efficiency'])
    p2 = M.power_w(cfg, 'vsat', 1.0, 0.0, 0.0, 2.0)
    assert p2 == pytest.approx(p / 4)
    assert M.power_w(cfg, 'vsat', 0.5, 60.0, 0.0, 1.0) == pytest.approx(p * 0.5 * 0.5)
    assert M.power_w(cfg, 'vsat', 0.0, 1.0, 0.0, 1.0) == 0.0


def test_fixed_vertical_incidence(cfg):
    phi = cfg['array']['fixed_azimuth_deg']
    assert M.cos_incidence('fixed_vertical', 0.0, phi, phi) == pytest.approx(1.0)
    assert M.cos_incidence('fixed_vertical', 0.0, phi + 60, phi) == pytest.approx(0.5)
    assert M.cos_incidence('fixed_vertical', 0.0, phi + 180, phi) == 0.0          # behind the face
    # never more than the tracking array
    az = np.linspace(0, 360, 73); el = np.full_like(az, 3.0)
    assert (M.cos_incidence('fixed_vertical', el, az, phi) <= M.cos_incidence('vsat', el) + 1e-15).all()


def test_scheduled_load(cfg):
    t = np.arange(48) * 3600.0                               # 1970-01-01 00:00 UTC + 48 h
    L = M.load_w(cfg, t)
    s = cfg['load']['scheduled'][0]
    on = ((np.arange(48) % 24) >= s['utc_hour_start']) & ((np.arange(48) % 24) < s['utc_hour_start'] + s['duration_h'])
    assert np.array_equal(L, cfg['load']['constant_w'] + s['power_w'] * on)


# ---------------------------------------------------------------- battery

def test_energy_conservation_over_cycle(cfg):
    gen, load = _profile()
    for C in (3000.0, 8000.0, 50000.0):
        for soc0 in (1.0, 0.5):
            c = _cfg(cfg, initial_soc=soc0)
            r = M.simulate(gen, load, C, c, ledger=True)
            dE = r['soc'][-1] - r['soc'][0]
            rhs = r['gen'] - r['served'] - r['curtailed'] - r['loss']
            assert dE == pytest.approx(rhs, abs=1e-6)
            assert r['soc'].min() >= -1e-9 and r['soc'].max() <= C + 1e-9
    # a lossless battery never over full or empty returns exactly what was put in
    c = _cfg(cfg, charge_efficiency=1.0, discharge_efficiency=1.0, initial_soc=0.5)
    g = np.array([300.0, 300.0, 0.0, 0.0]); l = np.array([100.0, 100.0, 200.0, 200.0])
    r = M.simulate(g, l, 10000.0, c, ledger=True)
    assert r['soc'][-1] == pytest.approx(r['soc'][0]) and r['loss'] == pytest.approx(0) and r['unmet'] == 0


def test_round_trip_efficiency_losses(cfg):
    c = _cfg(cfg, initial_soc=0.5)
    r = M.simulate(np.array([1000.0, 0.0]), np.array([0.0, 950.0 * 0.95]), 10000.0, c, ledger=True)
    # 1000 Wh in -> 950 stored -> 902.5 Wh delivered back: ends where it started
    assert r['soc'][-1] == pytest.approx(r['soc'][0])
    assert r['loss'] == pytest.approx(1000 - 950 * 0.95)


def test_more_battery_fewer_hours_below_reserve(cfg):
    for seed in range(5):
        gen, load = _profile(seed=seed)
        for soc0 in (1.0, 0.6):
            c = _cfg(cfg, initial_soc=soc0)
            caps = np.linspace(500, 40000, 60)
            r = M.simulate(np.broadcast_to(gen, (60, gen.size)), load, caps, c)
            h = r['hours_below_reserve']
            assert (np.diff(h) <= 0).all(), h
            assert h[0] > 0 and h[-1] == 0


def test_zero_load_never_depletes(cfg):
    gen, _ = _profile()
    for g in (gen, np.zeros_like(gen)):
        r = M.simulate(g, np.zeros_like(g), 5000.0, cfg)
        assert (np.diff(r['soc']) >= -1e-12).all()
        assert r['hours_below_reserve'] == 0
        assert r['min_soc_frac'] == pytest.approx(cfg['battery']['initial_soc'])
    need = M.capacity_needed(np.zeros(100), np.zeros(100), cfg)
    assert need == pytest.approx(cfg['battery']['reserve_wh'] / cfg['battery']['initial_soc'], abs=1.0)


def test_always_lit_synthetic(cfg):
    """Sun always fully visible with cos = 1: power exceeds load every hour, so the battery never leaves full
    and the capacity needed is the reserve alone."""
    n = 336
    P = M.power_w(cfg, 'vsat', np.ones(n), np.zeros(n), np.zeros(n), np.ones(n))
    load = M.load_w(cfg, np.arange(n) * 3600.0)
    assert (P > load).all()
    r = M.simulate(P, load, 20000.0, cfg, ledger=True)
    assert r['soc'].min() == pytest.approx(20000.0) and r['hours_below_reserve'] == 0 and r['unmet'] == 0
    assert M.capacity_needed(P, load, cfg) == pytest.approx(cfg['battery']['reserve_wh'], abs=1.0)


def test_capacity_needed_bisection_matches_drawdown(cfg):
    """With initial SoC = 1 the need is reserve + max drawdown below full (Lindley recursion), independent of C."""
    ec, ed = cfg['battery']['charge_efficiency'], cfg['battery']['discharge_efficiency']
    for seed in range(5):
        gen, load = _profile(seed=seed)
        net = gen - load
        D, Dmax = 0.0, 0.0
        for x in net:
            D = max(0.0, D - (x * ec if x >= 0 else x / ed))
            Dmax = max(Dmax, D)
        need = M.capacity_needed(gen, load, cfg)
        assert need == pytest.approx(cfg['battery']['reserve_wh'] + Dmax, abs=1.01)
        assert M.simulate(gen, load, need, cfg)['ok']
        assert not M.simulate(gen, load, need - 2.0, cfg)['ok']


def test_capacity_needed_general_soc(cfg):
    c = _cfg(cfg, initial_soc=0.4)
    gen, load = _profile(seed=3)
    need = M.capacity_needed(gen, load, c)
    assert M.simulate(gen, load, need, c)['ok'] and not M.simulate(gen, load, need - 2.0, c)['ok']
    caps = np.linspace(need * 0.5, need * 0.999, 20)
    assert not M.simulate(np.broadcast_to(gen, (20, gen.size)), load, caps, c)['ok'].any()


# ---------------------------------------------------------------- built cube

def _energy(site):
    p = ROOT / 'data' / 'cubes' / site / 'energy.json.gz'
    if not p.exists():
        pytest.skip(f'{p} not built')
    return json.loads(gzip.decompress(p.read_bytes()))


def _inputs(site):
    from science.cube import ephem_year as E
    if not (E.RAW / f'{site}_year.npz').exists():
        pytest.skip('ephemeris cache absent')
    from science.energy import build_energy as B
    return B, B.load_inputs(site)


@pytest.mark.parametrize('site', SITES)
def test_antenna_height_and_earth_never_change_power(site, cfg):
    B, inp = _inputs(site)
    P0 = B.hourly_power(inp, cfg)
    c = copy.deepcopy(cfg); c['not_used_by_power']['antenna_height_m'] = 37.0
    alt = dict(inp); alt['eph'] = dict(inp['eph'])
    for k in ('earth_az', 'earth_el', 'earth_r', 'earth_range_au'):
        alt['eph'][k] = np.random.default_rng(1).uniform(-90, 90, inp['eph'][k].shape)
    assert np.array_equal(P0, B.hourly_power(alt, c))
    # the mast axis is the ARRAY top: power does change with D_mast (disc fraction at that height)
    assert not np.array_equal(P0[:, :, 0], P0[:, :, 4])


@pytest.mark.parametrize('site', SITES)
def test_cube_schema_and_cells(site, cfg):
    from jsonschema import validate
    c = _energy(site)
    validate(c, json.loads((ROOT / 'schemas' / 'scenario-cube-v1.schema.json').read_text()))
    assert c['label'] == 'ENGINEERING ASSUMPTION'
    assert [d['name'] for d in c['dims']] == ['T', 'D_array', 'D_mast', 'S']
    shape = [len(d['values']) for d in c['dims']]
    assert shape == [21, 2, 10, 366]
    for k, m in c['metrics'].items():
        assert len(m['values']) == int(np.prod(shape)), k
    assert c['fixed']['battery_capacity_wh'] == cfg['battery']['capacity_wh']
    idx = json.loads((ROOT / 'data' / 'cubes' / site / 'index.json').read_text())
    assert 'energy.json.gz' in [e['file'] for e in idx['cubes']]
    # recompute a few cells from scratch
    B, inp = _inputs(site)
    rng = np.random.default_rng(7)
    starts = rng.choice(366, 3, replace=False) * 24
    out, _ = B.compute(site, cfg, inp, starts=starts)
    need = np.asarray(c['metrics']['battery_needed_kwh']['values']).reshape(shape)
    hrs = np.asarray(c['metrics']['hours_below_reserve_h']['values']).reshape(shape)
    si = starts // 24
    assert np.array_equal(need[..., si], np.ceil(out['need_wh'] - 1e-9).astype(int))
    assert np.array_equal(hrs[..., si], np.rint(out['hours_below']).astype(int))


@pytest.mark.parametrize('site', SITES)
def test_cube_derived_consistent(site):
    c = _energy(site)
    shape = [len(d['values']) for d in c['dims']]
    need = np.asarray(c['metrics']['battery_needed_kwh']['values']).reshape(shape)
    kb = np.asarray(c['derived']['battery_for_k_maps']['metrics']['battery_kwh']['values']).reshape([20] + shape[1:])
    assert np.array_equal(kb[-1], need[1:].max(axis=0))
    assert (np.diff(kb, axis=0) >= 0).all()
    band = c['derived']['band_over_T']['metrics']
    assert np.array_equal(np.asarray(band['battery_needed_kwh_max']['values']).reshape(shape[1:]), need.max(axis=0))
    tr = c['derived']['trade']['metrics']
    assert np.array_equal(np.asarray(tr['worst20_worst_start_kwh']['values']).reshape(shape[1:3]), need[1:].max(axis=(0, 3)))
    assert np.array_equal(np.asarray(tr['nominal_demo_kwh']['values']).reshape(shape[1:3]), need[0, :, :, 0])
    # the need always covers the reserve; k of 20 at capacity agrees with the need
    cap = c['fixed']['battery_capacity_wh']
    assert need.min() >= c['fixed']['reserve_wh']
    kp = np.asarray(c['derived']['pass_at_capacity']['metrics']['k_pass']['values']).reshape(shape[1:])
    clear = (np.abs(need[1:] - cap) > 2).all(axis=0)          # stored need is within 1 Wh above the true need
    assert np.array_equal(kp[clear], (need[1:] <= cap).sum(axis=0)[clear])
    # the tracking array never needs more battery than the fixed array with identical inputs
    assert (need[:, 0] <= need[:, 1] + 1).all()
