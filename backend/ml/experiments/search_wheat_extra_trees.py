"""Проверяет wheat-only ExtraTrees поверх принятого ensemble v2."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.model_selection import GroupKFold


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from config import DATE_COL, RANDOM_SEED, SYNTHETIC_MASK_RATE, SYNTHETIC_SEEDS, TRAIN_PATH  # noqa: E402
from extra_trees_model import _new_extra_trees  # noqa: E402
from global_model import build_training_samples, rmse  # noqa: E402


BASE_PATH = ROOT / "reports/extra_trees_oof_predictions.csv"
OUTPUT_PATH = ROOT / "reports/wheat_extra_trees_search.json"


def main() -> None:
    train = pd.read_csv(TRAIN_PATH, parse_dates=[DATE_COL])
    X, y_series, groups, meta = build_training_samples(
        train, seeds=SYNTHETIC_SEEDS, mask_rate=SYNTHETIC_MASK_RATE
    )
    X = X.replace([np.inf, -np.inf], np.nan).reset_index(drop=True)
    y_series = y_series.reset_index(drop=True)
    groups = groups.reset_index(drop=True)
    meta = meta.reset_index(drop=True)
    y = y_series.to_numpy(dtype=float)

    old = pd.read_csv(BASE_PATH)
    aligned = meta[["synthetic_seed", "row_id"]].merge(
        old[["synthetic_seed", "row_id", "target_true", "ensemble_prediction"]],
        on=["synthetic_seed", "row_id"], how="left", validate="one_to_one", sort=False
    )
    if aligned.isna().any().any() or not np.allclose(aligned.target_true, y):
        raise ValueError("Не удалось выровнять v2 OOF")
    base = aligned.ensemble_prediction.to_numpy(dtype=float)

    baseline = meta.baseline.astype(float).to_numpy()
    baseline = np.where(np.isfinite(baseline), baseline, float(y_series.median()))
    residual = y - baseline
    wheat = meta.crop_type.fillna("unknown").astype(str).eq("озимая пшеница").to_numpy()
    oof_residual = np.full(len(X), np.nan)
    fold_ids = np.full(len(X), -1, dtype=int)

    splitter = GroupKFold(n_splits=min(5, groups.nunique()))
    for fold, (train_idx, val_idx) in enumerate(splitter.split(X, y_series, groups)):
        fold_ids[val_idx] = fold
        tr = train_idx[wheat[train_idx]]
        va = val_idx[wheat[val_idx]]
        model = _new_extra_trees(RANDOM_SEED + 500 + fold)
        model.fit(X.iloc[tr], residual[tr])
        oof_residual[va] = model.predict(X.iloc[va])

    valid = wheat & np.isfinite(oof_residual)
    best = None
    for rw in np.linspace(0.0, 1.4, 29):
        special = baseline + rw * oof_residual
        for blend in np.linspace(0.0, 1.0, 21):
            pred = base.copy()
            pred[valid] = (1.0 - blend) * base[valid] + blend * special[valid]
            pred = np.clip(pred, -1.0, 1.0)
            score = rmse(y, pred)
            if best is None or score < best["oof_rmse"]:
                best = {
                    "oof_rmse": score,
                    "residual_weight": float(rw),
                    "blend_weight": float(blend),
                    "prediction": pred,
                    "special": special,
                }
    assert best is not None
    folds=[]; improved=0
    for fold in sorted(np.unique(fold_ids)):
        va=fold_ids==fold
        before=rmse(y[va],base[va]); after=rmse(y[va],best['prediction'][va])
        improved += int(after < before)
        folds.append({'fold':int(fold),'base_rmse':before,'candidate_rmse':after,'improvement':before-after})
    output={
        'base_oof_rmse':rmse(y,base),
        'wheat_rows':int(valid.sum()),
        'wheat_base_rmse':rmse(y[valid],base[valid]),
        'wheat_specialist_rmse':rmse(y[valid],best['special'][valid]),
        'ensemble_oof_rmse':best['oof_rmse'],
        'absolute_improvement':rmse(y,base)-best['oof_rmse'],
        'residual_weight':best['residual_weight'],
        'blend_weight':best['blend_weight'],
        'improved_folds':improved,
        'folds':folds,
    }
    OUTPUT_PATH.write_text(json.dumps(output,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(output,ensure_ascii=False,indent=2))


if __name__ == '__main__':
    main()
