"""ExtraTrees residual-модель и ансамбль поверх global + wheat HGB."""
from __future__ import annotations

import os
from pathlib import Path
from typing import Iterable

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import ExtraTreesRegressor
from sklearn.model_selection import GroupKFold

from config import DATE_COL, ID_COL
from gap_features import align_feature_columns, build_gap_features
from global_model import rmse


os.environ.setdefault("LOKY_MAX_CPU_COUNT", "1")

N_ESTIMATORS = 90
MIN_SAMPLES_LEAF = 3
MAX_FEATURES = 0.45


def _new_extra_trees(seed: int) -> ExtraTreesRegressor:
    return ExtraTreesRegressor(
        n_estimators=N_ESTIMATORS,
        min_samples_leaf=MIN_SAMPLES_LEAF,
        max_features=MAX_FEATURES,
        bootstrap=False,
        n_jobs=-1,
        random_state=seed,
    )


def cross_validate_extra_trees(
    X: pd.DataFrame,
    y: pd.Series,
    groups: pd.Series,
    meta: pd.DataFrame,
    base_oof_prediction: Iterable[float],
    seed: int = 42,
) -> tuple[dict, np.ndarray, np.ndarray]:
    """Честный GroupKFold для ExtraTrees и подбор веса ансамбля по OOF."""
    X = X.replace([np.inf, -np.inf], np.nan).reset_index(drop=True)
    y = y.reset_index(drop=True)
    groups = groups.reset_index(drop=True)
    meta = meta.reset_index(drop=True)
    y_array = y.to_numpy(dtype=float)
    base_oof = np.asarray(list(base_oof_prediction), dtype=float)

    if len(base_oof) != len(X) or not np.isfinite(base_oof).all():
        raise ValueError("base_oof_prediction не совпадает с матрицей X")

    baseline = meta["baseline"].astype(float).to_numpy()
    baseline = np.where(np.isfinite(baseline), baseline, float(y.median()))
    residual_target = y_array - baseline
    extra_oof_residual = np.full(len(X), np.nan)
    fold_ids = np.full(len(X), -1, dtype=int)

    splitter = GroupKFold(n_splits=min(5, groups.nunique()))
    for fold, (train_idx, val_idx) in enumerate(splitter.split(X, y, groups)):
        fold_ids[val_idx] = fold
        model = _new_extra_trees(seed + fold)
        model.fit(X.iloc[train_idx], residual_target[train_idx])
        extra_oof_residual[val_idx] = model.predict(X.iloc[val_idx])

    if not np.isfinite(extra_oof_residual).all():
        raise RuntimeError("Не для всех строк получен ExtraTrees OOF")

    best = None
    for residual_weight in np.linspace(0.0, 1.4, 29):
        extra_prediction = baseline + residual_weight * extra_oof_residual
        for blend_weight in np.linspace(0.0, 1.0, 21):
            candidate = (
                (1.0 - blend_weight) * base_oof
                + blend_weight * extra_prediction
            )
            candidate = np.clip(candidate, -1.0, 1.0)
            score = rmse(y_array, candidate)
            if best is None or score < best["score"]:
                best = {
                    "score": score,
                    "residual_weight": float(residual_weight),
                    "blend_weight": float(blend_weight),
                    "prediction": candidate,
                    "extra_prediction": extra_prediction,
                }

    assert best is not None
    fold_metrics = []
    improved_folds = 0
    for fold in sorted(np.unique(fold_ids)):
        val = fold_ids == fold
        base_score = rmse(y_array[val], base_oof[val])
        final_score = rmse(y_array[val], best["prediction"][val])
        improved_folds += int(final_score < base_score)
        fold_metrics.append(
            {
                "fold": int(fold),
                "rows": int(val.sum()),
                "base_rmse": base_score,
                "ensemble_rmse": final_score,
                "improvement": base_score - final_score,
            }
        )

    base_score = rmse(y_array, base_oof)
    metrics = {
        "rows": int(len(X)),
        "polygons": int(groups.nunique()),
        "n_estimators": N_ESTIMATORS,
        "min_samples_leaf": MIN_SAMPLES_LEAF,
        "max_features": MAX_FEATURES,
        "base_oof_rmse": base_score,
        "extra_trees_oof_rmse": rmse(y_array, best["extra_prediction"]),
        "ensemble_oof_rmse": float(best["score"]),
        "absolute_improvement": base_score - float(best["score"]),
        "relative_improvement_pct": 100.0
        * (base_score - float(best["score"]))
        / base_score,
        "residual_weight": best["residual_weight"],
        "blend_weight": best["blend_weight"],
        "clip_predictions": True,
        "improved_folds": improved_folds,
        "accepted": bool(best["score"] < base_score and improved_folds >= 4),
        "folds": fold_metrics,
    }
    return metrics, best["prediction"], best["extra_prediction"]


def fit_extra_trees_bundle(
    X: pd.DataFrame,
    y: pd.Series,
    meta: pd.DataFrame,
    metrics: dict,
    seed: int = 42,
) -> dict:
    """Обучает production ExtraTrees на всех synthetic gaps."""
    X = X.replace([np.inf, -np.inf], np.nan).reset_index(drop=True)
    y = y.reset_index(drop=True)
    meta = meta.reset_index(drop=True)
    baseline = meta["baseline"].astype(float).to_numpy()
    target_median = float(y.median())
    baseline = np.where(np.isfinite(baseline), baseline, target_median)
    residual_target = y.to_numpy(dtype=float) - baseline

    model = _new_extra_trees(seed + 1000)
    model.fit(X, residual_target)
    return {
        "model": model,
        "feature_columns": list(X.columns),
        "residual_weight": float(metrics["residual_weight"]),
        "blend_weight": float(metrics["blend_weight"]),
        "clip_predictions": bool(metrics["clip_predictions"]),
        "target_median": target_median,
        "metrics": metrics,
    }


def save_extra_trees_bundle(bundle: dict, path: str | Path) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(bundle, path)


def predict_private_gaps_extra_trees(
    private: pd.DataFrame,
    bundle: dict,
    reference: pd.DataFrame | None = None,
    prediction_col: str = "extra_trees_prediction",
) -> pd.DataFrame:
    """Возвращает standalone ExtraTrees-прогноз для private gaps."""
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
    query = (combined["_source"] == "private") & combined["is_synthetic_gap"].eq(True)

    built = build_gap_features(combined, query)
    X = align_feature_columns(built.features, bundle["feature_columns"])
    X = X.replace([np.inf, -np.inf], np.nan)
    baseline = (
        built.meta["baseline"]
        .astype(float)
        .fillna(bundle["target_median"])
        .to_numpy()
    )
    prediction = (
        baseline
        + bundle["residual_weight"] * bundle["model"].predict(X)
    )

    combined_rows = built.features.index.to_numpy(dtype=int)
    private_rows = combined.loc[combined_rows, "_private_row"].to_numpy(dtype=int)
    result = private.loc[private_rows, [ID_COL, DATE_COL]].copy()
    result[prediction_col] = prediction
    result[DATE_COL] = result[DATE_COL].dt.strftime("%Y-%m-%d")
    return result.reset_index(drop=True)
