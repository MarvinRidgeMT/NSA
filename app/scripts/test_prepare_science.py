import math
import tempfile
import unittest
from pathlib import Path

import numpy as np
import rasterio
from rasterio.transform import from_origin

import prepare_science as pipeline


HORIZONS_SAMPLE = """API VERSION: 1.3
Center geodetic : 222.51, -89.4632, 0.0 {E-lon(deg),Lat(deg),Alt(km)}
Center pole/equ : MEAN_ME (high precision) {East-longitude positive}
Atmos refraction: NO (AIRLESS)
 Date__(UT)__HR:MN:SS, , ,Azi_(a-app), Elev_(a-app),
$$SOE
 2026-Nov-14 14:00:00,*, , 256.984524, 1.435750,
 2026-Nov-14 15:00:00,*, , 256.476841, 1.431105,
$$EOE
"""


class ProjectionTests(unittest.TestCase):
    def test_known_projected_reference_points_and_round_trip(self):
        for site_id in pipeline.SITES:
            result = pipeline.projection_validation(site_id)
            self.assertEqual(result["status"], "PASS", result)
            self.assertLess(result["projectedErrorMeters"], 2)
            self.assertLess(abs(result["roundTripErrorDegrees"]["longitude"]), 1e-10)

    def test_east_positive_longitude_changes_easting_sign(self):
        west_x, _ = pipeline.xy_from_latlon(-89, -45)
        east_x, _ = pipeline.xy_from_latlon(-89, 45)
        self.assertLess(west_x, 0)
        self.assertGreater(east_x, 0)
        self.assertAlmostEqual(abs(west_x), abs(east_x), places=8)


class HorizonsParserTests(unittest.TestCase):
    def test_header_driven_airless_apparent_parser(self):
        rows = pipeline.parse_csv_response(HORIZONS_SAMPLE)
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["time"], "2026-11-14T14:00:00Z")
        self.assertAlmostEqual(rows[0]["az"], 256.984524)
        self.assertAlmostEqual(rows[0]["el"], 1.435750)

    def test_response_metadata_checks_frame_site_and_conventions(self):
        validation = pipeline.validate_horizons_response(HORIZONS_SAMPLE, "connecting")
        self.assertEqual(validation["status"], "PASS", validation)
        self.assertEqual(validation["apiVersion"], "1.3")

    def test_parser_rejects_ambiguous_numeric_columns(self):
        broken = HORIZONS_SAMPLE.replace("Azi_(a-app)", "mystery")
        with self.assertRaisesRegex(ValueError, "declare Date/Azimuth/Elevation"):
            pipeline.parse_csv_response(broken)


class RasterContractTests(unittest.TestCase):
    def test_source_rows_are_flipped_to_south_to_north(self):
        site_x, site_y = pipeline.xy_from_latlon(*pipeline.SITES["connecting"][:2])
        source = np.array([
            [40, 41, 42, 43, 44],
            [30, 31, 32, 33, 34],
            [20, 21, 22, 23, 24],
            [10, 11, 12, 13, 14],
            [0, 1, 2, 3, 4],
        ], dtype="float32")
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "orientation.tif"
            transform = from_origin(site_x - 12.5, site_y + 12.5, 5, 5)
            with rasterio.open(
                path,
                "w",
                driver="GTiff",
                width=5,
                height=5,
                count=1,
                dtype="float32",
                crs="+proj=stere +lat_0=-90 +lon_0=0 +R=1737400 +units=m +no_defs",
                transform=transform,
            ) as dataset:
                dataset.write(source, 1)
            crop = pipeline.read_raster_crop(path, "connecting", 5, "test")
        values = np.array(crop["values"]).reshape(5, 5)
        self.assertEqual(values[0, 0], 0)
        self.assertEqual(values[-1, 0], 40)
        self.assertEqual(crop["rowOrder"], "south-to-north after explicit source flip")
        self.assertTrue(math.isfinite(crop["validCoverageRadiusM"]))


if __name__ == "__main__":
    unittest.main()
