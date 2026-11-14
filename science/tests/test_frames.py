"""T1 regression tests: grid<->local ENU rotation and Moon-fixed 3D elevation model.

Bug being fixed: legacy ray code stepped along polar-stereographic GRID
directions (east=sin az, north=cos az) while JPL Horizons azimuths are LOCAL
(clockwise from local north). At the south pole those differ by the site
longitude L.
"""
import math
import os
import unittest

import numpy as np

from science import frames
from science.dem import ArrayDEM
from science.skyline import compute_skyline

SITE01 = (-89.4632, -137.4900)
SITE04 = (-89.7668, -171.8700)


class GridEnuRotation(unittest.TestCase):
    def test_local_north_east_in_grid(self):
        L = SITE01[1]
        n = frames.local_north_in_grid(L)
        e = frames.local_east_in_grid(L)
        self.assertAlmostEqual(n[0], math.sin(math.radians(L)), places=12)
        self.assertAlmostEqual(n[1], math.cos(math.radians(L)), places=12)
        self.assertAlmostEqual(e[0], math.cos(math.radians(L)), places=12)
        self.assertAlmostEqual(e[1], -math.sin(math.radians(L)), places=12)

    def test_rotation_matches_numeric_projection_derivative(self):
        # Moving 1 m north / east on the sphere must move the grid point along the
        # predicted unit vectors (south-polar stereographic, x=rho sinL, y=rho cosL).
        for lat, lon in (SITE01, SITE04):
            # central differences (forward differences carry an O(dlon/2) bias)
            dlat = math.degrees(1.0 / frames.R_MOON_M)
            xs, ys = frames.stereo_forward(lat - dlat, lon)
            xn, yn = frames.stereo_forward(lat + dlat, lon)
            vn = np.array([xn - xs, yn - ys]); vn /= np.linalg.norm(vn)
            np.testing.assert_allclose(vn, frames.local_north_in_grid(lon), atol=1e-6)
            dlon = math.degrees(1.0 / (frames.R_MOON_M * math.cos(math.radians(lat))))
            xw, yw = frames.stereo_forward(lat, lon - dlon)
            xe, ye = frames.stereo_forward(lat, lon + dlon)
            ve = np.array([xe - xw, ye - yw]); ve /= np.linalg.norm(ve)
            np.testing.assert_allclose(ve, frames.local_east_in_grid(lon), atol=1e-6)

    def test_azimuth_conversion_error_equals_longitude(self):
        # The legacy bug's angular error equals L (mod 360, signed).
        for (lat, lon), expected in ((SITE01, -137.49), (SITE04, -171.87)):
            grid_az = frames.local_az_to_grid_az(0.0, lon)  # local north
            err = (grid_az - 0.0 + 180) % 360 - 180
            self.assertAlmostEqual(err, expected, places=9)
            back = frames.grid_az_to_local_az(grid_az, lon)
            self.assertAlmostEqual((back + 180) % 360 - 180, 0.0, places=9)


class MoonFixed3D(unittest.TestCase):
    def test_unit_vector_and_up(self):
        P = frames.moon_fixed(-90.0, 0.0, 0.0)
        np.testing.assert_allclose(P, [0, 0, -frames.R_MOON_M], atol=1e-6)

    def test_elevation_of_point_on_flat_sphere_is_negative_dip(self):
        # A point at h=0 at distance s along the sphere appears below the
        # observer's horizontal by approx s/(2R) radians (observer at h=0).
        lat, lon = SITE01
        s = 50_000.0
        lat2, lon2 = frames.destination(lat, lon, 90.0, s)
        el = frames.elevation_angle_deg(frames.moon_fixed(lat, lon, 0.0),
                                        frames.up_vector(lat, lon),
                                        frames.moon_fixed(lat2, lon2, 0.0))
        self.assertAlmostEqual(el, -math.degrees(s / (2 * frames.R_MOON_M)), places=4)

    def test_destination_heading_is_local_azimuth(self):
        lat, lon = SITE01
        lat2, lon2 = frames.destination(lat, lon, 90.0, 100.0)
        P0 = frames.moon_fixed(lat, lon, 0)
        d = frames.moon_fixed(lat2, lon2, 0) - P0
        e, n, u = frames.enu_basis(lat, lon)
        az = math.degrees(math.atan2(d @ e, d @ n)) % 360
        self.assertAlmostEqual(az, 90.0, places=3)


def _ridge_dem(lat, lon, local_az_deg, dist_m=2000.0, height_m=300.0):
    """Synthetic flat DEM in grid coordinates with a ridge disk placed
    dist_m along LOCAL azimuth local_az_deg from the site. SYNTHETIC TEST FIXTURE."""
    x0, y0 = frames.stereo_forward(lat, lon)
    a = math.radians(local_az_deg)
    e = frames.local_east_in_grid(lon); n = frames.local_north_in_grid(lon)
    rx = x0 + dist_m * (math.sin(a) * e[0] + math.cos(a) * n[0])
    ry = y0 + dist_m * (math.sin(a) * e[1] + math.cos(a) * n[1])
    step = 20.0
    half = 6000.0
    xs = np.arange(x0 - half, x0 + half + step, step)
    ys = np.arange(y0 + half, y0 - half - step, -step)  # north-up raster rows
    X, Y = np.meshgrid(xs, ys)
    Z = np.where((X - rx) ** 2 + (Y - ry) ** 2 < 300.0 ** 2, height_m, 0.0)
    return ArrayDEM(Z, x_left=xs[0] - step / 2, y_top=ys[0] + step / 2, step=step,
                    name='SYNTHETIC ridge test DEM')


class RidgeRegression(unittest.TestCase):
    def test_ridge_due_local_east_blocks_az90_not_270(self):
        lat, lon = SITE01
        dem = _ridge_dem(lat, lon, 90.0)
        sky = compute_skyline(lat, lon, obs_height_m=0.0, mast_m=2.0, near=dem, far=None,
                              bins=720, max_range_m=5500.0, step_m=20.0)
        el = np.array(sky['elevation_deg'], dtype=float)
        i90, i270 = 180, 540  # 0.5 deg bins, bin centre i*0.5
        self.assertGreater(el[i90], 5.0)
        self.assertLess(el[i270], 0.0)

    def test_legacy_grid_ray_would_miss(self):
        # Document the bug: the legacy grid direction for az=90 points elsewhere.
        lat, lon = SITE01
        legacy = np.array([math.sin(math.radians(90)), math.cos(math.radians(90))])
        correct = np.array(frames.local_east_in_grid(lon))
        ang = math.degrees(math.acos(float(np.clip(legacy @ correct, -1, 1))))
        self.assertAlmostEqual(ang, 137.49, places=6)


@unittest.skipIf(os.environ.get('POLARIS_OFFLINE') == '1', 'network disabled')
class CogRoundTrip(unittest.TestCase):
    def test_roundtrip_under_1mm_using_cog_crs(self):
        crs = frames.ldem_crs()
        for lat, lon in (SITE01, SITE04):
            x, y = frames.stereo_forward(lat, lon, crs=crs)
            lat2, lon2 = frames.stereo_inverse(x, y, crs=crs)
            x2, y2 = frames.stereo_forward(lat2, lon2, crs=crs)
            self.assertLess(math.hypot(x2 - x, y2 - y), 1e-3)
            # hand-coded formula agrees with the file CRS to < 1 mm
            xh, yh = frames.stereo_forward(lat, lon)
            self.assertLess(math.hypot(xh - x, yh - y), 1e-3)


if __name__ == '__main__':
    unittest.main()
