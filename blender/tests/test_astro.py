import json
import math
import unittest

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from v2 import astro as A  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
BUNDLE = ROOT / 'data' / 'bundles' / 'site01_roi6_2026-11-14_14d_mast1m.json'


class Geometry(unittest.TestCase):
    def test_enu_direction_convention(self):
        # azimuth 0 = north (+y), 90 = east (+x), elevation 90 = up
        for az, el, want in ((0, 0, (0, 1, 0)), (90, 0, (1, 0, 0)), (180, 0, (0, -1, 0)), (0, 90, (0, 0, 1))):
            got = A.enu_direction(az, el)
            for g, w in zip(got, want):
                self.assertAlmostEqual(g, w, places=12)

    def test_solar_irradiance_inverse_square(self):
        self.assertAlmostEqual(A.solar_irradiance(1.0), 1361.0)
        self.assertAlmostEqual(A.solar_irradiance(2.0), 1361.0 / 4)

    def test_sun_disc_is_full_diameter(self):
        self.assertAlmostEqual(A.sun_disc_angle_deg(0.2697), 0.5394)

    def test_lambert_phase_limits(self):
        self.assertAlmostEqual(A.lambert_sphere_phase(0.0), 1.0)
        self.assertAlmostEqual(A.lambert_sphere_phase(90.0), 1 / math.pi)
        self.assertAlmostEqual(A.lambert_sphere_phase(180.0), 0.0, places=12)

    def test_earth_phase_full_and_new(self):
        # Sun behind the observer, Earth in front: full Earth (phase 0); Sun beyond the Earth: new Earth (phase 180)
        full = A.earth_phase(180, 0, 1.0, 0, 0, 0.0026)
        self.assertLess(full['phaseAngleDeg'], 0.2)
        self.assertAlmostEqual(full['illuminatedFraction'], 1.0, places=4)
        new = A.earth_phase(0, 0, 1.0, 0, 0, 0.0026)
        self.assertGreater(new['phaseAngleDeg'], 179.9)

    def test_earthshine_full_earth_magnitude(self):
        # full Earth: E_sun p sin^2(rho) with rho = asin(6371/384400): ~0.137 W/m^2 (~13 lux at 93 lm/W)
        rho = math.degrees(math.asin(6371 / 384400))
        e = A.earthshine_irradiance(1.0, 0.0, rho)
        self.assertAlmostEqual(e, 1361 * 0.367 * (6371 / 384400) ** 2, places=9)
        self.assertTrue(0.10 < e < 0.20)


class Samples(unittest.TestCase):
    samples = [{'utc': f'2026-11-14T{h:02d}:00:00.000Z'} for h in range(5)]

    def test_exact_and_half_step(self):
        self.assertEqual(A.pick_sample(self.samples, '2026-11-14T02:00Z'), (2, 0.0))
        k, off = A.pick_sample(self.samples, '2026-11-14T02:20Z')
        self.assertEqual((k, off), (2, 1200.0))

    def test_no_extrapolation(self):
        with self.assertRaises(A.SampleError):
            A.pick_sample(self.samples, '2026-11-14T05:31Z')
        with self.assertRaises(A.SampleError):
            A.pick_sample(self.samples, '2026-11-13T23:00Z')


class StarFrame(unittest.TestCase):
    def test_triad_is_a_rotation(self):
        M = A.triad((0, 0, 1), (1, 0, 0), (0, 1, 0), (0, 0, 1))
        for i in range(3):
            for j in range(3):
                d = sum(M[i][k] * M[j][k] for k in range(3))
                self.assertAlmostEqual(d, 1.0 if i == j else 0.0, places=12)
        v = A.matvec(M, (0, 0, 1))
        for g, w in zip(v, (0, 1, 0)):
            self.assertAlmostEqual(g, w, places=12)

    def test_pole_close_to_iau_constant(self):
        p, a0, d0 = A.moon_pole_icrf(A.parse_utc('2026-11-14T00:00Z'))
        self.assertLess(abs(a0 - 269.9949), 4.2)   # libration terms are a few degrees in alpha0
        self.assertLess(abs(d0 - 66.5392), 1.7)

    @unittest.skipUnless(BUNDLE.exists(), 'bundle not present')
    def test_horizons_sun_matches_iau_pole_and_almanac_sun(self):
        """Independent cross-check: the Sun-to-Moon-pole angle from JPL Horizons az/el (bundle) equals the one from the IAU 2009
        pole + Astronomical Almanac Sun within the Sun's parallax over the Earth-Moon distance (< 0.2 deg)."""
        b = json.loads(BUNDLE.read_text())
        worst = 0.0
        for s in b['samples'][::24]:
            _, chk = A.icrf_to_enu(A.parse_utc(s['utc']), b['site']['lat_deg'], b['site']['lon_deg_east'], s['sun']['az_deg'], s['sun']['el_deg'])
            worst = max(worst, chk['differenceDeg'])
        self.assertLess(worst, 0.2)

    @unittest.skipUnless(BUNDLE.exists(), 'bundle not present')
    def test_earth_phase_follows_the_lunar_calendar(self):
        """Earth seen from the Moon is the complement of the Moon seen from Earth: full Moon (24 Nov 2026) <-> new Earth."""
        b = json.loads(BUNDLE.read_text())
        frac = {}
        for s in b['samples']:
            ph = A.earth_phase(s['sun']['az_deg'], s['sun']['el_deg'], s['sun']['range_au'], s['earth']['az_deg'], s['earth']['el_deg'], s['earth']['range_au'])
            frac[s['utc'][:10]] = ph['illuminatedFraction']
        self.assertGreater(frac['2026-11-14'], 0.7)
        self.assertLess(min(frac.values()), 0.05)
        self.assertEqual(min(frac, key=frac.get), '2026-11-24')


if __name__ == '__main__':
    unittest.main()
