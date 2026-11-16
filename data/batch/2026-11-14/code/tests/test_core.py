import math

import numpy as np
import pyproj

from polaris_batch import core


def test_destination_distance_and_bearing():
    lon0, lat0 = -137.3813, -89.47409
    lon, lat = core.destination(lon0, lat0, np.array([0.0, 90.0, 180.0, 270.0]), np.array([1000.0, 50000.0]))
    g = pyproj.Geod(a=core.R_MOON, b=core.R_MOON)
    for i, az in enumerate([0, 90, 180, 270]):
        for j, d in enumerate([1000.0, 50000.0]):
            fwd, _, dist = g.inv(lon0, lat0, lon[i, j], lat[i, j])
            assert abs(dist - d) < 1e-3 * d
            assert abs(((fwd - az + 180) % 360) - 180) < 1e-6
    # local north points away from the south pole: latitude increases
    assert lat[0, 0] > lat0 and lat[2, 0] < lat0


def test_elevation_angle_curvature():
    e = core.elevation_angle_deg(0.0, np.array([0.0]), np.array([10000.0]))[0]
    assert abs(e - (-math.degrees(10000 / (2 * core.R_MOON)))) < 1e-4
    e = core.elevation_angle_deg(0.0, np.array([100.0]), np.array([1000.0]))[0]
    assert abs(e - math.degrees(math.atan(100 / 1000))) < 0.05


def test_disc_fraction():
    f = core.disc_fraction_above(np.array([1.0, 0.0, -1.0, 0.5]), 0.0, 1.0)
    assert np.allclose(f[:3], [1.0, 0.5, 0.0])
    assert 0.5 < f[3] < 1.0


def test_horizon_interp_wraps():
    az = (np.arange(4) + 0.5) * 90
    hz = core.Horizon(az, np.array([0.0, 1.0, 2.0, 3.0]), az, np.ones(4, bool), 0.0)
    assert np.isclose(hz.at(np.array([45.0]))[0], 0.0)
    assert np.isclose(hz.at(np.array([0.0]))[0], 1.5)
    assert np.isclose(hz.at(np.array([90.0]))[0], 0.5)


def test_grid_azimuth_relation():
    crs = pyproj.CRS.from_proj4(f"+proj=stere +lat_0=-90 +lat_ts=-90 +lon_0=0 +R={core.R_MOON} +units=m")
    t = pyproj.Transformer.from_crs(core.LONLAT, crs, always_xy=True)
    L = -137.3813
    lon, lat = core.destination(L, -89.47, np.array([0.0]), np.array([1.0, 100.0]))
    x, y = t.transform(lon[0], lat[0])
    grid_az = math.degrees(math.atan2(x[1] - x[0], y[1] - y[0])) % 360
    assert abs(((grid_az - L % 360) + 180) % 360 - 180) < 0.01


def test_transfer_identity_and_rotation():
    az = np.array([10.0, 200.0]); el = np.array([1.5, -0.5])
    a2, e2 = core.transfer_azel(az, el, -137.0, -89.4, -137.0, -89.4)
    assert np.allclose(a2, az) and np.allclose(e2, el)
    a3, _ = core.transfer_azel(az, el, -137.0, -89.4, -136.0, -89.4)
    d = ((a3 - az + 180) % 360) - 180
    assert np.all(np.abs(np.abs(d) - 1.0) < 0.05)


def test_fine_near_step_distances():
    d = core.ray_distances(5.0, 25000.0, 80.0, 280000.0, near_fine_step=1.0, near_fine_m=1000.0)
    assert d[0] == 1.0 and np.all(np.diff(d) > 0)
    assert np.allclose(np.diff(d[d < 1000.0]), 1.0)
    assert np.allclose(np.diff(d[(d >= 1000.0) & (d < 25000.0)]), 5.0)
    legacy = core.ray_distances(5.0, 25000.0, 80.0, 280000.0)
    assert legacy[0] == 5.0
