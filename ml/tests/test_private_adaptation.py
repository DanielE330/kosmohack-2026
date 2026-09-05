from __future__ import annotations

import sys
import unittest
from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from private_adaptation import (  # noqa: E402
    CALIBRATION_FEATURES,
    GLOBAL_CALIBRATION_FEATURES,
    apply_nonlinear_global_calibration,
    apply_polygon_calibration,
    apply_global_calibration,
    make_disjoint_calibration_masks,
)


class PrivateAdaptationTests(unittest.TestCase):
    def test_calibration_masks_are_disjoint_and_never_include_real_gap(self):
        frame = pd.DataFrame(
            {
                "anon_polygon_id": ["A"] * 11,
                "date": pd.date_range("2024-04-01", periods=11, freq="D"),
                "primary_ndvi": [float(i) / 10 for i in range(10)] + [np.nan],
                "is_synthetic_gap": [False] * 10 + [True],
            }
        )
        masks = make_disjoint_calibration_masks(
            frame, n_masks=4, rate=0.2, seed=42
        )
        stacked = np.vstack(masks)
        self.assertTrue((stacked.sum(axis=0) <= 1).all())
        self.assertFalse(stacked[:, -1].any())
        self.assertEqual(int(stacked.sum()), 8)

    def test_local_correction_is_shrunk_by_calibration_count(self):
        calibration = pd.DataFrame(
            {
                "anon_polygon_id": ["A"] * 20,
                "target_true": np.linspace(0.24, 0.62, 20),
            }
        )
        actual = pd.DataFrame({"anon_polygon_id": ["A"], "v3_prediction": [0.5]})
        for column in CALIBRATION_FEATURES:
            calibration[column] = 0.0
            actual[column] = 0.0
        calibration["v3_prediction"] = calibration["target_true"] - 0.04
        actual["v3_prediction"] = 0.5

        adapted, diagnostics = apply_polygon_calibration(actual, calibration)
        self.assertAlmostEqual(float(adapted.loc[0, "local_blend_weight"]), 0.05)
        self.assertAlmostEqual(float(adapted.loc[0, "v4_prediction"]), 0.502)
        self.assertEqual(diagnostics.loc[0, "status"], "adapted")

    def test_global_correction_uses_crop_specific_conservative_weight(self):
        calibration = pd.DataFrame(
            {
                "anon_polygon_id": ["A"] * 20,
                "crop_type": ["зерновые"] * 20,
                "target_true": np.linspace(0.24, 0.62, 20),
            }
        )
        actual = pd.DataFrame(
            {
                "anon_polygon_id": ["A"],
                "crop_type": ["зерновые"],
                "v4_prediction": [0.50],
            }
        )
        for column in GLOBAL_CALIBRATION_FEATURES:
            calibration[column] = 0.0
            actual[column] = 0.0
        calibration["v3_prediction"] = calibration["target_true"] - 0.04
        actual["v3_prediction"] = 0.50

        result = apply_global_calibration(actual, calibration)
        self.assertAlmostEqual(float(result.loc[0, "global_correction_raw"]), 0.04)
        self.assertAlmostEqual(float(result.loc[0, "global_blend_weight"]), 0.65)
        self.assertAlmostEqual(float(result.loc[0, "v5_prediction"]), 0.526)

    def test_nonlinear_correction_blends_ridge_and_tree(self):
        calibration = pd.DataFrame(
            {
                "anon_polygon_id": ["A"] * 20,
                "crop_type": ["зерновые"] * 20,
                "target_true": np.linspace(0.24, 0.62, 20),
            }
        )
        actual = pd.DataFrame(
            {
                "anon_polygon_id": ["A"],
                "crop_type": ["зерновые"],
                "v4_prediction": [0.50],
            }
        )
        for column in GLOBAL_CALIBRATION_FEATURES:
            calibration[column] = 0.0
            actual[column] = 0.0
        calibration["v3_prediction"] = calibration["target_true"] - 0.04
        actual["v3_prediction"] = 0.50

        result = apply_nonlinear_global_calibration(actual, calibration)
        self.assertAlmostEqual(float(result.loc[0, "global_correction_raw"]), 0.04)
        self.assertAlmostEqual(float(result.loc[0, "tree_correction_raw"]), 0.04)
        self.assertAlmostEqual(float(result.loc[0, "v7_prediction"]), 0.536)


if __name__ == "__main__":
    unittest.main()
