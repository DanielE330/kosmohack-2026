"""Обучение, честная валидация и инференс модели восстановления NDVI."""
from __future__ import annotations

import os
from pathlib import Path
from typing import Iterable

import joblib
import numpy as np
import pandas as pd

# В контейнерах число физических CPU иногда не определяется; фиксируем только
# служебное предупреждение joblib, на математический результат это не влияет.
os.environ.setdefault("LOKY_MAX_CPU_COUNT", "1")

from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.metrics import mean_squared_error
from sklearn.model_selection import GroupKFold

from config import DATE_COL, ID_COL, TARGET_COL
from gap_features import align_feature_columns, build_gap_features, make_synthetic_mask


def rmse(y_true: Iterable[float], y_pred: Iterable[float]) -> float:
    return float(np.sqrt(mean_squared_error(y_true, y_pred)))


def gapscore(value: float) -> float:
    return round(30 * max(0.0, 1.0 - value / 0.10), 2)


def _new_estimator(seed: int = 42) -> HistGradientBoostingRegressor:
    # Небольшая регуляризованная модель хорошо работает на 10-20 тыс. синтетических
    # пропусков и нативно обрабатывает NaN в краевых/длинных gaps.
    return HistGradientBoostingRegressor(
        loss="squared_error",
        learning_rate=0.045,
        max_iter=350,
        max_leaf_nodes=23,
        max_depth=None,
        min_samples_leaf=24,
        l2_regularization=0.35,
        early_stopping=True,
        validation_fraction=0.12,
        n_iter_no_change=35,
        random_state=seed,
    )


def build_training_samples(
    train: pd.DataFrame,
    seeds: tuple[int, ...] = (13, 42, 87),
    mask_rate: float = 0.15,
) -> tuple[pd.DataFrame, pd.Series, pd.Series, pd.DataFrame]:
    """Создаёт несколько реалистичных вариантов synthetic gaps."""
    source = train.copy().reset_index(drop=True)
    source[DATE_COL] = pd.to_datetime(source[DATE_COL])
    batches: list[pd.DataFrame] = []
    targets: list[pd.Series] = []
    groups: list[pd.Series] = []
    metas: list[pd.DataFrame] = []

    for seed in seeds:
        mask = make_synthetic_mask(source, rate=mask_rate, seed=seed)
        built = build_gap_features(source, mask)
        row_ids = built.features.index.to_numpy(dtype=int)
        batch = built.features.replace([np.inf, -np.inf], np.nan).copy()
        batches.append(batch.reset_index(drop=True))
        targets.append(source.loc[row_ids, TARGET_COL].reset_index(drop=True))
        groups.append(source.loc[row_ids, ID_COL].reset_index(drop=True))
        meta = built.meta.reset_index(drop=True)
        meta["synthetic_seed"] = seed
        meta["row_id"] = row_ids
        metas.append(meta)

    X = pd.concat(batches, ignore_index=True, sort=False)
    y = pd.concat(targets, ignore_index=True)
    group_series = pd.concat(groups, ignore_index=True)
    meta = pd.concat(metas, ignore_index=True, sort=False)
    return X, y, group_series, meta


def _baseline_metrics(y: pd.Series, meta: pd.DataFrame) -> dict[str, float]:
    metrics: dict[str, float] = {}
    for name in (
        "baseline_mean",
        "baseline_linear",
        "baseline_climatology",
        "baseline",
    ):
        pred = meta[name].astype(float)
        valid = pred.notna()
        metrics[f"{name}_rmse"] = rmse(y[valid], pred[valid])
    return metrics


def cross_validate(
    X: pd.DataFrame,
    y: pd.Series,
    groups: pd.Series,
    meta: pd.DataFrame,
    seed: int = 42,
) -> tuple[dict, np.ndarray]:
    """GroupKFold: ни один полигон не попадает одновременно в train и val."""
    X = X.replace([np.inf, -np.inf], np.nan)
    baseline = meta["baseline"].astype(float).to_numpy()
    fallback = float(y.median())
    baseline = np.where(np.isfinite(baseline), baseline, fallback)
    residual_target = y.to_numpy(dtype=float) - baseline
    oof_residual = np.zeros(len(X), dtype=float)
    fold_metrics: list[dict] = []

    splitter = GroupKFold(n_splits=min(5, groups.nunique()))
    for fold, (train_idx, val_idx) in enumerate(splitter.split(X, y, groups)):
        model = _new_estimator(seed + fold)
        model.fit(X.iloc[train_idx], residual_target[train_idx])
        oof_residual[val_idx] = model.predict(X.iloc[val_idx])
        raw_pred = baseline[val_idx] + oof_residual[val_idx]
        fold_metrics.append(
            {
                "fold": fold,
                "polygons": int(groups.iloc[val_idx].nunique()),
                "rows": int(len(val_idx)),
                "baseline_rmse": rmse(y.iloc[val_idx], baseline[val_idx]),
                "model_rmse": rmse(y.iloc[val_idx], raw_pred),
            }
        )

    # Масштаб residual-коррекции выбирается только по OOF прогнозам.
    weights = np.linspace(0.0, 1.4, 29)
    candidates = {
        float(weight): rmse(y, baseline + weight * oof_residual) for weight in weights
    }
    residual_weight = min(candidates, key=candidates.get)
    oof_prediction = baseline + residual_weight * oof_residual

    unclipped_rmse = rmse(y, oof_prediction)
    clipped_prediction = np.clip(oof_prediction, -1.0, 1.0)
    clipped_rmse = rmse(y, clipped_prediction)
    use_clip = clipped_rmse < unclipped_rmse
    final_oof = clipped_prediction if use_clip else oof_prediction

    metrics = {
        "rows": int(len(X)),
        "polygons": int(groups.nunique()),
        **_baseline_metrics(y, meta),
        "oof_rmse": rmse(y, final_oof),
        "oof_gapscore": gapscore(rmse(y, final_oof)),
        "residual_weight": float(residual_weight),
        "clip_predictions": bool(use_clip),
        "folds": fold_metrics,
    }
    return metrics, final_oof


def fit_bundle(
    X: pd.DataFrame,
    y: pd.Series,
    meta: pd.DataFrame,
    metrics: dict,
    seed: int = 42,
) -> dict:
    X = X.replace([np.inf, -np.inf], np.nan)
    baseline = meta["baseline"].astype(float).fillna(y.median()).to_numpy()
    residual = y.to_numpy(dtype=float) - baseline
    model = _new_estimator(seed)
    model.fit(X, residual)
    return {
        "model": model,
        "feature_columns": list(X.columns),
        "residual_weight": metrics["residual_weight"],
        "clip_predictions": metrics["clip_predictions"],
        "target_median": float(y.median()),
        "metrics": metrics,
    }


def save_bundle(bundle: dict, path: str | Path) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(bundle, path)


def predict_private_gaps(
    private: pd.DataFrame,
    bundle: dict,
    reference: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """Предсказывает только строки private_features с is_synthetic_gap=True."""
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
    baseline = built.meta["baseline"].astype(float).fillna(bundle["target_median"]).to_numpy()
    residual = bundle["model"].predict(X)
    prediction = baseline + bundle["residual_weight"] * residual
    if bundle.get("clip_predictions", False):
        prediction = np.clip(prediction, -1.0, 1.0)

    combined_query_rows = built.features.index.to_numpy(dtype=int)
    private_rows = combined.loc[combined_query_rows, "_private_row"].to_numpy(dtype=int)
    result = private.loc[private_rows, [ID_COL, DATE_COL]].copy()
    result["primary_ndvi_pred"] = prediction
    result[DATE_COL] = result[DATE_COL].dt.strftime("%Y-%m-%d")
    return result.reset_index(drop=True)
