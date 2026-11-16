"""Mercury data conventions: datums, pixel/orientation conventions and provenance of the downloaded products.
Skipped (with the reason) when a product is not cached. Numbers measured 2026-11-16 are in docs/v2/PHASE_6_WORLDS_RESULTS.md."""
import json
import os
from pathlib import Path

import numpy as np
import pytest

from science import dem as demmod
from science.worlds import get_world
from science.worlds.mercury import dem as MD
from science.worlds.mercury import products as PR

MERC = get_world('mercury')


def _need(pid, rel):
    if not MD.have(pid, rel):
        pytest.skip(f'{pid}/{rel} not cached (python -m science.worlds.mercury.fetch)')


def test_catalogue_is_public_and_sized():
    plan = PR.download_plan()
    total = sum(p.total_bytes for p in plan)
    assert total < 30e9                                                       # cap from the task
    for p in plan:
        assert p.product_id.startswith('mercury_') and p.licence and p.acknowledgement and p.landing_page
        for f in p.files:
            assert f.url.startswith('https://') and 'login' not in f.url and 'token' not in f.url
    assert PR.get('mercury_radar_bright_global').status == 'not-downloaded'


def test_manifest_lines_for_downloaded_files():
    man = Path(MD.products_root()).parent / 'manifest.jsonl'
    if not man.exists():
        pytest.skip('no manifest')
    entries = {}
    for line in man.read_text().splitlines():
        e = json.loads(line)
        if e['product_id'].startswith('mercury_'):
            entries[e['local_path']] = e
    if not entries:
        pytest.skip('no Mercury product downloaded yet')
    for rel, e in entries.items():
        assert len(e['sha256']) == 64 and e['licence'] and e['acknowledgement'] and e['url'].startswith('https://')
        p = Path(MD.products_root()).parent.parent / rel
        if p.exists():
            assert p.stat().st_size == int(e['bytes'])


def test_mla_label_datums_are_read_not_assumed():
    _need(*MD.MLA_V2[::2])
    lab = MD.parse_pds3_label(open(MD.path(MD.MLA_V2[0], MD.MLA_V2[2]), encoding='latin-1').read())
    assert lab['OFFSET'] == 2_440_000.0 and lab['A_AXIS_RADIUS'] == 2439.4 and lab['SCALING_FACTOR'] == 0.5
    g = MD.mla_v2(window=(150_000, 160_000, -90_000, -80_000))
    assert g.meta['datum_shift_applied_m'] == 600.0 and g.proj.Rp == 2_439_400.0
    assert g.dem.bounds[0] <= 150_000 and g.dem.bounds[2] >= 160_000
    full = MD.mla_v2()
    assert full.dem.bounds == (-640_000.0, -640_000.0, 640_000.0, 640_000.0)    # symmetric 5120 x 250 m grid


def test_mla_v1_and_v2_agree_after_rereferencing():
    """v1 (OFFSET 2 439 400 m) and v2 (OFFSET 2 440 000 m) share most data: after radius -> height above 2 439.4 km
    their median difference must be ~0, not 600 m."""
    _need(*MD.MLA_V2[::2]); _need(MD.MLA_V1_250[0], MD.MLA_V1_250[2])
    v2 = MD.mla_v2()
    v1 = MD.read_mla_polar(MD.path(*MD.MLA_V1_250[:2]), MD.path(MD.MLA_V1_250[0], MD.MLA_V1_250[2]), 'v1',
                           (-640_000, 640_000, -640_000, 640_000))
    rng = np.random.default_rng(0)
    lat = rng.uniform(76, 89.5, 20000); lon = rng.uniform(-180, 180, 20000)
    d = v2.dem.sample(*v2.proj.forward(lat, lon)) - v1.dem.sample(*v1.proj.forward(lat, lon))
    d = d[np.isfinite(d)]
    assert abs(np.median(d)) < 20.0
    assert np.percentile(np.abs(d), 90) < 150.0


def test_pgda85_height_reference_and_orientation_against_mla():
    """PGDA 85 heights (km) on a 2 440 km reference (hypothesis in dem.P85_HEIGHT_REFERENCE_M) agree with MLA v2 to a
    median of a few metres (a 2 439.4 km reference would give ~600 m), and the two grids correlate only with the
    documented orientations (flipping the MLA y axis destroys the correlation)."""
    _need(MD.P85, MD.P85_DEM); _need(*MD.MLA_V2[::2])
    p = MD.prokofiev('dem'); v2 = MD.mla_v2()
    b0 = p.dem.bounds
    X, Y = np.meshgrid(np.linspace(b0[0] + 1500, b0[2] - 1500, 200), np.linspace(b0[1] + 1500, b0[3] - 1500, 200))
    la, lo = p.proj.inverse(X, Y)
    hp = p.dem.sample(*p.proj.forward(la, lo)); xv, yv = v2.proj.forward(la, lo); hv = v2.dem.sample(xv, yv)
    d = hp - hv
    assert abs(np.nanmedian(d)) < 15.0
    assert np.corrcoef(hp.ravel(), hv.ravel())[0, 1] > 0.995
    assert np.corrcoef(hp.ravel(), np.nan_to_num(v2.dem.sample(xv, -yv)).ravel())[0, 1] < 0.6
    # co-registration residual: the best grid shift is ~1 MLA pixel (recorded as a product member, not corrected)
    best = min((float(np.nanstd(p.dem.sample(*p.proj.forward(la, lo)) * 0 + p.dem.sample(X + dx, Y + dy) - hv)), dx, dy)
               for dx in range(-500, 501, 100) for dy in range(-500, 501, 100))
    assert np.hypot(best[1], best[2]) <= 300.0


def test_usgs_dem_is_on_the_2439p4_sphere_and_relief_bound_holds():
    rel = 'Mercury_Messenger_USGS_DEM_Global_665m_v2.tif'
    _need('mercury_usgs_dem_665m_v2', rel); _need(*MD.MLA_V2[::2])
    import rasterio
    with rasterio.open(MD.path('mercury_usgs_dem_665m_v2', rel)) as ds:
        crs = ds.crs.to_dict(); T = ds.transform; A = ds.read(1).astype(float); sc = ds.scales[0]
    assert crs['proj'] == 'eqc' and crs['R'] == 2_439_400.0 and crs['lon_0'] == 180 and sc == 0.5
    A[A == -32768] = np.nan; A *= sc
    U = demmod.ArrayDEM(A, T.c, T.f, T.a, 'usgs')
    rng = np.random.default_rng(1); lat = rng.uniform(76, 84, 20000); lon = rng.uniform(0, 360, 20000)
    hu = U.sample(2_439_400.0 * np.radians(lon % 360 - 180), 2_439_400.0 * np.radians(lat))
    v2 = MD.mla_v2(); hv = v2.dem.sample(*v2.proj.forward(lat, lon))
    d = hu - hv; m = np.isfinite(d)
    assert abs(np.median(d[m])) < 60.0                      # measured +18 m: same reference sphere (not +-600 m)
    assert np.corrcoef(hu[m], hv[m])[0, 1] > 0.9
    assert np.nanmax(A) < MERC.relief_max_m and np.nanmin(v2.dem.Z) > MERC.relief_min_m and np.nanmin(A) > MERC.relief_min_m


def test_pgda85_posted_cube_is_truncated_so_zip_layers_are_used():
    rel = 'Barker_Prokofiev_stack_125mpp.cub'
    _need(MD.P85, rel)
    raw = open(MD.path(MD.P85, rel), 'rb').read(70000).decode('latin-1')
    import re
    ns, nl, nb = (int(re.search(rf'^\s*{k}\s*=\s*(\d+)', raw, re.M).group(1)) for k in ('Samples', 'Lines', 'Bands'))
    start = int(re.search(r'StartByte\s*=\s*(\d+)', raw).group(1))
    need = start - 1 + ns * nl * nb * 4
    assert os.path.getsize(MD.path(MD.P85, rel)) < need          # 55.5 MB on disk vs 95.3 MB required by its label
    for rel in (MD.P85_DEM, MD.P85_SLOPE, MD.P85_MAXFLUX, MD.P85_RADAR):
        _need(MD.P85, rel)


def test_radar_layer_is_north_polar_and_georeferenced():
    _need(MD.P85, MD.P85_RADAR)
    g = MD.prokofiev('radar')
    assert g.proj.pole == 'north' and abs(g.proj.Rp - 2_439_700.0) < 1e-6
    lat_edge, _ = g.proj.inverse(g.dem.bounds[2], 0.0)
    assert 79.5 < lat_edge < 81.0                                 # covers the cap poleward of ~80 N
    assert 0.3 < np.isfinite(g.dem.Z).mean() < 0.7
    assert np.nanmax(g.dem.Z) > 0.1                                # radar-bright pixels exist at the assumed threshold
