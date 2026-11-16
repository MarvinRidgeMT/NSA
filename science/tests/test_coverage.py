"""A3 Coverage Gauge tests. Synthetic DEMs are SYNTHETIC TEST FIXTURES (not lunar data)."""
import json
import unittest
from pathlib import Path

import numpy as np

from science import frames
from science.attribution import attribute
from science.coverage import for_bundle
from science.crossings import horizon_at
from science.dem import ArrayDEM
from science.skyline import compute_skyline

ROOT = Path(__file__).resolve().parents[2]
LAT, LON = -89.4632, -137.49


def _dem(half, step, r0, r1, height, name):
    """Flat 0 m DEM with a plateau at local az 80-100 deg, range r0..r1 (None = no plateau)."""
    x0, y0 = frames.stereo_forward(LAT, LON)
    xs = np.arange(x0 - half, x0 + half + step, step)
    ys = np.arange(y0 + half, y0 - half - step, -step)
    X, Y = np.meshgrid(xs, ys)
    e = frames.local_east_in_grid(LON); n = frames.local_north_in_grid(LON)
    dx, dy = X - x0, Y - y0
    az = np.degrees(np.arctan2(dx * e[0] + dy * e[1], dx * n[0] + dy * n[1])) % 360.0
    r = np.hypot(dx, dy)
    Z = np.zeros_like(X)
    if r0 is not None:
        Z = np.where((az >= 80) & (az <= 100) & (r >= r0) & (r <= r1), height, 0.0)
    return ArrayDEM(Z, x_left=xs[0] - step / 2, y_top=ys[0] + step / 2, step=step, name=name)


def _bundle(near, far):
    sky = compute_skyline(LAT, LON, 0.0, 2.0, near=near, far=far, bins=720, max_range_m=5500.0,
                          step_m=5.0, with_gap=True)
    samples = []
    for k in range(720):  # Sun 0.3 deg above the skyline everywhere -> every hour is critical
        az = k * 0.5
        H, _, f = horizon_at(sky, az)
        He, _, fe = horizon_at(sky, 270.0)
        samples.append({'sun': {'az_deg': az, 'el_deg': H + 0.3, 'margin_deg': 0.3, 'center_visible': True, 'horizon_flag': f},
                        'earth': {'az_deg': 270.0, 'el_deg': 5.0, 'margin_deg': 5.0 - He, 'center_visible': True,
                                  'horizon_flag': fe}})
    att = attribute(sky, samples, 1.0, 0.0, join_m=160.0)
    return {'time': {'step_h': 1}, 'samples': samples, 'derived': {'attribution': att}}, sky


class CoverageGauge(unittest.TestCase):
    def test_ridge_outside_tile_gives_zero_coverage_there(self):
        near = _dem(1000.0, 5.0, None, None, 0, 'SYNTHETIC near tile (flat)')
        far = _dem(6000.0, 80.0, 3000.0, 3300.0, 120.0, 'SYNTHETIC far DEM (plateau 3 km)')
        b, sky = _bundle(near, far)
        att = b['derived']['attribution']
        i90 = 180
        self.assertEqual(att['per_bin']['source'][i90], 'far_80m')
        # restrict the samples to the plateau's azimuths: every critical hour is controlled from outside the tile
        b['samples'] = [s for s in b['samples'] if 82 <= s['sun']['az_deg'] <= 98]
        c = for_bundle(b)
        self.assertGreater(c['n_critical_h'], 0)
        self.assertEqual(c['covered_frac'], 0.0)
        self.assertTrue(c['uncovered_ridges'])

    def test_ridge_inside_tile_gives_full_coverage_there(self):
        near = _dem(1000.0, 5.0, 400.0, 500.0, 15.0, 'SYNTHETIC near tile (plateau 400 m)')
        far = _dem(6000.0, 80.0, None, None, 0, 'SYNTHETIC far DEM (flat)')
        b, sky = _bundle(near, far)
        b['samples'] = [s for s in b['samples'] if 82 <= s['sun']['az_deg'] <= 98]
        c = for_bundle(b)
        self.assertEqual(c['covered_frac'], 1.0)
        self.assertEqual(c['uncovered_ridges'], [])

    def test_threshold_excludes_safe_hours(self):
        near = _dem(1000.0, 5.0, None, None, 0, 'SYNTHETIC near tile (flat)')
        far = _dem(6000.0, 80.0, None, None, 0, 'SYNTHETIC far DEM (flat)')
        b, _ = _bundle(near, far)
        self.assertEqual(for_bundle(b, critical_threshold_deg=0.2)['n_critical_h'], 0)
        self.assertIsNone(for_bundle(b, critical_threshold_deg=0.2)['covered_frac'])


class RealBundleCoverage(unittest.TestCase):
    def test_roi_bundles_carry_coverage(self):
        for p in sorted((ROOT / 'data/bundles').glob('site0*_roi*_mast*.json')):
            b = json.loads(p.read_text())
            c = b.get('derived', {}).get('coverage')
            if c is None:
                self.skipTest('coverage not yet written')
            with self.subTest(p.name):
                self.assertEqual(c, for_bundle(b, c['critical_threshold_deg']))   # reproducible from the bundle
                self.assertEqual(c['label'], 'SOURCE-BASED UNVALIDATED')


if __name__ == '__main__':
    unittest.main()
