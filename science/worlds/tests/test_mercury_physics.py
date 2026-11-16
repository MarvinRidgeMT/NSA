"""Mercury physics (prompt §3.2): Sun angular size vs the analytic perihelion/aphelion range, the 3:2 resonance and the
~176-day solar day (analytic and from Horizons samples), and solar-conjunction flags. Each test can fail."""
import json
import math
from pathlib import Path

import numpy as np
import pytest

from science.worlds import get_world
from science.worlds.mercury import physics as PH

ROOT = Path(__file__).resolve().parents[3]
BUNDLE = ROOT / 'data' / 'worlds' / 'mercury' / 'mercury_prokofiev_rim_2026-11-14_176d_mast1m.json'
MERC = get_world('mercury')


def _bundle():
    if not BUNDLE.exists():
        pytest.skip('Mercury bundle not built (python -m science.worlds.mercury.site)')
    return json.loads(BUNDLE.read_text())


# ---------------------------------------------------------------------------------------------------- analytic
def test_sun_size_formula():
    # 1 AU -> 0.5329 deg (IAU nominal R_sun 695 700 km); scales as 1/r
    assert PH.sun_angular_diameter_deg(1.0) == pytest.approx(0.53291, abs=1e-5)
    a = PH.analytic_sun_size_range()
    assert a['max_diam_deg'] == pytest.approx(1.733, abs=1e-3) and a['min_diam_deg'] == pytest.approx(1.142, abs=1e-3)
    assert a['ratio_max_min'] == pytest.approx(a['ratio_analytic_(1+e)/(1-e)'], rel=1e-4)
    assert a['ratio_max_min'] > 1.5                                  # "varies a lot": > 50 % between perihelion and aphelion


def test_resonance_analytic():
    r = PH.resonance()
    assert r['sidereal_rotation_days'] == pytest.approx(58.646, abs=1e-3)
    assert r['orbit_over_rotation'] == pytest.approx(1.5, abs=1e-3)          # 3:2 spin-orbit
    assert r['solar_day_days'] == pytest.approx(175.94, abs=0.05)              # ~176 d
    assert r['solar_day_over_orbit'] == pytest.approx(2.0, abs=1e-3)          # one solar day = two Mercury years


def test_solar_day_estimator_on_synthetic_eccentric_series():
    """The azimuth estimator must not be fooled by the equation of centre: build a polar-site Sun azimuth
    az = 360 t / T_sd - (nu - M) with a Kepler orbit (e = 0.2056) and recover T_sd; the naive first-360-crossing
    estimate is off by days (the trap the first draft fell into)."""
    P, Tsd, e = 87.969, 175.938, 0.2056
    t = np.arange(0, 176.0 * 24 + 1) * 3600.0
    M = 2 * np.pi * (t / 86400.0) / P + 0.26       # the real window's phase: perihelion 84.3 d after 2026-11-14
    E = M.copy()
    for _ in range(50):
        E = E - (E - e * np.sin(E) - M) / (1 - e * np.cos(E))
    nu = 2 * np.arctan2(np.sqrt(1 + e) * np.sin(E / 2), np.sqrt(1 - e) * np.cos(E / 2))
    eoc = np.degrees(np.unwrap(nu - M))
    az = (360.0 * (t / 86400.0) / Tsd - (eoc - eoc[0]) + 17.0) % 360.0
    sd = PH.solar_day_from_azimuth(t, az, P)
    assert sd['solar_day_days'] == pytest.approx(Tsd, abs=1e-3)
    u = np.degrees(np.unwrap(np.radians(az))) - az[0]
    first = t[np.nonzero(np.abs(u) >= 360)[0][0]] / 86400.0
    assert abs(first - Tsd) > 2.0


def test_conjunction_flags_synthetic():
    rows = [{'t': k * 3600.0, 'utc': f'T{k}', 'sep_deg': s, 'delta_au': d} for k, (s, d) in enumerate(
        [(5, 1.4), (2.0, 1.4), (1.0, 1.4), (2.5, 1.4), (6, 0.6), (2.0, 0.6), (4, 0.6)])]
    c = PH.conjunctions(rows, 2.3)
    assert c['outage_flags'] == [False, True, True, False, False, False, False]
    assert c['inferior_flags'] == [False, False, False, False, False, True, False]
    assert [s['kind'] for s in c['spans']] == ['superior', 'inferior']
    assert [m['kind'] for m in c['minima']] == ['superior', 'inferior']


def test_sep_threshold_is_cited():
    dte = [c for c in MERC.comms if c.id == 'dsn-dte'][0]
    assert dte.thresholds['sep_outage_x_band_deg'] == 2.3 and dte.thresholds['sep_outage_ka_band_deg'] == 1.0
    assert '810-005' in dte.source and '106' in dte.source and 'ENGINEERING' in dte.label
    assert not [c for c in MERC.comms if c.kind == 'relay'][0].wired                 # direct-to-Earth only


# ---------------------------------------------------------------------------------------------------- from Horizons
def test_horizons_sun_size_within_analytic_range():
    b = _bundle()
    s = b['world']['physics_checks']['sun_angular_size']; a = s['analytic']
    # the Horizons extremes over one Mercury year equal the analytic perihelion/aphelion values (hourly sampling, site
    # parallax < 2e-5 AU): within 0.1 %
    assert s['horizons_max_deg'] == pytest.approx(a['max_diam_deg'], rel=1e-3)
    assert s['horizons_min_deg'] == pytest.approx(a['min_diam_deg'], rel=1e-3)
    sizes = [2 * x['sun']['radius_deg'] for x in b['samples'][:b['time']['mercury_year_1_n_samples']]]
    assert min(sizes) >= a['min_diam_deg'] * (1 - 1e-3) and max(sizes) <= a['max_diam_deg'] * (1 + 1e-3)
    assert all(x['sun']['radius_source'] == 'horizons-ang-diam' for x in b['samples'])


def test_horizons_solar_day_and_resonance():
    e = _bundle()['world']['physics_checks']['resonance_from_horizons']
    assert e['orbital_period_days'] == pytest.approx(87.969, abs=0.01)
    assert e['solar_day_days'] == pytest.approx(175.94, abs=0.05)
    assert e['orbit_over_rotation'] == pytest.approx(1.5, abs=1e-3)


def test_horizons_conjunctions_recur_with_synodic_period():
    c = _bundle()['world']['comms']['conjunctions']
    kinds = [m['kind'] for m in c['minima']]
    assert len(kinds) >= 3 and all(a != b for a, b in zip(kinds, kinds[1:]))          # superior/inferior alternate
    sup = [m['t'] for m in c['minima'] if m['kind'] == 'superior']
    assert len(sup) >= 2
    assert (sup[1] - sup[0]) / 86400.0 == pytest.approx(115.88, abs=10.0)          # synodic period, +- eccentricity
    assert any(s['counts_as_outage'] for s in c['spans'])
    assert all(m['delta_au'] > 1.0 for m in c['minima'] if m['kind'] == 'superior')


def test_longitude_sign_and_azimuth_convention_independent():
    s = _bundle()['world']['physics_checks']['subsolar_independent_check']
    assert s['n'] > 600
    assert s['max_sep_deg'] < 0.05                                 # aberration-level agreement
    assert s['wrong_sign_hypothesis_median_sep_deg'] > 5.0          # the alternative is grossly wrong
    assert 'West-longitude positive' in s['target_pole_equ_header']


def test_frame_tie_magnitude():
    f = _bundle()['world']['physics_checks']['frame_tie']
    assert 0.0 < f['geodetic_minus_centric_lat_deg'] < 0.01
    assert f['max_el_correction_deg'] == pytest.approx(f['geodetic_minus_centric_lat_deg'], abs=2e-4)
