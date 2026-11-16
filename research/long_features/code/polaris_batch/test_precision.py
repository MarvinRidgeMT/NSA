import json
import tempfile
import unittest
from pathlib import Path

import numpy as np
import rasterio
from rasterio.crs import CRS
from rasterio.transform import from_origin

from . import core


ROOT = Path(__file__).resolve().parents[4]


class Float64HeightRegression(unittest.TestCase):
    def test_float32_raster_is_promoted_before_lunar_radius_addition(self):
        value = np.float32(1738.98)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "height.tif"
            with rasterio.open(
                path,
                "w",
                driver="GTiff",
                height=2,
                width=2,
                count=1,
                dtype="float32",
                crs=CRS.from_proj4("+proj=stere +lat_0=-90 +lon_0=0 +R=1737400 +units=m"),
                transform=from_origin(-5, 5, 5, 5),
            ) as dataset:
                dataset.write(np.full((1, 2, 2), value, dtype=np.float32))

            dem = core.Dem.open(path)
            radius_plus_height = core.R_MOON + dem.z

        self.assertEqual(dem.z.dtype, np.dtype(np.float64))
        self.assertEqual(radius_plus_height.dtype, np.dtype(np.float64))
        self.assertEqual(radius_plus_height[0, 0], core.R_MOON + float(value))

    def test_repo_site04_anchor_remains_94_36_percent(self):
        bundle = json.loads(
            (ROOT / "data" / "bundles" / "site04_roi3_2026-11-14_14d_mast1m.json").read_text()
        )
        value = bundle["metrics"]["sun_center_visible_pct_hourly_samples"]
        self.assertAlmostEqual(value, 94.36, delta=0.01)
        self.assertEqual(value, 94.362)


if __name__ == "__main__":
    unittest.main()
