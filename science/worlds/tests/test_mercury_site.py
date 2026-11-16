"""Mercury polar site end to end: rule-selected site, reproducible offline rebuild, labels, sections and comms logic."""
import json
from pathlib import Path

import numpy as np
import pytest

from science.worlds.mercury import dem as MD
from science.worlds.mercury import site as S

ROOT = Path(__file__).resolve().parents[3]
BUNDLE = ROOT / 'data' / 'worlds' / 'mercury' / 'mercury_prokofiev_rim_2026-11-14_176d_mast1m.json'


def _have_inputs():
    return all(MD.have(MD.P85, r) for r in (MD.P85_DEM, MD.P85_SLOPE, MD.P85_MAXFLUX, MD.P85_RADAR)) and \
        MD.have(*MD.MLA_V2[::2]) and MD.have(MD.MLA_V1_250[0], MD.MLA_V1_250[1])


@pytest.fixture(scope='module')
def committed():
    if not BUNDLE.exists():
        pytest.skip('Mercury bundle not built')
    return json.loads(BUNDLE.read_text())


@pytest.fixture(scope='module')
def rebuilt(tmp_path_factory):
    if not _have_inputs():
        pytest.skip('Mercury inputs not cached')
    try:
        b, _ = S.build(allow_network=False, out_dir=tmp_path_factory.mktemp('merc'))
    except LookupError as e:
        pytest.skip(f'Horizons responses not cached: {e}')
    return b


def test_site_rule_is_reproducible_and_on_the_rim(committed):
    if not _have_inputs():
        pytest.skip('Mercury inputs not cached')
    s = S.select_site()
    assert (s['lat_deg'], s['lon_deg_east']) == (committed['site']['lat_deg'], committed['site']['lon_deg_east'])
    assert 0.85 * 56 <= s['distance_from_crater_centre_km'] <= 1.15 * 56 and s['slope_deg'] < 15.0


def test_offline_rebuild_reproduces_committed_numbers(committed, rebuilt):
    for k in ('sun_center_visible_pct', 'earth_center_visible_pct', 'sun_and_earth_center_visible_pct',
              'longest_sun_center_hidden_h'):
        assert rebuilt['metrics'][k] == committed['metrics'][k], k
    assert rebuilt['skyline']['elevation_deg'] == committed['skyline']['elevation_deg']
    assert rebuilt['world']['comms']['dte_available_pct_solar_day'] == committed['world']['comms']['dte_available_pct_solar_day']


def test_labels_provenance_and_sections(committed):
    b = committed
    assert b['schema'] == 'polaris-science-results-v1' and b['world']['name'] == 'mercury'
    assert b['validation_status']['overall'] == 'SOURCE-BASED UNVALIDATED'
    assert b['world']['comms']['label'] == 'ENGINEERING ASSUMPTION'
    secs = b['world']['sections']
    for k in ('decision_card', 'cube', 'sensitivity'):
        assert secs[k]['status'] == 'not available for this world' and secs[k]['reason']
    for r in secs['requirements_check']:
        assert 'ENGINEERING ASSUMPTION' in r['threshold_source']['label'] and r['nominal']['source_path'].startswith('metrics')
    lay = b['skyline']['dem_layers']
    assert [l['role'] for l in lay] == ['near', 'far'] and all(l['file_sha256'] and l['source_url'] for l in lay)
    assert all(len(h['sha256']) == 64 for h in b['provenance']['horizons_raw'])
    assert b['skyline']['n_truncated'] == 0 and b['skyline']['curvature_limit']['n_range_limited_world'] == 0
    assert b['time']['n_samples'] == 176 * 24 + 1 and b['time']['mercury_year_1_n_samples'] == 88 * 24 + 1


def test_terrain_vs_flat_control_and_dte_logic(committed):
    b = committed; f = b['world']['flat_horizon_control']; m = b['metrics']
    assert m['sun_center_visible_pct'] <= f['sun_center_visible_pct_solar_day']     # terrain can only hide
    assert m['earth_center_visible_pct'] <= f['earth_center_visible_pct_solar_day']
    ev = np.array([s['earth']['center_visible'] for s in b['samples']])
    c = b['world']['comms']
    assert c['dte_available_pct_solar_day'] <= round(100 * ev.mean(), 3)
    sweep = b['world']['mast_sweep']
    sun = [x['solar_day']['sun_center_visible_pct_hourly_samples'] for x in sweep]
    assert sun == sorted(sun)                                                        # higher mast never sees less
    assert sweep[0]['solar_day']['sun_center_visible_pct_hourly_samples'] == m['sun_center_visible_pct']


def test_ice_layer_recorded(committed):
    ice = committed['world']['ice']
    assert ice['radar_bright_threshold'] == 0.1 and 'ASSUMPTION' in ice['threshold_source']
    assert ice['nearest_radar_bright_pixel'] is not None
    assert 'not available' in ice['global_layer']


def test_moon_bundle_schema_compatibility(committed):
    jsonschema = pytest.importorskip('jsonschema')
    schema = json.loads((ROOT / 'schemas' / 'science-results-v1.schema.json').read_text())
    errs = list(jsonschema.Draft202012Validator(schema).iter_errors(committed))
    # science-results-v1 pins datum.radius_m to the Moon (const 1737400): that is the ONLY violation allowed. A
    # world-aware schema (v2) is an open item for the schema owner.
    assert [(list(e.path), e.validator) for e in errs] == [(['datum', 'radius_m'], 'const')], \
        [f'{list(e.path)}: {e.message[:120]}' for e in errs[:5]]
