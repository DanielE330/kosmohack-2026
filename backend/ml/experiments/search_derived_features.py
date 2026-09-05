"""OOF-проверка явных динамических и межсенсорных признаков."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from config import (  # noqa: E402
    DATE_COL,
    RANDOM_SEED,
    SYNTHETIC_MASK_RATE,
    SYNTHETIC_SEEDS,
    TRAIN_PATH,
)
from modeling import build_training_samples, cross_validate  # noqa: E402
from wheat_specialist import cross_validate_wheat_specialist  # noqa: E402


OUTPUT_PATH = ROOT / "reports/derived_features_experiment.json"


def safe_divide(numerator: pd.Series, denominator: pd.Series) -> pd.Series:
    denominator = denominator.replace(0, np.nan)
    return numerator / denominator


def add_derived_features(X: pd.DataFrame) -> pd.DataFrame:
    result = X.copy()
    prefixes = [
        "target",
        "s2_ndvi",
        "landsat_ndvi",
        "modis_ndvi",
        "s2_evi",
        "landsat_evi",
        "modis_evi",
        "s2_ndwi",
        "landsat_ndwi",
    ]
    for prefix in prefixes:
        span = f"{prefix}_span_days"
        delta = f"{prefix}_neighbor_delta"
        prev_days = f"{prefix}_days_prev1"
        linear = f"{prefix}_linear"
        mean = f"{prefix}_mean"
        if span in result and delta in result:
            result[f"{prefix}_growth_rate"] = safe_divide(
                result[delta], result[span]
            )
        if span in result and prev_days in result:
            result[f"{prefix}_gap_position"] = safe_divide(
                result[prev_days], result[span]
            )
        if linear in result and mean in result:
            result[f"{prefix}_linear_minus_mean"] = result[linear] - result[mean]

    if {"target_slope_before", "target_slope_after"}.issubset(result.columns):
        result["target_slope_change"] = (
            result["target_slope_after"] - result["target_slope_before"]
        )
        result["target_slope_average"] = (
            result["target_slope_after"] + result["target_slope_before"]
        ) / 2.0

    sensor_linear_cols = [
        col
        for col in (
            "s2_ndvi_linear",
            "landsat_ndvi_linear",
            "modis_ndvi_linear",
        )
        if col in result
    ]
    if sensor_linear_cols:
        result["sensor_ndvi_linear_median"] = result[sensor_linear_cols].median(
            axis=1, skipna=True
        )
        result["sensor_ndvi_linear_std"] = result[sensor_linear_cols].std(
            axis=1, skipna=True
        )
        result["sensor_ndvi_linear_count"] = result[sensor_linear_cols].notna().sum(
            axis=1
        )
        if "target_linear" in result:
            result["target_vs_sensor_consensus"] = (
                result["target_linear"] - result["sensor_ndvi_linear_median"]
            )

    # Явные crop × season взаимодействия: дереву не нужно заново искать их
    # через несколько последовательных split-ов.
    crop_cols = [col for col in result.columns if col.startswith("crop_")]
    for crop_col in crop_cols:
        result[f"{crop_col}_doy_sin"] = result[crop_col] * result["doy_sin"]
        result[f"{crop_col}_doy_cos"] = result[crop_col] * result["doy_cos"]

    return result.replace([np.inf, -np.inf], np.nan)


def main() -> None:
    train = pd.read_csv(TRAIN_PATH, parse_dates=[DATE_COL])
    X, y, groups, meta = build_training_samples(
        train,
        seeds=SYNTHETIC_SEEDS,
        mask_rate=SYNTHETIC_MASK_RATE,
    )
    original_columns = len(X.columns)
    X = add_derived_features(X)
    print(f"Признаки: {original_columns} -> {len(X.columns)}")

    global_metrics, global_oof = cross_validate(
        X, y, groups, meta, seed=RANDOM_SEED
    )
    ensemble_metrics, ensemble_oof, _ = cross_validate_wheat_specialist(
        X=X,
        y=y,
        groups=groups,
        meta=meta,
        global_oof_prediction=global_oof,
        seed=RANDOM_SEED,
    )

    output = {
        "original_feature_count": original_columns,
        "new_feature_count": len(X.columns),
        "global": global_metrics,
        "ensemble": ensemble_metrics,
    }
    OUTPUT_PATH.write_text(
        json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print("\nRESULT")
    print(f"Original accepted ensemble: 0.063122")
    print(f"Derived global:            {global_metrics['oof_rmse']:.6f}")
    print(f"Derived + wheat:           {ensemble_metrics['ensemble_oof_rmse']:.6f}")
    print(f"Wheat blend:               {ensemble_metrics['wheat_blend_weight']:.2f}")
    print(f"Сохранено: {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
