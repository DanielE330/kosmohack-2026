"""Nested validation of the global private correction used by submission v5."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from private_adaptation import (  # noqa: E402
    DEFAULT_GLOBAL_BLEND,
    GLOBAL_BLEND_BY_CROP,
    predict_global_residual_correction,
)


INPUT = ROOT / "reports/private_adaptation_oof_predictions.csv"
REPORT = ROOT / "reports/global_private_adaptation_validation.json"
OOF_OUTPUT = ROOT / "reports/global_private_adaptation_oof_predictions.csv"
GRID = np.arange(0.0, 0.81, 0.05)


def rmse(truth, prediction) -> float:
    return float(
        np.sqrt(
            np.mean(
                (np.asarray(truth, dtype=float) - np.asarray(prediction, dtype=float))
                ** 2
            )
        )
    )


def best_global_weight(frame: pd.DataFrame) -> float:
    truth = frame["target_true"].to_numpy(dtype=float)
    v4 = frame["v4_prediction"].to_numpy(dtype=float)
    correction = frame["global_correction_raw"].to_numpy(dtype=float)
    return float(
        min(GRID, key=lambda weight: rmse(truth, v4 + weight * correction))
    )


def main() -> None:
    data = pd.read_csv(INPUT, parse_dates=["date"])
    data["v2_prediction"] = data["base_prediction"]
    data["global_correction_raw"] = 0.0

    # Each seed is evaluated using calibration labels from other seeds only;
    # the same original row_id is explicitly forbidden in calibration.
    for evaluation_seed in sorted(data["synthetic_seed"].unique()):
        evaluation = data["synthetic_seed"].eq(evaluation_seed)
        forbidden_rows = set(data.loc[evaluation, "row_id"])
        calibration = data[
            ~data["synthetic_seed"].eq(evaluation_seed)
            & ~data["row_id"].isin(forbidden_rows)
        ].drop_duplicates(["anon_polygon_id", "row_id"])
        data.loc[evaluation, "global_correction_raw"] = (
            predict_global_residual_correction(
                data.loc[evaluation],
                calibration,
            )
        )

    data["v5_prediction"] = np.clip(
        data["v4_prediction"]
        + data["crop_type"]
        .map(GLOBAL_BLEND_BY_CROP)
        .fillna(DEFAULT_GLOBAL_BLEND)
        .to_numpy(dtype=float)
        * data["global_correction_raw"],
        -1.0,
        1.0,
    )

    # Hyperparameter check: for each outer fold, choose crop weights using only
    # the other polygon folds, then score the untouched fold.
    data["nested_prediction"] = np.nan
    selected_weights = []
    for fold in sorted(data["outer_fold"].unique()):
        training = data[data["outer_fold"].ne(fold)]
        validation = data[data["outer_fold"].eq(fold)]
        fallback_weight = best_global_weight(training)
        for crop_type, indices in validation.groupby("crop_type").groups.items():
            crop_training = training[training["crop_type"].eq(crop_type)]
            weight = (
                best_global_weight(crop_training)
                if len(crop_training) >= 300
                else fallback_weight
            )
            row_indices = np.asarray(list(indices), dtype=int)
            data.loc[row_indices, "nested_prediction"] = np.clip(
                data.loc[row_indices, "v4_prediction"]
                + weight * data.loc[row_indices, "global_correction_raw"],
                -1.0,
                1.0,
            )
            selected_weights.append(
                {
                    "fold": int(fold),
                    "crop_type": str(crop_type),
                    "training_rows": len(crop_training),
                    "validation_rows": len(row_indices),
                    "selected_global_weight": weight,
                }
            )

    if data["nested_prediction"].isna().any():
        raise AssertionError("Не всем OOF-строкам назначен nested prediction")

    folds = []
    for fold, part in data.groupby("outer_fold"):
        folds.append(
            {
                "fold": int(fold),
                "rows": len(part),
                "v4_rmse": rmse(part["target_true"], part["v4_prediction"]),
                "nested_v5_rmse": rmse(
                    part["target_true"], part["nested_prediction"]
                ),
            }
        )
    seeds = []
    for seed, part in data.groupby("synthetic_seed"):
        seeds.append(
            {
                "seed": int(seed),
                "rows": len(part),
                "v4_rmse": rmse(part["target_true"], part["v4_prediction"]),
                "nested_v5_rmse": rmse(
                    part["target_true"], part["nested_prediction"]
                ),
            }
        )
    crops = []
    for crop_type, part in data.groupby("crop_type"):
        crops.append(
            {
                "crop_type": str(crop_type),
                "rows": len(part),
                "v4_rmse": rmse(part["target_true"], part["v4_prediction"]),
                "nested_v5_rmse": rmse(
                    part["target_true"], part["nested_prediction"]
                ),
            }
        )

    v4_rmse = rmse(data["target_true"], data["v4_prediction"])
    nested_rmse = rmse(data["target_true"], data["nested_prediction"])
    fixed_rmse = rmse(data["target_true"], data["v5_prediction"])
    report = {
        "protocol": (
            "global Ridge correction is seed-held-out; crop weights are selected "
            "on four outer GroupKFold folds and evaluated on the fifth"
        ),
        "rows": len(data),
        "v4_oof_rmse": v4_rmse,
        "nested_v5_oof_rmse": nested_rmse,
        "nested_improvement": v4_rmse - nested_rmse,
        "fixed_production_v5_oof_rmse": fixed_rmse,
        "fixed_production_improvement": v4_rmse - fixed_rmse,
        "production_global_blend_by_crop": GLOBAL_BLEND_BY_CROP,
        "folds": folds,
        "seeds": seeds,
        "crops": crops,
        "nested_selected_weights": selected_weights,
    }
    REPORT.write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    data.to_csv(OOF_OUTPUT, index=False, encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    print(f"saved: {REPORT}")
    print(f"saved: {OOF_OUTPUT}")


if __name__ == "__main__":
    main()
