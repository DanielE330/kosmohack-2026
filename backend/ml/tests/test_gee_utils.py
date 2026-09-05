from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from webapp import gee_utils  # noqa: E402


class GeoJsonTests(unittest.TestCase):
    def test_accepts_feature(self):
        geometry = gee_utils.normalize_geojson_geometry(
            {
                "type": "Feature",
                "properties": {},
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [[[30, 45], [31, 45], [31, 46], [30, 45]]],
                },
            }
        )
        self.assertEqual(geometry["type"], "Polygon")

    def test_rejects_point(self):
        with self.assertRaisesRegex(ValueError, "Polygon"):
            gee_utils.normalize_geojson_geometry(
                {"type": "Point", "coordinates": [30, 45]}
            )

    def test_rejects_out_of_range_coordinate(self):
        with self.assertRaisesRegex(ValueError, "диапазона"):
            gee_utils.normalize_geojson_geometry(
                {
                    "type": "Polygon",
                    "coordinates": [[[300, 45], [31, 45], [31, 46], [300, 45]]],
                }
            )


class RecordPreparationTests(unittest.TestCase):
    def test_duplicate_tiles_are_averaged_and_sensors_are_merged(self):
        result = gee_utils._collapse_by_date(
            [
                {"date": "2024-06-01", "s2_ndvi": 0.4},
                {"date": "2024-06-01", "s2_ndvi": 0.6},
                {"date": "2024-06-01", "landsat_ndvi": 0.3},
            ]
        )
        self.assertEqual(len(result), 1)
        self.assertAlmostEqual(result[0]["s2_ndvi"], 0.5)
        self.assertAlmostEqual(result[0]["landsat_ndvi"], 0.3)

    def test_prepares_regular_gaps_and_climatology(self):
        records = [
            {"date": "2021-06-01", "s2_ndvi": 0.4, "s2_valid_fraction": 0.9},
            {"date": "2022-06-01", "s2_ndvi": 0.5, "s2_valid_fraction": 0.9},
            {"date": "2023-06-01", "s2_ndvi": 0.6, "s2_valid_fraction": 0.9},
            {"date": "2024-06-01", "s2_ndvi": 0.7, "s2_valid_fraction": 0.9},
        ]
        result = gee_utils.prepare_live_records(
            records,
            "2024-06-01",
            "2024-06-11",
            cadence_days=5,
            climatology_std_floor=0.12,
        )
        by_date = {row["date"]: row for row in result}

        self.assertEqual(set(by_date), {"2024-06-01", "2024-06-06", "2024-06-11"})
        self.assertEqual(by_date["2024-06-01"]["observation_source"], "Sentinel-2")
        self.assertFalse(by_date["2024-06-01"]["is_synthetic_gap"])
        self.assertTrue(by_date["2024-06-06"]["is_synthetic_gap"])
        self.assertEqual(by_date["2024-06-06"]["n_reference_years"], 3)
        self.assertAlmostEqual(by_date["2024-06-06"]["ndvi_climatology_mean"], 0.5)
        self.assertAlmostEqual(by_date["2024-06-06"]["ndvi_climatology_std"], 0.12)

    def test_low_valid_fraction_is_not_used_as_primary(self):
        result = gee_utils.prepare_live_records(
            [
                {
                    "date": "2024-06-01",
                    "s2_ndvi": 0.8,
                    "s2_valid_fraction": 0.01,
                    "landsat_ndvi": 0.4,
                    "landsat_valid_fraction": 0.8,
                }
            ],
            "2024-06-01",
            "2024-06-01",
        )
        self.assertAlmostEqual(result[0]["primary_ndvi"], 0.4)
        self.assertEqual(result[0]["observation_source"], "Landsat")


class DateTests(unittest.TestCase):
    def test_earth_engine_end_date_is_exclusive(self):
        self.assertEqual(
            gee_utils._validate_dates("2024-01-01", "2024-01-02"),
            ("2024-01-01", "2024-01-03"),
        )

    def test_rejects_reversed_range(self):
        with self.assertRaisesRegex(ValueError, "раньше"):
            gee_utils._validate_dates("2024-01-02", "2024-01-01")


if __name__ == "__main__":
    unittest.main()
