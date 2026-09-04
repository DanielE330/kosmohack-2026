"""Seed-held-out and nested GroupKFold validation for submission v7."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from private_adaptation import (  # noqa: E402
    DEFAULT_NONLINEAR_BLEND,
    NONLINEAR_BLEND_BY_CROP,
    predict_tree_residual_correction,
)


INPUT = ROOT / "reports/global_private_adaptation_oof_predictions.csv"
REPORT = ROOT / "reports/tree_private_adaptation_validation.json"
OOF_OUTPUT = ROOT / "reports/tree_private_adaptation_oof_predictions.csv"
GRID = np.arange(0.0, 0.81, 0.05)


def rmse(frame: pd.DataFrame, prediction: str) -> float:
    return float(
        np.sqrt(np.mean((frame["target_true"] - frame[prediction]) ** 2))
    )


def choose_weights(frame: pd.DataFrame) -> tuple[float, float]:
    truth = frame["target_true"].to_numpy(dtype=float)
    v4 = frame["v4_prediction"].to_numpy(dtype=float)
    ridge = frame["global_correction_raw"].to_numpy(dtype=float)
    tree = frame["tree_correction_raw"].to_numpy(dtype=float)
    best = (float("inf"), 0.0, 0.0)
    for ridge_weight in GRID:
        for tree_weight in GRID:
            prediction = v4 + ridge_weight * ridge + tree_weight * tree
            score = float(np.sqrt(np.mean((truth - prediction) ** 2)))
            if score < best[0]:
                best = (score, float(ridge_weight), float(tree_weight))
    return best[1], best[2]


def main() -> None:
    data = pd.read_csv(INPUT, parse_dates=["date"])
    data["v2_prediction"] = data["base_prediction"]
    data["tree_correction_raw"] = 0.0

    for evaluation_seed in sorted(data["synthetic_seed"].unique()):
        evaluation = data["synthetic_seed"].eq(evaluation_seed)
        forbidden_rows = set(data.loc[evaluation, "row_id"])
        calibration = data[
            ~data["synthetic_seed"].eq(evaluation_seed)
            & ~data["row_id"].isin(forbidden_rows)
        ].drop_duplicates(["anon_polygon_id", "row_id"])
        data.loc[evaluation, "tree_correction_raw"] = (
            predict_tree_residual_correction(data.loc[evaluation], calibration)
        )

    weights = data["crop_type"].map(NONLINEAR_BLEND_BY_CROP).apply(
        lambda value: value
        if isinstance(value, tuple)
        else DEFAULT_NONLINEAR_BLEND
    )
    data["ridge_weight"] = weights.map(lambda value: value[0])
    data["tree_weight"] = weights.map(lambda value: value[1])
    data["v7_prediction"] = np.clip(
        data["v4_prediction"]
        + data["ridge_weight"] * data["global_correction_raw"]
        + data["tree_weight"] * data["tree_correction_raw"],
        -1.0,
        1.0,
    )

    data["nested_prediction"] = np.nan
    selected_weights = []
    for fold in sorted(data["outer_fold"].unique()):
        training = data[data["outer_fold"].ne(fold)]
        validation = data[data["outer_fold"].eq(fold)]
        fallback = choose_weights(training)
        for crop_type, indices in validation.groupby("crop_type").groups.items():
            crop_training = training[training["crop_type"].eq(crop_type)]
            ridge_weight, tree_weight = (
                choose_weights(crop_training)
                if len(crop_training) >= 300
                else fallback
            )
            rows = np.asarray(list(indices), dtype=int)
            data.loc[rows, "nested_prediction"] = np.clip(
                data.loc[rows, "v4_prediction"]
                + ridge_weight * data.loc[rows, "global_correction_raw"]
                + tree_weight * data.loc[rows, "tree_correction_raw"],
                -1.0,
                1.0,
            )
            selected_weights.append(
                {
                    "fold": int(fold),
                    "crop_type": str(crop_type),
                    "training_rows": len(crop_training),
                    "validation_rows": len(rows),
                    "ridge_weight": ridge_weight,
                    "tree_weight": tree_weight,
                }
            )

    def breakdown(column: str) -> list[dict]:
        result = []
        for value, part in data.groupby(column):
            result.append(
                {
                    column: int(value) if column != "crop_type" else str(value),
                    "rows": len(part),
                    "v5_rmse": rmse(part, "v5_prediction"),
                    "nested_v7_rmse": rmse(part, "nested_prediction"),
                }
            )
        return result

    v5_score = rmse(data, "v5_prediction")
    nested_score = rmse(data, "nested_prediction")
    fixed_score = rmse(data, "v7_prediction")
    report = {
        "protocol": (
            "ExtraTrees residuals are seed-held-out and same-row forbidden; "
            "Ridge/ExtraTrees weights are selected on four polygon folds"
        ),
        "rows": len(data),
        "v5_oof_rmse": v5_score,
        "nested_v7_oof_rmse": nested_score,
        "nested_improvement": v5_score - nested_score,
        "fixed_v7_oof_rmse": fixed_score,
        "fixed_improvement": v5_score - fixed_score,
        "production_blend_by_crop": NONLINEAR_BLEND_BY_CROP,
        "folds": breakdown("outer_fold"),
        "seeds": breakdown("synthetic_seed"),
        "crops": breakdown("crop_type"),
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
