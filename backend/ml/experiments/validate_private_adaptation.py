"""Leakage-safe seed-holdout check of per-polygon Ridge calibration."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.impute import SimpleImputer
from sklearn.linear_model import Ridge
from sklearn.model_selection import GroupKFold
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from config import DATE_COL, SYNTHETIC_MASK_RATE, SYNTHETIC_SEEDS, TRAIN_PATH  # noqa: E402
from global_model import build_training_samples  # noqa: E402
from private_adaptation import LOCAL_HISTORY_FEATURES  # noqa: E402


REPORTS = ROOT / "reports"
OUTPUT = REPORTS / "private_adaptation_validation.json"
OOF_OUTPUT = REPORTS / "private_adaptation_oof_predictions.csv"
KEY = ["synthetic_seed", "row_id"]
FEATURES = [
    "ensemble_prediction",
    "base_prediction",
    "reweighted_prediction",
    "global_prediction",
    "wheat_prediction",
    "extra_trees_prediction",
    "baseline",
    "baseline_mean",
    "baseline_linear",
    "baseline_climatology",
    "year",
    "doy_sin",
    "doy_cos",
    *LOCAL_HISTORY_FEATURES,
]
CONTEXT_FEATURES = [
    "target_days_prev1",
    "target_days_next1",
    "target_span_days",
]


def rmse(y_true, prediction) -> float:
    return float(np.sqrt(np.mean((np.asarray(y_true) - np.asarray(prediction)) ** 2)))


def main() -> None:
    data = pd.read_csv(REPORTS / "reweighted_hgb_oof_predictions.csv", parse_dates=["date"])
    wheat = pd.read_csv(REPORTS / "wheat_oof_predictions.csv")[
        KEY + ["global_prediction", "wheat_prediction"]
    ]
    extra = pd.read_csv(REPORTS / "extra_trees_oof_predictions.csv")[
        KEY + ["extra_trees_prediction"]
    ]
    data = data.merge(wheat, on=KEY, validate="one_to_one").merge(
        extra, on=KEY, validate="one_to_one"
    )
    data["wheat_prediction"] = data["wheat_prediction"].fillna(
        data["global_prediction"]
    )
    data["year"] = data["date"].dt.year
    doy = data["date"].dt.dayofyear
    data["doy_sin"] = np.sin(2 * np.pi * doy / 365.25)
    data["doy_cos"] = np.cos(2 * np.pi * doy / 365.25)

    train = pd.read_csv(TRAIN_PATH, parse_dates=[DATE_COL])
    feature_matrix, _, _, feature_meta = build_training_samples(
        train,
        seeds=SYNTHETIC_SEEDS,
        mask_rate=SYNTHETIC_MASK_RATE,
    )
    if not np.array_equal(feature_meta[KEY].to_numpy(), data[KEY].to_numpy()):
        raise ValueError("Порядок OOF и восстановленных feature rows не совпадает")
    for column in [*LOCAL_HISTORY_FEATURES, *CONTEXT_FEATURES]:
        data[column] = feature_matrix[column].to_numpy(dtype=float)

    truth = data["target_true"].to_numpy(dtype=float)
    base = data["ensemble_prediction"].to_numpy(dtype=float)
    correction = np.zeros(len(data), dtype=float)
    calibration_n = np.zeros(len(data), dtype=int)

    # For an evaluation seed, calibration comes only from other seeds and rows
    # that are not evaluation targets.  Duplicate row_ids are removed.
    for evaluation_seed in sorted(data["synthetic_seed"].unique()):
        evaluation = data["synthetic_seed"].eq(evaluation_seed)
        forbidden_rows = set(data.loc[evaluation, "row_id"])
        calibration = data[
            ~data["synthetic_seed"].eq(evaluation_seed)
            & ~data["row_id"].isin(forbidden_rows)
        ].drop_duplicates(["anon_polygon_id", "row_id"])

        for polygon_id, indices in data[evaluation].groupby("anon_polygon_id").groups.items():
            indices = np.asarray(list(indices), dtype=int)
            local = calibration[calibration["anon_polygon_id"].eq(polygon_id)]
            model = make_pipeline(
                SimpleImputer(strategy="median", keep_empty_features=True),
                StandardScaler(),
                Ridge(alpha=1.0),
            )
            model.fit(
                local[FEATURES],
                local["target_true"] - local["ensemble_prediction"],
            )
            correction[indices] = np.clip(
                model.predict(data.loc[indices, FEATURES]), -0.10, 0.10
            )
            calibration_n[indices] = len(local)

    blend = np.minimum(0.33, 0.0025 * calibration_n)
    prediction = np.clip(base + blend * correction, -1.0, 1.0)

    outer_fold = np.full(len(data), -1, dtype=int)
    for fold, (_, validation_idx) in enumerate(
        GroupKFold(5).split(data, groups=data["anon_polygon_id"])
    ):
        outer_fold[validation_idx] = fold

    folds = []
    for fold in range(5):
        selected = outer_fold == fold
        folds.append(
            {
                "fold": fold,
                "rows": int(selected.sum()),
                "v3_rmse": rmse(truth[selected], base[selected]),
                "adapted_rmse": rmse(truth[selected], prediction[selected]),
            }
        )
    seeds = []
    for seed in sorted(data["synthetic_seed"].unique()):
        selected = data["synthetic_seed"].eq(seed).to_numpy()
        seeds.append(
            {
                "seed": int(seed),
                "rows": int(selected.sum()),
                "v3_rmse": rmse(truth[selected], base[selected]),
                "adapted_rmse": rmse(truth[selected], prediction[selected]),
            }
        )
    crops = []
    for crop_type, indices in data.groupby("crop_type").groups.items():
        selected = np.zeros(len(data), dtype=bool)
        selected[np.asarray(list(indices), dtype=int)] = True
        crops.append(
            {
                "crop_type": str(crop_type),
                "rows": int(selected.sum()),
                "v3_rmse": rmse(truth[selected], base[selected]),
                "adapted_rmse": rmse(truth[selected], prediction[selected]),
            }
        )

    report = {
        "protocol": "evaluation seed held out; same row_id forbidden in calibration",
        "rows": len(data),
        "v3_oof_rmse": rmse(truth, base),
        "adapted_oof_rmse": rmse(truth, prediction),
        "improvement": rmse(truth, base) - rmse(truth, prediction),
        "ridge_alpha": 1.0,
        "max_local_blend": 0.33,
        "max_abs_correction": 0.10,
        "folds": folds,
        "seeds": seeds,
        "crops": crops,
    }
    export_columns = list(
        dict.fromkeys(
            [
            "anon_polygon_id",
            "date",
            "crop_type",
            "synthetic_seed",
            "row_id",
            "target_true",
            *FEATURES,
            *CONTEXT_FEATURES,
            ]
        )
    )
    oof_output = data[export_columns].copy()
    oof_output = oof_output.rename(columns={"ensemble_prediction": "v3_prediction"})
    oof_output["local_correction_raw"] = correction
    oof_output["calibration_rows"] = calibration_n
    oof_output["local_blend_weight"] = blend
    oof_output["v4_prediction"] = prediction
    oof_output["outer_fold"] = outer_fold
    oof_output.to_csv(OOF_OUTPUT, index=False, encoding="utf-8")
    OUTPUT.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    print(f"saved: {OUTPUT}")
    print(f"saved: {OOF_OUTPUT}")


if __name__ == "__main__":
    main()
