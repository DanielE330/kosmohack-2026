"""HGB, перевзвешенный под распределение культур в private gaps."""
from __future__ import annotations

from pathlib import Path
from typing import Iterable

import joblib
import numpy as np
import pandas as pd
from sklearn.model_selection import GroupKFold

from config import DATE_COL, GAP_FLAG_COL, ID_COL
from gap_features import align_feature_columns, build_gap_features
from global_model import _new_estimator, rmse


def make_crop_sample_weights(
    meta: pd.DataFrame,
    private: pd.DataFrame,
) -> tuple[np.ndarray, dict[str, float]]:
    """Приближает доли культур training samples к реальным private gaps."""
    train_crop = meta["crop_type"].fillna("unknown").astype(str)
    gap_rows = private[private[GAP_FLAG_COL].eq(True)]
    private_crop = gap_rows["crop_type"].fillna("unknown").astype(str)
    train_share = train_crop.value_counts(normalize=True)
    private_share = private_crop.value_counts(normalize=True)
    ratios = (private_share / train_share).replace([np.inf, -np.inf], np.nan)
    ratios = ratios.fillna(0.20).clip(lower=0.20, upper=4.0)
    weights = train_crop.map(ratios).fillna(0.20).to_numpy(dtype=float)
    weights = weights / weights.mean()
    return weights, {str(k): float(v) for k, v in ratios.items()}


def weighted_rmse(
    y_true: np.ndarray,
    y_pred: np.ndarray,
    weights: np.ndarray,
) -> float:
    return float(np.sqrt(np.average((y_true - y_pred) ** 2, weights=weights)))


def cross_validate_reweighted_hgb(
    X: pd.DataFrame,
    y: pd.Series,
    groups: pd.Series,
    meta: pd.DataFrame,
    sample_weights: np.ndarray,
    base_oof_prediction: Iterable[float],
    crop_weight_map: dict[str, float],
    seed: int = 42,
) -> tuple[dict, np.ndarray, np.ndarray]:
    """GroupKFold и подбор веса модели по private-weighted OOF RMSE."""
    X = X.replace([np.inf, -np.inf], np.nan).reset_index(drop=True)
    y = y.reset_index(drop=True)
    groups = groups.reset_index(drop=True)
    meta = meta.reset_index(drop=True)
    sample_weights = np.asarray(sample_weights, dtype=float)
    base_oof = np.asarray(list(base_oof_prediction), dtype=float)
    y_array = y.to_numpy(dtype=float)
    if len(sample_weights) != len(X) or len(base_oof) != len(X):
        raise ValueError("X, веса и base OOF имеют разную длину")

    baseline = meta["baseline"].astype(float).to_numpy()
    baseline = np.where(np.isfinite(baseline), baseline, float(y.median()))
    residual_target = y_array - baseline
    oof_residual = np.full(len(X), np.nan)
    fold_ids = np.full(len(X), -1, dtype=int)

    splitter = GroupKFold(n_splits=min(5, groups.nunique()))
    for fold, (train_idx, val_idx) in enumerate(splitter.split(X, y, groups)):
        fold_ids[val_idx] = fold
        model = _new_estimator(seed + 700 + fold)
        model.fit(
            X.iloc[train_idx],
            residual_target[train_idx],
            sample_weight=sample_weights[train_idx],
        )
        oof_residual[val_idx] = model.predict(X.iloc[val_idx])

    best = None
    for residual_weight in np.linspace(0.0, 1.4, 29):
        alternative = baseline + residual_weight * oof_residual
        for blend_weight in np.linspace(0.0, 1.0, 21):
            candidate = (
                (1.0 - blend_weight) * base_oof
                + blend_weight * alternative
            )
            candidate = np.clip(candidate, -1.0, 1.0)
            score = weighted_rmse(y_array, candidate, sample_weights)
            if best is None or score < best["weighted_score"]:
                best = {
                    "weighted_score": score,
                    "residual_weight": float(residual_weight),
                    "blend_weight": float(blend_weight),
                    "prediction": candidate,
                    "alternative": alternative,
                }
    assert best is not None

    folds = []
    improved_weighted_folds = 0
    improved_regular_folds = 0
    for fold in sorted(np.unique(fold_ids)):
        val = fold_ids == fold
        base_weighted = weighted_rmse(
            y_array[val], base_oof[val], sample_weights[val]
        )
        new_weighted = weighted_rmse(
            y_array[val], best["prediction"][val], sample_weights[val]
        )
        base_regular = rmse(y_array[val], base_oof[val])
        new_regular = rmse(y_array[val], best["prediction"][val])
        improved_weighted_folds += int(new_weighted < base_weighted)
        improved_regular_folds += int(new_regular < base_regular)
        folds.append(
            {
                "fold": int(fold),
                "rows": int(val.sum()),
                "base_weighted_rmse": base_weighted,
                "ensemble_weighted_rmse": new_weighted,
                "base_rmse": base_regular,
                "ensemble_rmse": new_regular,
            }
        )

    base_regular = rmse(y_array, base_oof)
    final_regular = rmse(y_array, best["prediction"])
    base_weighted = weighted_rmse(y_array, base_oof, sample_weights)
    final_weighted = weighted_rmse(y_array, best["prediction"], sample_weights)
    metrics = {
        "rows": int(len(X)),
        "polygons": int(groups.nunique()),
        "crop_weight_map": crop_weight_map,
        "base_oof_rmse": base_regular,
        "ensemble_oof_rmse": final_regular,
        "base_weighted_oof_rmse": base_weighted,
        "ensemble_weighted_oof_rmse": final_weighted,
        "regular_improvement": base_regular - final_regular,
        "weighted_improvement": base_weighted - final_weighted,
        "residual_weight": best["residual_weight"],
        "blend_weight": best["blend_weight"],
        "clip_predictions": True,
        "improved_weighted_folds": improved_weighted_folds,
        "improved_regular_folds": improved_regular_folds,
        "accepted": bool(
            final_weighted < base_weighted and improved_weighted_folds >= 4
        ),
        "folds": folds,
    }
    return metrics, best["prediction"], best["alternative"]


def fit_reweighted_bundle(
    X: pd.DataFrame,
    y: pd.Series,
    meta: pd.DataFrame,
    sample_weights: np.ndarray,
    metrics: dict,
    seed: int = 42,
) -> dict:
    X = X.replace([np.inf, -np.inf], np.nan).reset_index(drop=True)
    y = y.reset_index(drop=True)
    meta = meta.reset_index(drop=True)
    target_median = float(y.median())
    baseline = meta["baseline"].astype(float).fillna(target_median).to_numpy()
    residual_target = y.to_numpy(dtype=float) - baseline
    model = _new_estimator(seed + 1700)
    model.fit(X, residual_target, sample_weight=sample_weights)
    return {
        "model": model,
        "feature_columns": list(X.columns),
        "residual_weight": float(metrics["residual_weight"]),
        "blend_weight": float(metrics["blend_weight"]),
        "clip_predictions": bool(metrics["clip_predictions"]),
        "target_median": target_median,
        "crop_weight_map": metrics["crop_weight_map"],
        "metrics": metrics,
    }


def save_reweighted_bundle(bundle: dict, path: str | Path) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(bundle, path)


def predict_private_gaps_reweighted(
    private: pd.DataFrame,
    bundle: dict,
    reference: pd.DataFrame | None = None,
    prediction_col: str = "reweighted_prediction",
) -> pd.DataFrame:
    private = private.copy().reset_index(drop=True)
    private[DATE_COL] = pd.to_datetime(private[DATE_COL])
    private["_private_row"] = np.arange(len(private))
    private["_source"] = "private"
    frames = []
    if reference is not None:
        ref = reference.copy().reset_index(drop=True)
        ref[DATE_COL] = pd.to_datetime(ref[DATE_COL])
        ref["_private_row"] = -1
        ref["_source"] = "reference"
        frames.append(ref)
    frames.append(private)
    combined = pd.concat(frames, ignore_index=True, sort=False)
    query = (combined["_source"] == "private") & combined[GAP_FLAG_COL].eq(True)
    built = build_gap_features(combined, query)
    X = align_feature_columns(built.features, bundle["feature_columns"])
    X = X.replace([np.inf, -np.inf], np.nan)
    baseline = (
        built.meta["baseline"].astype(float).fillna(bundle["target_median"]).to_numpy()
    )
    prediction = baseline + bundle["residual_weight"] * bundle["model"].predict(X)
    rows = built.features.index.to_numpy(dtype=int)
    private_rows = combined.loc[rows, "_private_row"].to_numpy(dtype=int)
    result = private.loc[private_rows, [ID_COL, DATE_COL]].copy()
    result[prediction_col] = prediction
    result[DATE_COL] = result[DATE_COL].dt.strftime("%Y-%m-%d")
    return result.reset_index(drop=True)
