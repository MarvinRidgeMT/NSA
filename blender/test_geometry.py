import unittest, math
from polaris_geometry import (MOON_RADIUS_M, cell_id, curvature_drop, direction,
                              elevation, terrain_horizon, trace_visibility,
                              validate_dem)

def dm(n=41):
    vals=[]
    for j in range(n):
        y=(j-n//2)*10
        for i in range(n):
            x=(i-n//2)*10
            vals.append(30.0 if 90<=x<=120 and -40<=y<=40 else 0.0)
    return {'n':n,'spacing':10,'originX':-200,'originY':-200,'values':vals}

class TestVisibility(unittest.TestCase):
    def test_grid(self):
        d=dm();validate_dem(d);self.assertEqual(elevation(d,0,0),0)
    def test_direction(self):
        dx,dy,dz=direction(90,0)
        self.assertAlmostEqual(dx,1);self.assertAlmostEqual(dy,0,places=8)
    def test_ridge_blocks_low_east_sun(self):
        d=dm();o=elevation(d,0,0)+2
        self.assertFalse(trace_visibility(d,0,0,o,90,2,150,5)['visible'])
        self.assertTrue(trace_visibility(d,0,0,o,270,2,150,5)['visible'])
    def test_observer_mast_restores_access(self):
        d=dm()
        self.assertTrue(trace_visibility(d,0,0,60,90,2,150,5)['visible'])
    def test_horizon_angle_ridge(self):
        d=dm()
        result=terrain_horizon(d,0,0,2,90,150,5)
        self.assertGreater(result['angle_deg'],10)
        self.assertIsNotNone(result['critical_cell'])
        self.assertEqual(result['termination'],'requested_radius')
    def test_outside_grid_rejected(self):
        with self.assertRaises(ValueError): elevation(dm(),10000,0)
    def test_exact_curvature_drop_matches_short_range_approximation(self):
        distance=12000
        approximate=distance*distance/(2*MOON_RADIUS_M)
        self.assertAlmostEqual(curvature_drop(distance),approximate,delta=.02)
        self.assertGreater(curvature_drop(distance),0)
    def test_first_hit_reports_source_cell_and_negative_clearance(self):
        d=dm();result=trace_visibility(d,0,0,2,90,2,150,5)
        self.assertFalse(result['visible'])
        self.assertIsNotNone(result['blocking_cell'])
        self.assertLessEqual(result['clearance_m'],0)
        self.assertEqual(result['termination'],'first_hit')
    def test_cell_ids_follow_south_to_north_rows(self):
        d=dm()
        self.assertEqual(cell_id(d,-199,-199),{'row':0,'column':0,'flat_index':0})
        self.assertEqual(cell_id(d,1,1),{'row':20,'column':20,'flat_index':840})

if __name__=='__main__': unittest.main()
