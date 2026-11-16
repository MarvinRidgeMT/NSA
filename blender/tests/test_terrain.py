import math
import sys
import unittest
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from v2 import terrain as T  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
COMMITTED = ROOT / 'app' / 'data' / 'polaris-source-site01-2026-11-14-v2.json'
NEAR = ROOT / 'data' / 'cache' / 'site01_roi6_p78_p78.npy'


def flat_level(n=257, step=10.0, h=0.0, cx=-10000.0, cy=-12000.0, name='flat'):
    return T.Level(name=name, h=np.full((n, n), h), x0=cx - (n - 1) * step / 2, y0=cy - (n - 1) * step / 2, step=step)


class Frames(unittest.TestCase):
    def test_stereo_roundtrip_and_science_formula(self):
        for lat, lon in ((-89.47409, -137.3813), (-89.78012, -156.32023), (-85.0, 40.0)):
            x, y = T.stereo_forward(lat, lon)
            la, lo = T.stereo_inverse(np.array(x), np.array(y))
            self.assertAlmostEqual(math.degrees(float(la)), lat, places=9)
            self.assertAlmostEqual(math.degrees(float(lo)), lon, places=9)
            rho = 2 * T.R_MOON_M * math.tan(math.pi / 4 + math.radians(lat) / 2)
            self.assertAlmostEqual(x, rho * math.sin(math.radians(lon)), places=6)

    def test_enu_origin_axes_and_curvature(self):
        lat, lon = -89.47409, -137.3813
        F = T.EnuFrame(lat, lon, 1948.29)
        x, y = T.stereo_forward(lat, lon)
        p = F.from_grid(np.array([x]), np.array([y]), np.array([1948.29]))[0]
        self.assertLess(np.abs(p).max(), 1e-6)
        # 1 km toward local north along the grid: the north unit vector at L is (sin L, cos L) in grid
        L = math.radians(lon)
        q = F.from_grid(np.array([x + 1000 * math.sin(L)]), np.array([y + 1000 * math.cos(L)]), np.array([1948.29]))[0]
        # 1 km on the reference-sphere projection is (R+h)/R km on the ground at height h (stereographic scale ~1 here)
        self.assertAlmostEqual(q[1], 1000.0 * (T.R_MOON_M + 1948.29) / T.R_MOON_M, delta=0.05)
        self.assertLess(abs(q[0]), 0.5)
        # sphere drop at distance d: ~ d^2 / 2R
        d = 100_000.0
        r = F.from_grid(np.array([x + d * math.sin(L)]), np.array([y + d * math.cos(L)]), np.array([1948.29]))[0]
        self.assertAlmostEqual(r[2], -d * d / (2 * (T.R_MOON_M + 1948.29)), delta=0.02 * d * d / (2 * T.R_MOON_M))


class Tiles(unittest.TestCase):
    def view(self, fwd=(0, 1, 0)):
        return T.View(pos=(0, 0, 2), fwd=fwd, half_h=math.radians(20), half_v=math.radians(12), pixel_rad=math.radians(40) / 512,
                      sun_dir=(1, 0, 0.03))

    def test_lod_coarsens_with_distance_and_never_beats_native(self):
        lv = flat_level()
        F = T.EnuFrame(*np.degrees(T.stereo_inverse(np.array(-10000.0), np.array(-12000.0))).tolist(), 0.0)
        tiles, rep = T.plan_tiles([lv], F, self.view(), tile_cells=16, budget=10**9)
        self.assertTrue(tiles)
        for t in tiles:
            if t['upsample'] > 1:     # bilinear densification only right next to the observer
                self.assertLessEqual(t['distM'], 150.0)
                self.assertAlmostEqual(t['spacingM'], lv.step / t['upsample'])
            else:
                self.assertGreaterEqual(t['spacingM'], lv.step)
            self.assertEqual(t['decim'] & (t['decim'] - 1), 0)
        self.assertTrue(any(t['upsample'] > 1 for t in tiles))
        near = min((t for t in tiles if t['upsample'] == 1), key=lambda t: t['distM'])
        far = max(tiles, key=lambda t: t['distM'])
        self.assertLessEqual(near['spacingM'], far['spacingM'])

    def test_tiles_behind_and_away_from_the_sun_are_dropped(self):
        lv = flat_level(n=513, step=20.0)
        F = T.EnuFrame(*np.degrees(T.stereo_inverse(np.array(-10000.0), np.array(-12000.0))).tolist(), 0.0)
        tiles, rep = T.plan_tiles([lv], F, self.view(), tile_cells=32, budget=10**9, near_keep_m=200)
        roles = {t['role'] for t in tiles}
        self.assertIn('view', roles)
        self.assertIn('shadow-caster', roles)
        total = ((513 - 1) // 32) ** 2
        self.assertLess(len(tiles), total)

    def test_budget_raises_k(self):
        lv = flat_level(n=513, step=5.0)
        F = T.EnuFrame(*np.degrees(T.stereo_inverse(np.array(-10000.0), np.array(-12000.0))).tolist(), 0.0)
        _, loose = T.plan_tiles([lv], F, self.view(), tile_cells=32, budget=10**9)
        _, tight = T.plan_tiles([lv], F, self.view(), tile_cells=32, budget=loose['vertexEstimate'] // 4)
        self.assertGreater(tight['k'], loose['k'])
        self.assertLess(tight['vertexEstimate'], loose['vertexEstimate'])

    def test_finer_level_cut_and_nan_never_filled(self):
        fine = flat_level(n=101, step=5.0, name='fine')
        coarse = flat_level(n=101, step=40.0, name='coarse')
        coarse.h[50, 50] = np.nan
        F = T.EnuFrame(*np.degrees(T.stereo_inverse(np.array(-10000.0), np.array(-12000.0))).tolist(), 0.0)
        t = {'level': 1, 'i0': 40, 'i1': 60, 'j0': 40, 'j1': 60, 'decim': 1}
        V, Fc, dropped = T.tile_mesh(coarse, t, F, [fine.box()], skirt=False)
        self.assertGreater(dropped, 0)
        # no face may use the NaN node (index of node (50, 50) in the 21 x 21 tile)
        bad = (50 - 40) * 21 + (50 - 40)
        self.assertFalse(np.any(Fc == bad))
        # no face centre inside the fine box (inset one coarse cell)
        b = fine.box()
        self.assertTrue(len(Fc) > 0)

    def test_skirt_vertices_are_separate(self):
        lv = flat_level(n=17, step=10.0)
        F = T.EnuFrame(*np.degrees(T.stereo_inverse(np.array(-10000.0), np.array(-12000.0))).tolist(), 0.0)
        t = {'level': 0, 'i0': 0, 'i1': 16, 'j0': 0, 'j1': 16, 'decim': 1}
        V0, F0, _ = T.tile_mesh(lv, t, F, skirt=False)
        tu = dict(t, upsample=4)
        Vu, Fu, _ = T.tile_mesh(lv, tu, F, skirt=False)
        self.assertEqual(len(Vu), (16 * 4 + 1) ** 2)
        V1, F1, _ = T.tile_mesh(lv, t, F, skirt=True)
        n0 = len(V0)
        skirt_faces = F1[len(F0):]
        self.assertTrue(len(skirt_faces) > 0)
        self.assertTrue(np.all(skirt_faces >= n0), 'skirt faces must not share surface vertices (smooth normals)')


class StackAdapter(unittest.TestCase):
    def test_arraydem_conversion_matches_science_sampler(self):
        """S3's ZoneDEM is an ArrayDEM subclass: the adapter must keep the pixel-edge convention."""
        try:
            sys.path.insert(0, str(ROOT))
            from science.dem import ArrayDEM
        except Exception as e:  # pragma: no cover
            self.skipTest(f'science.dem not importable ({type(e).__name__})')
        rng = np.random.default_rng(5)
        Z = rng.normal(1500, 30, size=(60, 80))
        dem = ArrayDEM(Z, x_left=-12000.0, y_top=-9000.0, step=5.0, name='synthetic')
        lv = T.level_from_arraydem(dem, 'stack test')
        for _ in range(100):
            x = rng.uniform(-12000 + 5, -12000 + 80 * 5 - 5)
            y = rng.uniform(-9000 - 60 * 5 + 5, -9000 - 5)
            self.assertAlmostEqual(T.sample_bilinear(lv, x, y), float(dem.sample(np.array([x]), np.array([y]))[0]), places=8)

    def test_non_polar_window_refused(self):
        class Fake:
            proj, Z, step, x_left, y_top = 'local-stere', np.zeros((2, 2)), 1.0, 0.0, 0.0
        with self.assertRaises(ValueError):
            T.level_from_arraydem(Fake(), 'x')

    def test_stack_reports_why_when_absent(self):
        lv, why = T.stack_levels(-89.5, -137.0)
        if lv is None:
            self.assertTrue(why)


@unittest.skipUnless(COMMITTED.exists(), 'committed bundle missing')
class CommittedLevel(unittest.TestCase):
    def test_committed_crop_loads_in_absolute_grid(self):
        lv = T.load_bundle_v2_level(COMMITTED, 'connecting')
        self.assertEqual(lv.h.shape, (401, 401))
        self.assertEqual(lv.step, 80.0)
        x, y = T.stereo_forward(-89.4632, -137.49)
        h = T.sample_bilinear(lv, x, y)
        self.assertTrue(1000 < h < 3000, h)


@unittest.skipUnless(NEAR.exists(), 'solver DEM cache not present')
class SolverCache(unittest.TestCase):
    def test_pixel_centre_convention_matches_science_dem(self):
        """Regression (found by skyline_check): cache x_left/y_top are pixel EDGES. Our bilinear sample must equal the
        solver's science.dem.ArrayDEM.sample at arbitrary points."""
        import json
        try:
            sys.path.insert(0, str(ROOT))
            from science.dem import ArrayDEM
        except Exception as e:  # pragma: no cover
            self.skipTest(f'science.dem not importable ({type(e).__name__})')
        meta = json.loads(NEAR.with_suffix('.json').read_text())
        Z = np.load(NEAR)
        dem = ArrayDEM(Z, x_left=meta['x_left'], y_top=meta['y_top'], step=meta['step'], name='near')
        lv = T.load_cache_level(NEAR, 'near', hash_file=False)
        rng = np.random.default_rng(3)
        for _ in range(200):
            x = rng.uniform(meta['x_left'] + 20, meta['x_left'] + Z.shape[1] * meta['step'] - 20)
            y = rng.uniform(meta['y_top'] - Z.shape[0] * meta['step'] + 20, meta['y_top'] - 20)
            self.assertAlmostEqual(T.sample_bilinear(lv, x, y), float(dem.sample(np.array([x]), np.array([y]))[0]), places=6)

    def test_site_height_matches_bundle(self):
        import json
        b = json.loads((ROOT / 'data' / 'bundles' / 'site01_roi6_2026-11-14_14d_mast1m.json').read_text())
        lv = T.load_cache_level(NEAR, 'near', hash_file=False)
        h = T.sample_bilinear(lv, b['site']['grid_x_m'], b['site']['grid_y_m'])
        self.assertAlmostEqual(h, b['site']['height_m'], delta=0.002)


if __name__ == '__main__':
    unittest.main()
