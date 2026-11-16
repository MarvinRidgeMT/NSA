"""Coverage accounting: every point counted once (zone rule), areas add up to the sphere, classes by native res."""
import math
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from globe_fixtures import SP, grid_centres, plane, write_raster  # noqa: E402

from science.terrain import stack as S  # noqa: E402
from tools.globe import coverage as CV  # noqa: E402
from tools.globe import pyramid as PY  # noqa: E402
from tools.globe import pyramid_products as PP  # noqa: E402


def test_counted_areas_tile_the_sphere():
    tot = sum(CV.cell_areas(z).sum() for z in ('sp', 'np', 'eq'))
    assert abs(tot / CV.MOON_AREA - 1) < 2e-4


def test_classes():
    assert list(CV.class_of([5.0, 5.01, 20, 59.2, 79.4, 80, 118, 236.9, 400])) == [0, 1, 1, 3, 3, 3, 4, 5, 6]


def test_mini_coverage(tmp_path):
    l, t, px, n = -20000.0, 20000.0, 80.0, 500
    X, Y = grid_centres(l, t, px, n, n)
    f = write_raster(tmp_path / 'c.tif', plane(X, Y), l, t, px, SP)
    root = tmp_path / 'v2' / 'pyramid'
    PY.build(zones=('sp',), max_level=4, workers=1, root=root, specs=[PP.ProductSpec('c', 5, f, 80.0)],
             log=lambda *a: None)
    s = CV.run(root=root, write=False, log=lambda *a: None)
    # a 40 x 40 km square near the pole (stereographic scale ~1): 1600 km^2 at 40-80 m class
    km2 = s['km2_by_resolution']['40-80 m']
    assert abs(km2 - 1600.0) / 1600.0 < 0.02, km2
    assert abs(sum(s['percent_by_resolution'].values()) + s['percent_no_terrain'] - 100.0) < 1e-6
    assert set(s['percent_by_source_id']) == {'5'}
