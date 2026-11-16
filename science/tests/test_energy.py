"""Phase 5 energy margin (ENGINEERING ASSUMPTION): conservation, monotonicity, zero load, always lit, analytic
bounds, antenna-height independence, and the written cube against a fresh recomputation."""
import gzip
import json
from dataclasses import replace
from pathlib import Path

import numpy as np
import pytest

from science.energy import model as M

ROOT = Path(__file__).resolve().parents[2]
CUBES = ROOT / 'data' / 'cubes'
BAT = M.Battery(capacity_wh=5000, charge_efficiency=0.9, discharge_efficiency=0.85, min_reserve_fraction=0.2,
                initial_soc_fraction=0.8)
SITES = ['site04_roi3', 'site01_roi6']


def _cycle(n_days=6, seed=3):
    rng = np.random.default_rng(seed)
    h = np.arange(24 * n_days)
    gen = np.where((h % 24) < 12, 600.0, 0.0) * rng.uniform(0.5, 1.0, h.size)
    load = 150.0 + 100.0 * ((h % 24) >= 18)
    return gen, load


def test_energy_conservation_over_charge_discharge_cycle():
    gen, load = _cycle()
    for cap in (500.0, 3000.0, 5000.0, 20000.0):         # spill-limited, deficit-limited, both, neither
        L = M.simulate(gen, load, cap, BAT)
        # battery: stored - drawn = change in state of charge
        assert L['soc_end'] - L['soc0'] == pytest.approx(L['charged'] - L['discharged'], abs=1e-6)
        # bus: generation - load = offered to battery + spilled - delivered by battery - unserved
        lhs = L['gen'] - L['load']
        rhs = (L['charged'] / BAT.charge_efficiency + L['spilled']) - (L['discharged'] * BAT.discharge_efficiency + L['unserved'])
        assert lhs == pytest.approx(rhs, abs=1e-6)
        assert L['spilled'] >= -1e-9 and L['unserved'] >= -1e-9
        assert 0 <= L['min_soc'] <= cap and L['soc_end'] <= cap + 1e-9


def test_more_battery_means_fewer_hours_below_reserve_and_monotone_feasibility():
    gen, load = _cycle(10, seed=7)
    caps = np.linspace(200, 40000, 60)
    hours = [int(M.simulate(gen, load, c, BAT)['hours_below_reserve']) for c in caps]
    ok = [bool(M.feasible(M.simulate(gen, load, c, BAT))) for c in caps]
    assert all(a >= b for a, b in zip(hours, hours[1:])), hours
    assert hours[0] > 0 and hours[-1] == 0
    assert ok == sorted(ok)                     # infeasible ... feasible, never back
    need = float(M.battery_needed(gen, load, BAT))
    assert M.feasible(M.simulate(gen, load, need, BAT))
    assert not M.feasible(M.simulate(gen, load, need * (1 - 1e-4), BAT))
    assert M.simulate(gen, load, need, BAT)['hours_below_reserve'] == 0


def test_zero_load_never_depletes():
    gen, _ = _cycle()
    for g in (gen, np.zeros_like(gen)):
        L = M.simulate(g, 0.0, 4000.0, BAT)
        assert L['hours_below_reserve'] == 0 and L['unserved'] == 0
        assert L['min_soc'] == pytest.approx(BAT.initial_soc_fraction * 4000.0)
    assert float(M.battery_needed(gen, np.zeros_like(gen), BAT)) < 1e-3


def test_synthetic_always_lit_case():
    """Sun always fully visible at constant range: power is the closed form and a load below it needs no battery."""
    H = 400
    rng = np.random.default_rng(0)
    el = rng.uniform(-1.7, 1.7, H); az = rng.uniform(0, 360, H)
    P = M.power_w(np.ones(H), el, az, np.ones(H), 2.0, 0.28, 'vsat')
    assert P == pytest.approx(1361.0 * 2.0 * 0.28 * np.cos(np.radians(el)), rel=1e-12)
    assert P.min() > 1361 * 0.56 * 0.999
    e = M.interval_energy_wh(P)
    L = M.simulate(e, 500.0, 1000.0, BAT)
    assert L['hours_below_reserve'] == 0 and L['unserved'] == 0 and L['min_soc'] == pytest.approx(800.0)
    assert float(M.battery_needed(e, np.full(e.size, 500.0), BAT)) < 1e-3
    # 1/r^2 scaling and fixed-array cosine law
    assert M.irradiance(0.5) == pytest.approx(4 * 1361.0)
    assert M.cos_incidence(0.0, 90.0, 'fixed_vertical', 90.0) == pytest.approx(1.0)
    assert M.cos_incidence(0.0, 150.0, 'fixed_vertical', 90.0) == pytest.approx(0.5)
    assert M.cos_incidence(0.0, 270.0, 'fixed_vertical', 90.0) == 0.0


def test_always_dark_battery_needed_matches_closed_form():
    load = np.full(336, 166.0)
    need = float(M.battery_needed(np.zeros(336), load, BAT))
    exact = load.sum() / (BAT.discharge_efficiency * (BAT.initial_soc_fraction - BAT.min_reserve_fraction))
    assert need == pytest.approx(exact, rel=1e-6)


def test_vectorised_windows_equal_scalar_runs():
    rng = np.random.default_rng(5)
    e_gen = rng.uniform(0, 400, (3, 500)); e_load = rng.uniform(100, 250, 500)
    starts = np.array([0, 50, 150])
    step = M.window_stepper(e_gen, e_load, starts)
    V = M.simulate(None, None, 3000.0, BAT, n_steps=100, step=step)
    for i in range(3):
        for j, s in enumerate(starts):
            L = M.simulate(e_gen[i, s:s + 100], e_load[s:s + 100], 3000.0, BAT)
            assert V['hours_below_reserve'][i, j] == L['hours_below_reserve']
            assert V['min_soc'][i, j] == pytest.approx(float(L['min_soc']), abs=1e-9)


def test_scheduled_load_profile():
    cfg = M.load_config()
    t = np.arange(48) * 3600.0              # 1970-01-01 00:00 UTC + hours
    l = M.load_w(t, cfg)
    assert l[0] == cfg.constant_w
    s = cfg.scheduled[0]
    on = [h for h in range(48) if l[h] > cfg.constant_w]
    assert on == [h for h in range(48) if (h - s['start_utc_hour']) % s['every_h'] < s['duration_h']]


def test_yaml_subset_parser_matches_file_and_rejects_junk():
    d = M.parse_simple_yaml((ROOT / 'science/energy/assumptions.yaml').read_text())
    assert d['battery']['capacity_wh'] == 10000 and d['array']['fixed_azimuth_deg'] == 'auto'
    assert d['load']['scheduled'][0]['every_h'] == 24
    with pytest.raises(ValueError):
        M.parse_simple_yaml('a: 1\n   b: 2\n')
    with pytest.raises(ValueError):
        M.Battery(1000, 0.9, 0.9, 0.5, 0.4)


# ---------------------------------------------------------------- real site data

def _have(site):
    return (CUBES / site / 'disc_fraction_hourly.json.gz').exists() and \
        (ROOT / 'data/cache/cube_horizons' / f'{site}_year.npz').exists()


@pytest.mark.parametrize('site', SITES)
def test_antenna_height_never_changes_power(site):
    if not _have(site):
        pytest.skip('cube inputs not present')
    from science.energy.build_energy import load_disc
    from science.cube.build_cube import site_inputs
    f, masts, _t, _p = load_disc(site)
    _b, eph = site_inputs(site)
    cfg = M.load_config()
    for a in M.ARRAY_TYPES:
        ref = M.layout_power(eph, f[0], masts, M.Layout(array_top_m=1.0, antenna_top_m=1.0), cfg, a, 90.0)
        for ant in (0.5, 3.0, 10.0, 15.0):
            p = M.layout_power(eph, f[0], masts, M.Layout(array_top_m=1.0, antenna_top_m=ant), cfg, a, 90.0)
            assert np.array_equal(p, ref)
    hi = M.layout_power(eph, f[0], masts, M.Layout(array_top_m=10.0, antenna_top_m=1.0), cfg, 'vsat')
    assert hi.mean() >= ref.mean() - 1e-9 and not np.array_equal(hi, ref)     # array height does matter


def _cube(site):
    p = CUBES / site / 'energy.json.gz'
    if not p.exists():
        pytest.skip('energy cube not built')
    return json.loads(gzip.decompress(p.read_bytes()))


@pytest.mark.parametrize('site', SITES)
def test_energy_cube_contract_and_index(site):
    c = _cube(site)
    import jsonschema
    jsonschema.validate(c, json.loads((ROOT / 'schemas/scenario-cube-v1.schema.json').read_text()))
    assert c['label'] == 'ENGINEERING ASSUMPTION' and c['fixed']['label'] == 'ENGINEERING ASSUMPTION'
    sizes = [len(d['values']) for d in c['dims']]
    assert [d['name'] for d in c['dims']] == ['T', 'D_array', 'D_mast', 'S'] and sizes == [21, 2, 10, 366]
    for m in c['metrics'].values():
        assert len(m['values']) == int(np.prod(sizes))
    cfg = M.load_config()
    assert c['fixed']['battery_capacity_wh'] == cfg.battery.capacity_wh
    assert c['fixed']['load_constant_w'] == cfg.constant_w
    idx = json.loads((CUBES / site / 'index.json').read_text())
    e = [x for x in idx['cubes'] if x['file'] == 'energy.json.gz']
    assert len(e) == 1 and e[0]['label'] == 'ENGINEERING ASSUMPTION'
    from science.limits.common import sha256_file
    assert e[0]['sha256'] == sha256_file(CUBES / site / 'energy.json.gz')
    assert (CUBES / site / 'energy.json.gz').stat().st_size < 20e6


@pytest.mark.parametrize('site', SITES)
def test_energy_cube_monotone_and_consistent(site):
    c = _cube(site)
    sizes = [len(d['values']) for d in c['dims']]
    need = np.asarray(c['metrics']['battery_needed_kwh']['values']).reshape(sizes)
    hrs = np.asarray(c['metrics']['hours_below_reserve']['values']).reshape(sizes)
    cap = c['fixed']['battery_capacity_wh']
    # the YAML capacity holds the reserve exactly where it is at least the battery needed (1 Wh rounding)
    assert np.array_equal(hrs == 0, need <= cap)
    # VSAT never needs more than a fixed vertical face on the same map, mast and start (it tracks the Sun)
    assert np.all(need[:, 0] <= need[:, 1] + 1)
    # nothing exceeds the zero-generation bound for the heaviest possible window load
    cfg = M.load_config(); bat = cfg.battery
    peak = (cfg.constant_w + sum(x['power_w'] for x in cfg.scheduled)) * 336
    assert need.max() <= np.ceil(M.capacity_upper_bound(peak, bat)) + 1
    k = c['derived']['k_of_N_capacity']['metrics']['k_ok']['values']
    assert min(k) >= 0 and max(k) <= 20
    tr = c['derived']['trade']['metrics']
    n = len(c['dims'][2]['values'])
    for a in range(2):
        for j in range(n):
            f = a * n + j
            assert tr['needed_demo_nominal']['values'][f] == need[0, a, j, 0]
            assert tr['needed_all_worst20']['values'][f] == need[1:, a, j].max()
    nk = c['derived']['needed_by_k']['metrics']['needed_all']['values']
    nk = np.asarray(nk).reshape(2, n, 20)
    assert np.all(np.diff(nk, axis=-1) >= 0)
    assert np.array_equal(nk[..., -1], np.asarray(tr['needed_all_worst20']['values']).reshape(2, n))


@pytest.mark.parametrize('site', SITES)
def test_energy_cube_cells_match_fresh_scalar_recomputation(site):
    c = _cube(site)
    if not _have(site):
        pytest.skip('cube inputs not present')
    from science.energy.build_energy import site_series
    cfg = M.load_config()
    s = site_series(site, cfg)
    e_gen = M.interval_energy_wh(s['P']); e_load = M.load_w(s['t'][:-1], cfg)
    sizes = [len(d['values']) for d in c['dims']]
    rng = np.random.default_rng(11)
    for _ in range(6):
        i, a, j, k = (int(rng.integers(n)) for n in sizes)
        st = k * 24
        g = e_gen[i, a, j, st:st + 336]; l = e_load[st:st + 336]
        L = M.simulate(g, l, cfg.battery.capacity_wh, cfg.battery)
        flat = ((i * sizes[1] + a) * sizes[2] + j) * sizes[3] + k
        assert c['metrics']['hours_below_reserve']['values'][flat] == int(L['hours_below_reserve'])
        assert c['metrics']['battery_needed_kwh']['values'][flat] == int(M.round_up(M.battery_needed(g, l, cfg.battery)))
