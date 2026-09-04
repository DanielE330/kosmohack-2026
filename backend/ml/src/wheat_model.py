"""Специализированная модель восстановления NDVI для озимой пшеницы.

Модуль не изменяет глобальную модель. Он обучает второй residual-бустинг
только на озимой пшенице и смешивает его прогноз с глобальным прогнозом.
Все веса выбираются только по GroupKFold OOF-предсказаниям.
"""
from __future__ import annotations

from pathlib import Path
from typing import Iterable

import joblib
import numpy as np
import pandas as pd
from sklearn.model_selection import GroupKFold

from config import DATE_COL, ID_COL, TARGET_COL
from gap_features import align_feature_columns, build_gap_features
from modeling import _new_estimator, rmse


SPECIAL_CROP = "озимая пшеница"


def cross_validate_wheat_specialist(
    X: pd.DataFrame,
    y: pd.Series,
    groups: pd.Series,
    meta: pd.DataFrame,
    global_oof_prediction: Iterable[float],
    seed: int = 42,
) -> tuple[dict, np.ndarray, np.ndarray]:
    """Проверяет wheat-модель на тех же GroupKFold-фолдах, что и global.

    Возвращает метрики, итоговый ensemble OOF и standalone wheat OOF.
    Для культур, отличных от SPECIAL_CROP, wheat OOF содержит NaN.
    """
    X = X.replace([np.inf, -np.inf], np.nan).reset_index(drop=True)
    y = y.reset_index(drop=True)
    groups = groups.reset_index(drop=True)
    meta = meta.reset_index(drop=True)

    y_array = y.to_numpy(dtype=float)
    global_oof = np.asarray(list(global_oof_prediction), dtype=float)
    if len(global_oof) != len(X):
        raise ValueError("global_oof_prediction и X имеют разную длину")
    if not np.isfinite(global_oof).all():
        raise ValueError("global_oof_prediction содержит NaN/inf")

    baseline = meta["baseline"].astype(float).to_numpy()
    baseline = np.where(np.isfinite(baseline), baseline, float(y.median()))
    residual_target = y_array - baseline

    wheat_mask = (
        meta["crop_type"].fillna("unknown").astype(str).eq(SPECIAL_CROP).to_numpy()
    )
    if wheat_mask.sum() < 100:
        raise ValueError(f"Слишком мало строк культуры {SPECIAL_CROP!r}")

    wheat_oof_residual = np.full(len(X), np.nan)
    fold_ids = np.full(len(X), -1, dtype=int)
    splitter = GroupKFold(n_splits=min(5, groups.nunique()))

    for fold, (train_idx, val_idx) in enumerate(splitter.split(X, y, groups)):
        fold_ids[val_idx] = fold
        wheat_train_idx = train_idx[wheat_mask[train_idx]]
        wheat_val_idx = val_idx[wheat_mask[val_idx]]

        if len(wheat_val_idx) == 0:
            continue
        if len(wheat_train_idx) < 100:
            raise ValueError(
                f"В fold={fold} только {len(wheat_train_idx)} обучающих wheat-строк"
            )

        model = _new_estimator(seed + 100 + fold)
        model.fit(X.iloc[wheat_train_idx], residual_target[wheat_train_idx])
        wheat_oof_residual[wheat_val_idx] = model.predict(X.iloc[wheat_val_idx])

    wheat_valid = wheat_mask & np.isfinite(wheat_oof_residual)
    if wheat_valid.sum() != wheat_mask.sum():
        missing = int(wheat_mask.sum() - wheat_valid.sum())
        raise RuntimeError(f"Не получен OOF-прогноз для {missing} wheat-строк")

    # Сначала подбираем силу residual-коррекции отдельной модели.
    residual_weights = np.linspace(0.0, 1.4, 29)
    residual_candidates = {
        float(weight): rmse(
            y_array[wheat_valid],
            baseline[wheat_valid] + weight * wheat_oof_residual[wheat_valid],
        )
        for weight in residual_weights
    }
    wheat_residual_weight = min(residual_candidates, key=residual_candidates.get)

    wheat_oof_prediction = np.full(len(X), np.nan)
    wheat_oof_prediction[wheat_valid] = (
        baseline[wheat_valid]
        + wheat_residual_weight * wheat_oof_residual[wheat_valid]
    )

    # Затем выбираем, какую долю specialist-прогноза подмешивать к global.
    blend_weights = np.linspace(0.0, 1.0, 21)
    blend_candidates: dict[float, float] = {}
    for blend_weight in blend_weights:
        candidate = global_oof.copy()
        candidate[wheat_valid] = (
            (1.0 - blend_weight) * global_oof[wheat_valid]
            + blend_weight * wheat_oof_prediction[wheat_valid]
        )
        blend_candidates[float(blend_weight)] = rmse(y_array, candidate)

    wheat_blend_weight = min(blend_candidates, key=blend_candidates.get)
    ensemble_oof = global_oof.copy()
    ensemble_oof[wheat_valid] = (
        (1.0 - wheat_blend_weight) * global_oof[wheat_valid]
        + wheat_blend_weight * wheat_oof_prediction[wheat_valid]
    )

    unclipped_rmse = rmse(y_array, ensemble_oof)
    clipped_oof = np.clip(ensemble_oof, -1.0, 1.0)
    clipped_rmse = rmse(y_array, clipped_oof)
    use_clip = clipped_rmse < unclipped_rmse
    final_oof = clipped_oof if use_clip else ensemble_oof

    fold_metrics = []
    for fold in sorted(np.unique(fold_ids)):
        val = fold_ids == fold
        wheat_val = val & wheat_mask
        item = {
            "fold": int(fold),
            "rows": int(val.sum()),
            "wheat_rows": int(wheat_val.sum()),
            "global_rmse": rmse(y_array[val], global_oof[val]),
            "ensemble_rmse": rmse(y_array[val], final_oof[val]),
        }
        if wheat_val.any():
            item["wheat_global_rmse"] = rmse(
                y_array[wheat_val], global_oof[wheat_val]
            )
            item["wheat_ensemble_rmse"] = rmse(
                y_array[wheat_val], final_oof[wheat_val]
            )
        fold_metrics.append(item)

    global_rmse = rmse(y_array, global_oof)
    ensemble_rmse = rmse(y_array, final_oof)
    metrics = {
        "special_crop": SPECIAL_CROP,
        "rows": int(len(X)),
        "wheat_rows": int(wheat_mask.sum()),
        "global_oof_rmse": global_rmse,
        "ensemble_oof_rmse": ensemble_rmse,
        "absolute_improvement": global_rmse - ensemble_rmse,
        "relative_improvement_pct": 100.0 * (global_rmse - ensemble_rmse) / global_rmse,
        "wheat_global_rmse": rmse(y_array[wheat_valid], global_oof[wheat_valid]),
        "wheat_specialist_rmse": rmse(
            y_array[wheat_valid], wheat_oof_prediction[wheat_valid]
        ),
        "wheat_ensemble_rmse": rmse(y_array[wheat_valid], final_oof[wheat_valid]),
        "wheat_residual_weight": float(wheat_residual_weight),
        "wheat_blend_weight": float(wheat_blend_weight),
        "clip_predictions": bool(use_clip),
        "accepted": bool(ensemble_rmse < global_rmse and wheat_blend_weight > 0),
        "folds": fold_metrics,
    }
    return metrics, final_oof, wheat_oof_prediction


def fit_wheat_bundle(
    X: pd.DataFrame,
    y: pd.Series,
    meta: pd.DataFrame,
    metrics: dict,
    seed: int = 42,
) -> dict:
    """Обучает production wheat-модель на всех wheat synthetic gaps."""
    X = X.replace([np.inf, -np.inf], np.nan).reset_index(drop=True)
    y = y.reset_index(drop=True)
    meta = meta.reset_index(drop=True)
    wheat_mask = (
        meta["crop_type"].fillna("unknown").astype(str).eq(SPECIAL_CROP).to_numpy()
    )

    baseline = meta["baseline"].astype(float).to_numpy()
    wheat_target_median = float(y[wheat_mask].median())
    baseline = np.where(np.isfinite(baseline), baseline, wheat_target_median)
    residual = y.to_numpy(dtype=float) - baseline

    model = _new_estimator(seed + 1000)
    model.fit(X.iloc[np.flatnonzero(wheat_mask)], residual[wheat_mask])
    return {
        "model": model,
        "feature_columns": list(X.columns),
        "special_crop": SPECIAL_CROP,
        "residual_weight": float(metrics["wheat_residual_weight"]),
        "blend_weight": float(metrics["wheat_blend_weight"]),
        "clip_predictions": bool(metrics["clip_predictions"]),
        "target_median": wheat_target_median,
        "metrics": metrics,
    }


def save_wheat_bundle(bundle: dict, path: str | Path) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(bundle, path)


def predict_private_gaps_ensemble(
    private: pd.DataFrame,
    global_bundle: dict,
    wheat_bundle: dict,
    reference: pd.DataFrame | None = None,
    prediction_col: str = "primary_ndvi_true",
) -> pd.DataFrame:
    """Применяет global ко всем gaps и specialist только к озимой пшенице."""
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

    global_X = align_feature_columns(
        built.features, global_bundle["feature_columns"]
    ).replace([np.inf, -np.inf], np.nan)
    global_baseline = (
        built.meta["baseline"]
        .astype(float)
        .fillna(global_bundle["target_median"])
        .to_numpy()
    )
    global_prediction = (
        global_baseline
        + global_bundle["residual_weight"]
        * global_bundle["model"].predict(global_X)
    )
    if global_bundle.get("clip_predictions", False):
        global_prediction = np.clip(global_prediction, -1.0, 1.0)

    final_prediction = global_prediction.copy()
    crop = wheat_bundle.get("special_crop", SPECIAL_CROP)
    wheat_mask = built.meta["crop_type"].fillna("unknown").astype(str).eq(crop).to_numpy()

    if wheat_mask.any() and wheat_bundle.get("blend_weight", 0.0) > 0:
        wheat_X = align_feature_columns(
            built.features, wheat_bundle["feature_columns"]
        ).replace([np.inf, -np.inf], np.nan)
        wheat_baseline = (
            built.meta["baseline"]
            .astype(float)
            .fillna(wheat_bundle["target_median"])
            .to_numpy()
        )
        wheat_rows = np.flatnonzero(wheat_mask)
        wheat_prediction = (
            wheat_baseline[wheat_rows]
            + wheat_bundle["residual_weight"]
            * wheat_bundle["model"].predict(wheat_X.iloc[wheat_rows])
        )
        blend = float(wheat_bundle["blend_weight"])
        final_prediction[wheat_rows] = (
            (1.0 - blend) * global_prediction[wheat_rows]
            + blend * wheat_prediction
        )

    if wheat_bundle.get("clip_predictions", False):
        final_prediction = np.clip(final_prediction, -1.0, 1.0)

    combined_query_rows = built.features.index.to_numpy(dtype=int)
    private_rows = combined.loc[combined_query_rows, "_private_row"].to_numpy(dtype=int)
    result = private.loc[private_rows, [ID_COL, DATE_COL]].copy()
    result[prediction_col] = final_prediction
    result[DATE_COL] = result[DATE_COL].dt.strftime("%Y-%m-%d")
    return result.reset_index(drop=True)
