"""A1 Ridge of Record tests. Synthetic DEMs are SYNTHETIC TEST FIXTURES (not lunar data)."""
import json
import math
import unittest
from pathlib import Path

import numpy as np

from science import frames
from science.attribution import attribute, cluster
from science.crossings import horizon_at
from science.dem import ArrayDEM
from science.skyline import compute_skyline

ROOT = Path(__file__).resolve().parents[2]
LAT, LON = -89.4632, -137.49
AZ0, AZ1, R0, R1 = 80.0, 100.0, 2000.0, 2300.0


def _plateau_dem(height_m):
    """Flat ground (0 m) with one plateau: local az AZ0..AZ1, range R0..R1 from the site."""
    x0, y0 = frames.stereo_forward(LAT, LON)
    step, half = 20.0, 6000.0
    xs = np.arange(x0 - half, x0 + half + step, step)
    ys = np.arange(y0 + half, y0 - half - step, -step)
    X, Y = np.meshgrid(xs, ys)
    e = frames.local_east_in_grid(LON); n = frames.local_north_in_grid(LON)
    dx, dy = X - x0, Y - y0
    east, north = dx * e[0] + dy * e[1], dx * n[0] + dy * n[1]
    az = np.degrees(np.arctan2(east, north)) % 360.0
    r = np.hypot(dx, dy)
    Z = np.where((az >= AZ0) & (az <= AZ1) & (r >= R0) & (r <= R1), height_m, 0.0)
    return ArrayDEM(Z, x_left=xs[0] - step / 2, y_top=ys[0] + step / 2, step=step, name='SYNTHETIC plateau DEM')


def _samples(sky):
    """Synthetic Sun track: one sample per 0.5 deg of azimuth, el = 0.3 + 0.05*|az-90| deg.
    Earth fixed at az 270, el 5 (always visible)."""
    out = []
    for k in range(720):
        az = k * 0.5
        el = 0.3 + 0.05 * abs(((az - 90 + 180) % 360) - 180)
        H, _, flag = horizon_at(sky, az)
        He, _, fe = horizon_at(sky, 270.0)
        out.append({'sun': {'az_deg': az, 'el_deg': el, 'center_visible': el > H, 'horizon_flag': flag},
                    'earth': {'az_deg': 270.0, 'el_deg': 5.0, 'center_visible': 5.0 > He, 'horizon_flag': fe}})
    return out


def _run(height_m):
    sky = compute_skyline(LAT, LON, 0.0, 2.0, near=_plateau_dem(height_m), bins=720,
                          max_range_m=5500.0, step_m=20.0, with_gap=True)
    return sky, attribute(sky, _samples(sky), step_h=1.0, obs_ground_m=0.0)


class RidgeOfRecord(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.sky20, cls.a20 = _run(20.0)
        cls.sky70, cls.a70 = _run(70.0)

    def test_single_planted_ridge_is_only_ridge_of_record(self):
        rec = [r for r in self.a20['ridges'] if r['of_record']]
        self.assertEqual(len(rec), 1)
        r = rec[0]
        self.assertEqual(r['id'], 'R1')
        self.assertLess(abs(r['az_span_deg'][0] - AZ0), 1.01)
        self.assertLess(abs(r['az_span_deg'][1] - AZ1), 1.01)
        self.assertAlmostEqual(r['dist_km'], R0 / 1000, delta=0.05)
        self.assertAlmostEqual(r['relief_m'], 20.0, delta=0.5)
        self.assertEqual(r['source'], 'near_5m')
        self.assertEqual(r['earth_loss_h'], 0)

    def test_raising_ridge_50m_increases_sun_loss(self):
        r20 = next(r for r in self.a20['ridges'] if r['of_record'])
        r70 = next(r for r in self.a70['ridges'] if r['of_record'])
        self.assertGreater(r20['sun_loss_h'], 0)
        self.assertGreater(r70['sun_loss_h'], r20['sun_loss_h'])

    def test_loss_hours_equal_blocked_samples(self):
        blocked = sum(not s['sun']['center_visible'] for s in _samples(self.sky20))
        self.assertEqual(sum(r['sun_loss_h'] for r in self.a20['ridges']), blocked)

    def test_gap_and_per_bin_shapes(self):
        pb = self.a20['per_bin']
        for k in ('ridge_idx', 'ctrl_idx', 'ctrl_dist_m', 'gap_deg', 'source'):
            self.assertEqual(len(pb[k]), 720)
        i90 = 180
        self.assertGreater(pb['gap_deg'][i90], 0.0)      # plateau edge clearly above anything 2 cells away
        self.assertEqual(self.a20['ridges'][pb['ridge_idx'][i90]]['id'], 'R1')

    def test_cluster_wraps_around_north(self):
        sky = {'bins': 4, 'critical': [{'grid_x_m': 0, 'grid_y_m': 0}, {'grid_x_m': 1000, 'grid_y_m': 0},
                                         {'grid_x_m': 2000, 'grid_y_m': 0}, {'grid_x_m': 0, 'grid_y_m': 50}]}
        runs = cluster(sky, join_m=160.0)
        self.assertEqual(sorted(map(sorted, runs)), [[0, 3], [1], [2]])


class RealBundleAttribution(unittest.TestCase):
    def test_site04_roi3_bundle_lists_ridges(self):
        p = ROOT / 'data/bundles/site04_roi3_2026-11-14_14d_mast1m.json'
        b = json.loads(p.read_text())
        att = b.get('derived', {}).get('attribution')
        if att is None:
            self.skipTest('attribution not yet written to the bundle')
        self.assertEqual(att['label'], 'SOURCE-BASED UNVALIDATED')
        rec = [r for r in att['ridges'] if r['of_record']]
        self.assertTrue(rec)
        blocked = sum(not s['sun']['center_visible'] for s in b['samples'] if s['sun']['horizon_flag'] != 'unknown')
        self.assertEqual(sum(r['sun_loss_h'] for r in att['ridges']), blocked)
        for r in rec:
            self.assertTrue(0 < r['dist_km'] < 280)


if __name__ == '__main__':
    unittest.main()
