"""Поиск устойчивого spring-wheat режима поверх текущего wheat ensemble."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.model_selection import GroupKFold


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from config import (  # noqa: E402
    DATE_COL,
    RANDOM_SEED,
    SYNTHETIC_MASK_RATE,
    SYNTHETIC_SEEDS,
    TRAIN_PATH,
)
from modeling import _new_estimator, build_training_samples, rmse  # noqa: E402


BASE_OOF_PATH = ROOT / "reports/wheat_oof_predictions.csv"
OUTPUT_PATH = ROOT / "reports/spring_wheat_search.json"


def align_base_oof(meta: pd.DataFrame, y: pd.Series) -> np.ndarray:
    old = pd.read_csv(BASE_OOF_PATH)
    lookup = old[
        ["synthetic_seed", "row_id", "target_true", "ensemble_prediction"]
    ].copy()
    aligned = meta[["synthetic_seed", "row_id"]].merge(
        lookup,
        on=["synthetic_seed", "row_id"],
        how="left",
        validate="one_to_one",
        sort=False,
    )
    if aligned.isna().any().any():
        raise ValueError("Не удалось выровнять текущий ensemble OOF")
    if not np.allclose(aligned["target_true"], y):
        raise ValueError("target в wheat OOF не совпадает с новой выборкой")
    return aligned["ensemble_prediction"].to_numpy(dtype=float)


def specialist_oof(
    X: pd.DataFrame,
    residual_target: np.ndarray,
    groups: pd.Series,
    train_scope: np.ndarray,
    predict_scope: np.ndarray,
    seed_offset: int,
) -> tuple[np.ndarray, np.ndarray]:
    prediction = np.full(len(X), np.nan)
    fold_ids = np.full(len(X), -1, dtype=int)
    splitter = GroupKFold(n_splits=min(5, groups.nunique()))
    for fold, (train_idx, val_idx) in enumerate(splitter.split(X, groups=groups)):
        fold_ids[val_idx] = fold
        local_train = train_idx[train_scope[train_idx]]
        local_val = val_idx[predict_scope[val_idx]]
        if not len(local_val):
            continue
        if len(local_train) < 100:
            raise ValueError(f"fold={fold}: мало specialist train: {len(local_train)}")
        model = _new_estimator(RANDOM_SEED + seed_offset + fold)
        model.fit(X.iloc[local_train], residual_target[local_train])
        prediction[local_val] = model.predict(X.iloc[local_val])
    return prediction, fold_ids


def tune_candidate(
    name: str,
    y: np.ndarray,
    baseline: np.ndarray,
    base_prediction: np.ndarray,
    specialist_residual: np.ndarray,
    apply_mask: np.ndarray,
    fold_ids: np.ndarray,
) -> dict:
    valid = apply_mask & np.isfinite(specialist_residual)
    if valid.sum() < 100:
        raise ValueError(f"{name}: слишком мало строк ({valid.sum()})")

    best = None
    for residual_weight in np.linspace(0.0, 1.4, 29):
        specialist = baseline + residual_weight * specialist_residual
        for blend_weight in np.linspace(0.0, 1.0, 21):
            candidate = base_prediction.copy()
            candidate[valid] = (
                (1.0 - blend_weight) * base_prediction[valid]
                + blend_weight * specialist[valid]
            )
            score = rmse(y, candidate)
            if best is None or score < best["oof_rmse"]:
                best = {
                    "name": name,
                    "rows": int(valid.sum()),
                    "oof_rmse": score,
                    "residual_weight": float(residual_weight),
                    "blend_weight": float(blend_weight),
                    "prediction": candidate,
                    "specialist_prediction": specialist,
                }

    assert best is not None
    folds = []
    improved_folds = 0
    for fold in sorted(np.unique(fold_ids)):
        val = fold_ids == fold
        base_rmse = rmse(y[val], base_prediction[val])
        new_rmse = rmse(y[val], best["prediction"][val])
        improved_folds += int(new_rmse < base_rmse)
        folds.append(
            {
                "fold": int(fold),
                "base_rmse": base_rmse,
                "candidate_rmse": new_rmse,
                "improvement": base_rmse - new_rmse,
            }
        )
    best["improved_folds"] = improved_folds
    best["folds"] = folds
    return best


def main() -> None:
    train = pd.read_csv(TRAIN_PATH, parse_dates=[DATE_COL])
    X, y_series, groups, meta = build_training_samples(
        train,
        seeds=SYNTHETIC_SEEDS,
        mask_rate=SYNTHETIC_MASK_RATE,
    )
    X = X.replace([np.inf, -np.inf], np.nan).reset_index(drop=True)
    y_series = y_series.reset_index(drop=True)
    groups = groups.reset_index(drop=True)
    meta = meta.reset_index(drop=True)
    y = y_series.to_numpy(dtype=float)
    base = align_base_oof(meta, y_series)

    baseline = meta["baseline"].astype(float).to_numpy()
    baseline = np.where(np.isfinite(baseline), baseline, float(y_series.median()))
    residual_target = y - baseline
    months = pd.to_datetime(meta[DATE_COL]).dt.month.to_numpy()
    wheat = meta["crop_type"].fillna("unknown").astype(str).eq("озимая пшеница").to_numpy()
    span = X["target_span_days"].to_numpy(dtype=float)

    definitions = [
        {
            "train_name": "wheat_apr_jun",
            "train_months": [4, 5, 6],
            "apply": {
                "apr_jun_all": wheat & np.isin(months, [4, 5, 6]),
                "apr_jun_6_20": wheat & np.isin(months, [4, 5, 6]) & (span > 5) & (span <= 20),
                "may_jun_6_20": wheat & np.isin(months, [5, 6]) & (span > 5) & (span <= 20),
                "jun_6_20": wheat & (months == 6) & (span > 5) & (span <= 20),
            },
        },
        {
            "train_name": "wheat_apr_jul",
            "train_months": [4, 5, 6, 7],
            "apply": {
                "apr_jun_all": wheat & np.isin(months, [4, 5, 6]),
                "apr_jun_6_20": wheat & np.isin(months, [4, 5, 6]) & (span > 5) & (span <= 20),
                "may_jun_6_20": wheat & np.isin(months, [5, 6]) & (span > 5) & (span <= 20),
                "jun_6_20": wheat & (months == 6) & (span > 5) & (span <= 20),
            },
        },
        {
            "train_name": "wheat_may_jun",
            "train_months": [5, 6],
            "apply": {
                "may_jun_all": wheat & np.isin(months, [5, 6]),
                "may_jun_6_20": wheat & np.isin(months, [5, 6]) & (span > 5) & (span <= 20),
                "jun_6_20": wheat & (months == 6) & (span > 5) & (span <= 20),
            },
        },
    ]

    results = []
    cached_predictions = {}
    cached_folds = {}
    for i, definition in enumerate(definitions):
        train_scope = wheat & np.isin(months, definition["train_months"])
        prediction, fold_ids = specialist_oof(
            X,
            residual_target,
            groups,
            train_scope=train_scope,
            predict_scope=wheat,
            seed_offset=200 + 20 * i,
        )
        cached_predictions[definition["train_name"]] = prediction
        cached_folds[definition["train_name"]] = fold_ids
        for apply_name, apply_mask in definition["apply"].items():
            result = tune_candidate(
                f"{definition['train_name']}__{apply_name}",
                y,
                baseline,
                base,
                prediction,
                apply_mask,
                fold_ids,
            )
            results.append(result)
            print(
                f"{result['name']:<44} rows={result['rows']:4d} "
                f"rmse={result['oof_rmse']:.6f} "
                f"delta={rmse(y, base)-result['oof_rmse']:+.6f} "
                f"folds={result['improved_folds']}/5 "
                f"rw={result['residual_weight']:.2f} blend={result['blend_weight']:.2f}"
            )

    stable = [r for r in results if r["improved_folds"] >= 4]
    pool = stable or results
    best = min(pool, key=lambda item: item["oof_rmse"])
    serializable = []
    for result in sorted(results, key=lambda item: item["oof_rmse"]):
        serializable.append({k: v for k, v in result.items() if k not in {"prediction", "specialist_prediction"}})
    output = {
        "base_oof_rmse": rmse(y, base),
        "best": {k: v for k, v in best.items() if k not in {"prediction", "specialist_prediction"}},
        "candidates": serializable,
    }
    OUTPUT_PATH.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
    print("\nBEST")
    print(json.dumps(output["best"], ensure_ascii=False, indent=2))
    print(f"\nСохранено: {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
