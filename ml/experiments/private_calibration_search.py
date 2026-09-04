"""Проверка test-time calibration на видимых точках private_features."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import joblib
import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from config import DATE_COL, ID_COL, MODEL_PATH, TEST_PATH, TRAIN_PATH  # noqa: E402
from extra_trees_model import predict_private_gaps_extra_trees  # noqa: E402
from gap_features import make_synthetic_mask  # noqa: E402
from global_model import rmse  # noqa: E402
from wheat_model import predict_private_gaps_ensemble  # noqa: E402


WHEAT_MODEL_PATH = ROOT / "models/wheat_gap_model.joblib"
EXTRA_MODEL_PATH = ROOT / "models/extra_trees_gap_model.joblib"
OUTPUT_PATH = ROOT / "reports/private_calibration_search.json"
CALIBRATION_ROWS_PATH = ROOT / "reports/private_calibration_rows.csv"
SEEDS = (311, 577, 911)
MASK_RATE = 0.12


def predict_v2(
    private: pd.DataFrame,
    reference: pd.DataFrame,
    global_bundle: dict,
    wheat_bundle: dict,
    extra_bundle: dict,
) -> pd.DataFrame:
    base = predict_private_gaps_ensemble(
        private,
        global_bundle,
        wheat_bundle,
        reference=reference,
        prediction_col="base_prediction",
    )
    extra = predict_private_gaps_extra_trees(
        private,
        extra_bundle,
        reference=reference,
        prediction_col="extra_prediction",
    )
    result = base.merge(
        extra,
        on=[ID_COL, DATE_COL],
        how="inner",
        validate="one_to_one",
    )
    blend = float(extra_bundle["blend_weight"])
    result["prediction"] = (
        (1.0 - blend) * result["base_prediction"]
        + blend * result["extra_prediction"]
    )
    result["prediction"] = np.clip(result["prediction"], -1.0, 1.0)
    return result[[ID_COL, DATE_COL, "prediction"]]


def build_calibration_rows(
    private: pd.DataFrame,
    reference: pd.DataFrame,
    global_bundle: dict,
    wheat_bundle: dict,
    extra_bundle: dict,
) -> pd.DataFrame:
    source = private.copy().reset_index(names="row_id")
    parts = []
    for seed in SEEDS:
        mask = make_synthetic_mask(source, rate=MASK_RATE, seed=seed)
        masked = source.drop(columns="row_id").copy()
        masked["is_synthetic_gap"] = mask.to_numpy()
        prediction = predict_v2(
            masked, reference, global_bundle, wheat_bundle, extra_bundle
        )
        truth = source.loc[
            mask,
            ["row_id", ID_COL, DATE_COL, "crop_type", "primary_ndvi"],
        ].copy()
        truth[DATE_COL] = pd.to_datetime(truth[DATE_COL]).dt.strftime("%Y-%m-%d")
        part = truth.merge(
            prediction,
            on=[ID_COL, DATE_COL],
            how="inner",
            validate="one_to_one",
        )
        part["calibration_seed"] = seed
        part["month"] = pd.to_datetime(part[DATE_COL]).dt.month
        part["error"] = part["prediction"] - part["primary_ndvi"]
        parts.append(part)
        print(f"seed={seed}: {len(part):,} контрольных строк")
    return pd.concat(parts, ignore_index=True)


def fit_effects(
    rows: pd.DataFrame,
    mode: str,
    lambda_polygon: float,
    lambda_crop_month: float,
) -> dict:
    global_bias = float(rows["error"].mean())
    polygon_effects: dict[str, float] = {}
    crop_month_effects: dict[tuple[str, int], float] = {}

    residual = rows["error"] - global_bias
    if mode in {"polygon", "polygon_crop_month"}:
        stats = rows.assign(_residual=residual).groupby(ID_COL)["_residual"].agg(
            ["mean", "count"]
        )
        polygon_effects = (
            stats["mean"] * stats["count"] / (stats["count"] + lambda_polygon)
        ).to_dict()
        residual = residual - rows[ID_COL].map(polygon_effects).fillna(0.0)

    if mode in {"crop_month", "polygon_crop_month"}:
        keys = ["crop_type", "month"]
        stats = rows.assign(_residual=residual).groupby(keys)["_residual"].agg(
            ["mean", "count"]
        )
        values = stats["mean"] * stats["count"] / (
            stats["count"] + lambda_crop_month
        )
        crop_month_effects = values.to_dict()

    return {
        "global_bias": global_bias,
        "polygon_effects": polygon_effects,
        "crop_month_effects": crop_month_effects,
    }


def corrections(rows: pd.DataFrame, effects: dict, mode: str) -> np.ndarray:
    correction = np.full(len(rows), effects["global_bias"], dtype=float)
    if mode in {"polygon", "polygon_crop_month"}:
        correction += (
            rows[ID_COL].map(effects["polygon_effects"]).fillna(0.0).to_numpy()
        )
    if mode in {"crop_month", "polygon_crop_month"}:
        correction += np.array(
            [
                effects["crop_month_effects"].get((crop, int(month)), 0.0)
                for crop, month in rows[["crop_type", "month"]].itertuples(
                    index=False, name=None
                )
            ]
        )
    return correction


def cross_validate_calibration(rows: pd.DataFrame) -> tuple[dict, np.ndarray]:
    configs = []
    for mode in ("global", "polygon", "crop_month", "polygon_crop_month"):
        polygon_lambdas = (10.0, 30.0, 60.0) if "polygon" in mode else (30.0,)
        cm_lambdas = (20.0, 60.0, 120.0) if "crop_month" in mode else (60.0,)
        for lambda_polygon in polygon_lambdas:
            for lambda_crop_month in cm_lambdas:
                for strength in (0.25, 0.5, 0.75, 1.0):
                    configs.append(
                        (mode, lambda_polygon, lambda_crop_month, strength)
                    )

    results = []
    for mode, lambda_polygon, lambda_crop_month, strength in configs:
        cv_prediction = np.full(len(rows), np.nan)
        fold_metrics = []
        for seed in SEEDS:
            val_mask = rows["calibration_seed"].eq(seed).to_numpy()
            val_row_ids = set(rows.loc[val_mask, "row_id"])
            train_mask = ~val_mask & ~rows["row_id"].isin(val_row_ids).to_numpy()
            train_rows = rows.loc[train_mask]
            val_rows = rows.loc[val_mask]
            effects = fit_effects(
                train_rows, mode, lambda_polygon, lambda_crop_month
            )
            corr = corrections(val_rows, effects, mode)
            pred = val_rows["prediction"].to_numpy() - strength * corr
            cv_prediction[val_mask] = pred
            fold_metrics.append(
                {
                    "seed": int(seed),
                    "rows": int(val_mask.sum()),
                    "base_rmse": rmse(
                        val_rows["primary_ndvi"], val_rows["prediction"]
                    ),
                    "calibrated_rmse": rmse(val_rows["primary_ndvi"], pred),
                }
            )

        score = rmse(rows["primary_ndvi"], cv_prediction)
        results.append(
            {
                "mode": mode,
                "lambda_polygon": lambda_polygon,
                "lambda_crop_month": lambda_crop_month,
                "strength": strength,
                "rmse": score,
                "prediction": cv_prediction,
                "folds": fold_metrics,
            }
        )

    best = min(results, key=lambda item: item["rmse"])
    return best, best["prediction"]


def main() -> None:
    reference = pd.read_csv(TRAIN_PATH, parse_dates=[DATE_COL])
    private = pd.read_csv(TEST_PATH, parse_dates=[DATE_COL])
    bundles = (
        joblib.load(MODEL_PATH),
        joblib.load(WHEAT_MODEL_PATH),
        joblib.load(EXTRA_MODEL_PATH),
    )
    rows = build_calibration_rows(private, reference, *bundles)
    rows.to_csv(CALIBRATION_ROWS_PATH, index=False)
    best, calibrated_prediction = cross_validate_calibration(rows)
    base_rmse = rmse(rows["primary_ndvi"], rows["prediction"])
    calibrated_rmse = rmse(rows["primary_ndvi"], calibrated_prediction)

    serializable_best = {k: v for k, v in best.items() if k != "prediction"}
    output = {
        "seeds": list(SEEDS),
        "mask_rate": MASK_RATE,
        "rows": int(len(rows)),
        "unique_rows": int(rows["row_id"].nunique()),
        "base_rmse": base_rmse,
        "calibrated_rmse": calibrated_rmse,
        "improvement": base_rmse - calibrated_rmse,
        "best": serializable_best,
    }
    OUTPUT_PATH.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
    print("\nPRIVATE CALIBRATION CV")
    print(f"rows:       {len(rows):,} ({rows['row_id'].nunique():,} unique)")
    print(f"base:       {base_rmse:.6f}")
    print(f"calibrated: {calibrated_rmse:.6f}")
    print(f"delta:      {base_rmse-calibrated_rmse:+.6f}")
    print(json.dumps(serializable_best, ensure_ascii=False, indent=2))
    print(f"Сохранено: {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
