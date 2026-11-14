import unittest, math
from polaris_geometry import elevation, validate_dem, direction, trace_visibility, terrain_horizon

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
        self.assertGreater(terrain_horizon(d,0,0,2,90,150,5)['angle_deg'],10)
    def test_outside_grid_rejected(self):
        with self.assertRaises(ValueError): elevation(dm(),10000,0)

if __name__=='__main__': unittest.main()
