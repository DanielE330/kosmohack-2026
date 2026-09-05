"""Быстрые проверки ключевых инвариантов решения."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

import numpy as np
import pandas as pd
from pandas.testing import assert_frame_equal


ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from anomalies import (  # noqa: E402
    add_interpretation,
    add_weather_context,
    detect_anomaly_periods,
    validate_against_reference,
)
from gap_features import build_gap_features  # noqa: E402


class CorePipelineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.train = pd.read_csv(ROOT / "data" / "train_dataset.csv", parse_dates=["date"])

    def test_primary_ndvi_sensor_priority(self) -> None:
        observed = self.train[self.train.primary_ndvi.notna()]
        reconstructed = observed[["s2_ndvi", "landsat_ndvi", "modis_ndvi"]].bfill(
            axis=1
        ).iloc[:, 0]
        self.assertTrue(np.allclose(reconstructed, observed.primary_ndvi))

    def test_query_value_cannot_leak_into_features(self) -> None:
        polygon = self.train[self.train.anon_polygon_id == self.train.anon_polygon_id.iloc[0]]
        polygon = polygon.reset_index(drop=True)
        query_row = int(polygon.index[polygon.primary_ndvi.notna()][20])
        mask = np.zeros(len(polygon), dtype=bool)
        mask[query_row] = True

        original_features = build_gap_features(polygon, mask).features
        changed = polygon.copy()
        changed.loc[query_row, "primary_ndvi"] = 999.0
        changed_features = build_gap_features(changed, mask).features
        assert_frame_equal(original_features, changed_features)

    def test_anomaly_formula_matches_reference(self) -> None:
        metrics = validate_against_reference(self.train)
        self.assertLess(metrics["max_zscore_difference"], 1e-10)
        self.assertEqual(metrics["status_accuracy_on_labeled"], 1.0)

    def test_submission_contract(self) -> None:
        private = pd.read_csv(ROOT / "data" / "private_features.csv")
        submission = pd.read_csv(ROOT / "submission.csv")
        self.assertEqual(len(submission), int(private.is_synthetic_gap.sum()))
        self.assertEqual(
            list(submission.columns),
            ["anon_polygon_id", "date", "primary_ndvi_pred"],
        )
        self.assertFalse(submission.primary_ndvi_pred.isna().any())
        self.assertFalse(submission.duplicated(["anon_polygon_id", "date"]).any())

    def test_reconstructed_points_do_not_anchor_alert_periods(self) -> None:
        frame = pd.DataFrame(
            {
                "anon_polygon_id": ["live"] * 3,
                "date": pd.to_datetime(["2024-06-01", "2024-06-06", "2024-06-11"]),
                "anomaly_status": ["Критическая аномалия"] * 3,
                "value_kind": ["reconstructed", "reconstructed", "measured"],
                "z_score": [-3.0, -2.5, -2.2],
                "anomaly_confidence": [0.4, 0.4, 0.8],
                "anomaly_reason": ["test"] * 3,
            }
        )
        periods = detect_anomaly_periods(frame)
        self.assertEqual(len(periods), 1)
        self.assertEqual(periods.iloc[0]["date_from"], "2024-06-11")
        self.assertEqual(periods.iloc[0]["observations"], 1)

    def test_weather_windows_use_calendar_days(self) -> None:
        frame = pd.DataFrame(
            {
                "anon_polygon_id": ["live", "live"],
                "date": pd.to_datetime(["2024-01-01", "2024-01-20"]),
                "primary_ndvi": [0.4, 0.5],
                "era5_precip_mm": [1.0, 2.0],
                "era5_temp_c": [10.0, 20.0],
            }
        )
        result = add_weather_context(frame)
        self.assertAlmostEqual(result.iloc[1]["precip_14d"], 2.0)
        self.assertAlmostEqual(result.iloc[1]["temp_7d"], 20.0)

    def test_mild_october_weather_is_not_called_heat_stress(self) -> None:
        frame = pd.DataFrame(
            {
                "anon_polygon_id": ["live"],
                "date": pd.to_datetime(["2024-10-20"]),
                "primary_ndvi": [0.15],
                "anomaly_status": ["Критическая аномалия"],
                "value_kind": ["measured"],
                "crop_type": ["зерновые"],
                "n_reference_years": [5],
                "precip_14d": [18.0],
                "temp_7d": [17.0],
                "sensor_spread": [0.03],
            }
        )
        result = add_interpretation(frame)
        self.assertEqual(result.iloc[0]["anomaly_cause"], "unconfirmed")
        self.assertTrue(result.iloc[0]["requires_review"])

    def test_physical_weather_thresholds_produce_drought_and_heat(self) -> None:
        frame = pd.DataFrame(
            {
                "anon_polygon_id": ["live"],
                "date": pd.to_datetime(["2024-07-20"]),
                "primary_ndvi": [0.20],
                "anomaly_status": ["Критическая аномалия"],
                "value_kind": ["measured"],
                "crop_type": ["зерновые"],
                "n_reference_years": [5],
                "precip_14d": [2.0],
                "temp_7d": [29.0],
                "sensor_spread": [0.03],
            }
        )
        result = add_interpretation(frame)
        self.assertEqual(result.iloc[0]["anomaly_cause"], "heat_and_drought")
        self.assertEqual(result.iloc[0]["cause_confidence"], 0.75)

    def test_sensor_conflict_is_reported_before_weather_cause(self) -> None:
        frame = pd.DataFrame(
            {
                "anon_polygon_id": ["live"],
                "date": pd.to_datetime(["2024-07-20"]),
                "primary_ndvi": [0.20],
                "anomaly_status": ["Критическая аномалия"],
                "value_kind": ["measured"],
                "crop_type": ["зерновые"],
                "n_reference_years": [5],
                "precip_14d": [2.0],
                "temp_7d": [29.0],
                "sensor_spread": [0.22],
            }
        )
        result = add_interpretation(frame)
        self.assertEqual(result.iloc[0]["anomaly_cause"], "sensor_conflict")
        self.assertTrue(result.iloc[0]["requires_review"])


if __name__ == "__main__":
    unittest.main()
