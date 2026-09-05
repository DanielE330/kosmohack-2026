"""Ищет разнообразную ExtraTrees-модель для ансамбля с текущим HGB."""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import ExtraTreesRegressor
from sklearn.model_selection import GroupKFold


os.environ.setdefault("LOKY_MAX_CPU_COUNT", "1")
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from config import (  # noqa: E402
    DATE_COL,
    RANDOM_SEED,
    SYNTHETIC_MASK_RATE,
    SYNTHETIC_SEEDS,
    TRAIN_PATH,
)
from modeling import build_training_samples, rmse  # noqa: E402


BASE_OOF_PATH = ROOT / "reports/wheat_oof_predictions.csv"
OUTPUT_PATH = ROOT / "reports/extra_trees_search.json"


def align_base_oof(meta: pd.DataFrame, y: pd.Series) -> np.ndarray:
    old = pd.read_csv(BASE_OOF_PATH)
    aligned = meta[["synthetic_seed", "row_id"]].merge(
        old[["synthetic_seed", "row_id", "target_true", "ensemble_prediction"]],
        on=["synthetic_seed", "row_id"],
        how="left",
        validate="one_to_one",
        sort=False,
    )
    if aligned.isna().any().any() or not np.allclose(aligned["target_true"], y):
        raise ValueError("Текущий ensemble OOF не совпадает с training samples")
    return aligned["ensemble_prediction"].to_numpy(dtype=float)


def run_candidate(
    name: str,
    params: dict,
    X: pd.DataFrame,
    y: np.ndarray,
    groups: pd.Series,
    baseline: np.ndarray,
    base_prediction: np.ndarray,
) -> dict:
    residual_target = y - baseline
    oof_residual = np.full(len(X), np.nan)
    fold_ids = np.full(len(X), -1, dtype=int)
    splitter = GroupKFold(n_splits=min(5, groups.nunique()))

    for fold, (train_idx, val_idx) in enumerate(splitter.split(X, groups=groups)):
        fold_ids[val_idx] = fold
        model = ExtraTreesRegressor(
            # Короткий screening. Полную модель имеет смысл обучать только
            # после подтверждённого OOF-прироста.
            n_estimators=90,
            random_state=RANDOM_SEED + fold,
            n_jobs=-1,
            bootstrap=False,
            **params,
        )
        model.fit(X.iloc[train_idx], residual_target[train_idx])
        oof_residual[val_idx] = model.predict(X.iloc[val_idx])

    best = None
    for residual_weight in np.linspace(0.0, 1.4, 29):
        extra_prediction = baseline + residual_weight * oof_residual
        for blend_weight in np.linspace(0.0, 1.0, 21):
            candidate = (
                (1.0 - blend_weight) * base_prediction
                + blend_weight * extra_prediction
            )
            candidate = np.clip(candidate, -1.0, 1.0)
            score = rmse(y, candidate)
            if best is None or score < best["oof_rmse"]:
                best = {
                    "name": name,
                    "params": params,
                    "oof_rmse": score,
                    "residual_weight": float(residual_weight),
                    "blend_weight": float(blend_weight),
                    "prediction": candidate,
                }

    assert best is not None
    folds = []
    improved = 0
    for fold in sorted(np.unique(fold_ids)):
        val = fold_ids == fold
        base_rmse = rmse(y[val], base_prediction[val])
        new_rmse = rmse(y[val], best["prediction"][val])
        improved += int(new_rmse < base_rmse)
        folds.append(
            {
                "fold": int(fold),
                "base_rmse": base_rmse,
                "candidate_rmse": new_rmse,
                "improvement": base_rmse - new_rmse,
            }
        )
    best["improved_folds"] = improved
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

    candidates = [
        ("extra_leaf3_f045", {"min_samples_leaf": 3, "max_features": 0.45}),
        ("extra_leaf6_f060", {"min_samples_leaf": 6, "max_features": 0.60}),
    ]
    results = []
    for name, params in candidates:
        result = run_candidate(name, params, X, y, groups, baseline, base)
        results.append(result)
        print(
            f"{name}: rmse={result['oof_rmse']:.6f} "
            f"delta={rmse(y, base)-result['oof_rmse']:+.6f} "
            f"folds={result['improved_folds']}/5 "
            f"rw={result['residual_weight']:.2f} blend={result['blend_weight']:.2f}"
        )

    best = min(results, key=lambda item: item["oof_rmse"])
    output = {
        "base_oof_rmse": rmse(y, base),
        "best": {k: v for k, v in best.items() if k != "prediction"},
        "candidates": [
            {k: v for k, v in result.items() if k != "prediction"}
            for result in sorted(results, key=lambda item: item["oof_rmse"])
        ],
    }
    OUTPUT_PATH.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
    print("\nBEST")
    print(json.dumps(output["best"], ensure_ascii=False, indent=2))
    print(f"Сохранено: {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
