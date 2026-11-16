"""The generic world geometry/skyline equals the Moon code bit for bit with the Moon's radius; the north-polar projection
matches PROJ; the frame-tie rotation is exact."""
import math

import numpy as np
import pytest

from science import dem as demmod
from science import frames
from science.skyline import compute_skyline
from science.worlds import get_world
from science.worlds.geometry import PolarStereo, Sphere
from science.worlds.skyline import Layer, layered_skyline

MOON_S = Sphere(frames.R_MOON_M)
SP = PolarStereo(frames.R_MOON_M, 'south')


def test_sphere_functions_equal_frames():
    lat, lon = -89.3, 47.0
    az = np.linspace(0, 359, 37)[:, None]; s = np.linspace(10, 200_000, 50)[None, :]
    a1 = frames.destination(lat, lon, az, s); a2 = MOON_S.destination(lat, lon, az, s)
    assert np.array_equal(a1[0], a2[0]) and np.array_equal(a1[1], a2[1])
    assert np.array_equal(frames.moon_fixed(lat, lon, 1234.5), MOON_S.body_fixed(lat, lon, 1234.5))
    assert np.array_equal(frames.unit(a1[0], a1[1]), MOON_S.unit(a1[0], a1[1]))
    for f, g in zip(frames.enu_basis(lat, lon), Sphere.enu_basis(lat, lon)):
        assert np.array_equal(f, g)


def test_south_stereo_equals_frames():
    la = np.linspace(-89.99, -80, 30); lo = np.linspace(-180, 179, 30)
    x1, y1 = frames.stereo_forward(la, lo); x2, y2 = SP.forward(la, lo)
    assert np.array_equal(x1, x2) and np.array_equal(y1, y2)
    lat2, lon2 = SP.inverse(x2, y2)
    assert np.allclose(lat2, la, atol=1e-10) and np.allclose(lon2, lo, atol=1e-9)


@pytest.mark.parametrize('pole,lat0', [('north', 90), ('south', -90)])
def test_polar_stereo_matches_proj(pole, lat0):
    from pyproj import CRS, Transformer
    R = 2_439_400.0
    ps = PolarStereo(R, pole)
    crs = CRS.from_proj4(ps.proj4())
    t = Transformer.from_crs(crs.geodetic_crs, crs, always_xy=True)
    sgn = 1 if pole == 'north' else -1
    la = sgn * np.linspace(75.0, 89.99, 25); lo = np.linspace(-179, 179, 25)
    xp, yp = t.transform(lo, la)
    x, y = ps.forward(la, lo)
    assert np.max(np.hypot(x - xp, y - yp)) < 1e-3
    lat2, lon2 = ps.inverse(x, y)
    assert np.allclose(lat2, la, atol=1e-10) and np.allclose(((lon2 - lo + 180) % 360) - 180, 0, atol=1e-9)


def test_north_stereo_orientation():
    # PDS DSMAP_POLAR north: lon 0 points toward -y (down the image), lon 90 E toward +x
    ps = PolarStereo(2_439_400.0, 'north')
    x, y = ps.forward(85.0, 0.0); assert abs(x) < 1e-6 and y < 0
    x, y = ps.forward(85.0, 90.0); assert x > 0 and abs(y) < 1e-6


def _synthetic(seed=3):
    rng = np.random.default_rng(seed)
    x0, y0 = frames.stereo_forward(-89.6, 30.0)
    n = 400; step = 50.0
    xx = (np.arange(n) - n / 2) * step
    X, Y = np.meshgrid(xx, -xx)
    Z = 300 * np.sin(X / 3000.0) * np.cos(Y / 4100.0) + 0.02 * X + rng.normal(0, 3, X.shape)
    near = demmod.ArrayDEM(Z, x0 - n / 2 * step, y0 + n / 2 * step, step, 'near-synth')
    nf = 300; stf = 800.0
    xf = (np.arange(nf) - nf / 2) * stf
    XF, YF = np.meshgrid(xf, -xf)
    ZF = 800 * np.sin(XF / 40_000.0 + 1) * np.cos(YF / 33_000.0) + rng.normal(0, 5, XF.shape)
    ZF[10:20, 140:160] = np.nan                                   # a no-data patch: truncation must agree too
    far = demmod.ArrayDEM(ZF, x0 - nf / 2 * stf, y0 + nf / 2 * stf, stf, 'far-synth')
    return near, far


def test_layered_skyline_equals_moon_code():
    near, far = _synthetic()
    kw = dict(bins=144, max_range_m=110_000.0)
    ref = compute_skyline(-89.6, 30.0, 120.0, 2.0, near=near, far=far, step_m=10.0, near_range_m=9_000.0,
                          far_step_m=800.0, **kw)
    got = layered_skyline(MOON_S, -89.6, 30.0, 120.0, 2.0, [Layer(near, SP.forward), Layer(far, SP.forward, 'far')],
                          step_near_m=10.0, near_cut_m=9_000.0, step_far_m=800.0, beyond_reference=Layer(far, SP.forward), **kw)
    for k in ('elevation_deg', 'status', 'valid_reach_m', 'range_limited', 'n_truncated', 'n_samples_per_bin',
              'beyond_range_max_possible_elev_deg', 'max_range_m', 'near_cut_m'):
        assert got[k] == ref[k], k
    for a, b in zip(got['critical'], ref['critical']):
        assert (a is None) == (b is None)
        if a:
            assert {k: a[k] for k in b} == b
    assert got['flat_baseline'] == ref['flat_baseline']
    assert ref['n_truncated'] > 0                                 # the no-data patch was actually hit


def test_world_skyline_dispatch_moon_is_existing_code():
    near, far = _synthetic(5)
    moon = get_world('moon')
    from science.worlds.skyline import compute_skyline as wsky
    a = wsky(moon, -89.6, 30.0, 120.0, 2.0, near=near, far=far, bins=36, max_range_m=60_000.0)
    b = compute_skyline(-89.6, 30.0, 120.0, 2.0, near=near, far=far, bins=36, max_range_m=60_000.0)
    assert a == b


def test_flat_sphere_dip_mercury():
    """Constant-height DEM on Mercury's sphere: every bin equals the bare-sphere tangent elevation (analytic)."""
    R = 2_439_400.0; Hc, mast = 500.0, 40.0
    ps = PolarStereo(R, 'north'); sph = Sphere(R)
    n = 1500; step = 100.0
    flat = demmod.ArrayDEM(np.full((n, n), Hc), -n / 2 * step, n / 2 * step, step, 'flat')
    sky = layered_skyline(sph, 89.0, 10.0, Hc, mast, [Layer(flat, ps.forward)], bins=36, max_range_m=25_000.0,
                          step_near_m=2.0)                         # tangent point at ~14 km; box reaches > 30 km
    dip = -math.degrees(math.acos((R + Hc) / (R + Hc + mast)))
    assert max(abs(e - dip) for e in sky['elevation_deg']) < 2e-4
    assert sky['n_truncated'] == 0


def test_frame_tie_zero_for_moon_and_bounded_for_mercury():
    moon = get_world('moon'); merc = get_world('mercury')
    az, el, d = moon.horizons_azel_to_sphere([10.0, 200.0], [1.0, -2.0], -89.7, -156.0, 1500.0)
    assert d == 0.0 and list(az) == [10.0, 200.0] and list(el) == [1.0, -2.0]
    az, el, d = merc.horizons_azel_to_sphere(np.arange(0, 360, 10.0), np.zeros(36), 85.8, 62.6, 0.0)
    assert 0.0 < d < 0.01
    # a north/south direction changes elevation by -/+ d; east/west directions are unchanged
    assert el[0] == pytest.approx(-d, abs=1e-9) and el[18] == pytest.approx(d, abs=1e-9)
    assert el[9] == pytest.approx(0.0, abs=1e-9) and az[9] == pytest.approx(90.0, abs=1e-9)


def test_geodetic_latitude_matches_horizons_header():
    """Horizons header for SITE_COORD (cylindrical) -62.6, 178.78491, 2433.43398 km echoed
    'Center geodetic : 297.4, 85.8057964, 1.72065' (2026-11-16)."""
    merc = get_world('mercury')
    p, z = 178.78491, 2433.43398
    r = math.hypot(p, z) * 1000.0; lat_c = math.degrees(math.atan2(z, p))
    phi, h = merc.geodetic_latitude_deg(lat_c, r - merc.radius_m, with_height=True)
    assert phi == pytest.approx(85.8057964, abs=5e-7)
    assert h / 1000.0 == pytest.approx(1.72065, abs=5e-5)


def test_site_coord_strings():
    moon = get_world('moon'); merc = get_world('mercury')
    from science import horizons as H
    p = moon.horizons_params('10', -89.78012, -156.32023, 1234.5678, '2026-11-14 00:00', '2026-11-28 00:00', '1 h')
    assert p == H.build_params('10', -89.78012, -156.32023, 1234.5678, '2026-11-14 00:00', '2026-11-28 00:00', '1 h')
    q = merc.horizons_params('10', 85.8, 62.6, 0.0, '2026-11-14 00:00', '2026-11-15 00:00', '1 h')
    assert q['CENTER'] == "'coord@199'" and q['COORD_TYPE'] == 'CYLINDRICAL'
    lon_s, dxy, dz = q['SITE_COORD'].strip("'").split(',')
    assert float(lon_s) == pytest.approx(-62.6)
    assert math.hypot(float(dxy), float(dz)) == pytest.approx(2439.4, abs=1e-6)
    assert math.degrees(math.atan2(float(dz), float(dxy))) == pytest.approx(85.8, abs=1e-6)
    q2 = merc.horizons_params('10', 85.8, -30.0, 0.0, '2026-11-14 00:00', '2026-11-15 00:00', '1 h')
    assert float(q2['SITE_COORD'].strip("'").split(',')[0]) == pytest.approx(-330.0)   # E-lon 330 entered as -330
