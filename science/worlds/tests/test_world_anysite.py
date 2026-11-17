"""The `world=` hook (T3): science.anysite.solve.solve(world=...) -> science.worlds.anysite for non-Moon worlds; the Moon
path is untouched (science/worlds/tests/test_moon_world.py and science/anysite/tests keep the Moon numbers). Here: the
generic world path reproduces R6's Prokofiev rim bundle (skyline and metrics), offline."""
import json
import os
import unittest

import numpy as np

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))
R6 = os.path.join(ROOT, 'data', 'worlds', 'mercury', 'mercury_prokofiev_rim_2026-11-14_176d_mast1m.json')


class WorldHook(unittest.TestCase):
    def test_moon_world_none_is_default_path(self):
        import inspect
        from science.anysite import solve as S
        src = inspect.getsource(S.solve)
        self.assertIn("str(getattr(world, 'name', world)).lower() != 'moon'", src)
        self.assertIsNone(inspect.signature(S.solve).parameters['world'].default)

    def test_prokofiev_through_world_hook_equals_r6(self):
        if not os.path.exists(R6):
            self.skipTest('R6 bundle missing')
        from science.anysite.solve import solve
        r6 = json.load(open(R6))
        try:
            b = solve(r6['site']['lat_deg'], r6['site']['lon_deg_east'], 1.0, '2026-11-14 00:00', 176, 1, world='mercury',
                      use_cache=False, allow_network=False, out_dir=os.path.join(ROOT, 'data', 'cache', 'anysite', 'test_worlds'))
        except (LookupError, FileNotFoundError) as e:
            self.skipTest(f'Mercury data / Horizons cache not available ({e})')
        a = np.array(b['skyline']['elevation_deg'], float); c = np.array(r6['skyline']['elevation_deg'], float)
        self.assertLessEqual(float(np.nanmax(np.abs(a - c))), 1e-9)
        for k in ('sun_center_visible_pct', 'earth_center_visible_pct', 'longest_sun_center_hidden_h'):
            self.assertEqual(b['metrics'][k], r6['metrics'][k], k)
        self.assertEqual(b['site']['height_m'], r6['site']['height_m'])
        self.assertEqual(b['frame']['horizons_longitude_offset_deg'], 0.0)
        self.assertEqual(b['datum']['radius_m'], 2_439_400.0)


if __name__ == '__main__':
    unittest.main()
