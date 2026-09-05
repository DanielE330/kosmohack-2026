"""HGB, обученный с весами под feature-распределение private gaps."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.model_selection import GroupKFold


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from config import DATE_COL, RANDOM_SEED, SYNTHETIC_MASK_RATE, SYNTHETIC_SEEDS, TRAIN_PATH, TEST_PATH  # noqa: E402
from gap_features import build_gap_features  # noqa: E402
from global_model import _new_estimator, build_training_samples, rmse  # noqa: E402


BASE_PATH = ROOT / "reports/extra_trees_oof_predictions.csv"
OUTPUT_PATH = ROOT / "reports/reweighted_hgb_search.json"


def weighted_rmse(y: np.ndarray, pred: np.ndarray, weights: np.ndarray) -> float:
    return float(np.sqrt(np.average((y - pred) ** 2, weights=weights)))


def ratio_weights(
    oof_rows: pd.DataFrame,
    private_rows: pd.DataFrame,
    columns: list[str],
) -> np.ndarray:
    oof_share = oof_rows.groupby(columns, dropna=False).size() / len(oof_rows)
    private_share = private_rows.groupby(columns, dropna=False).size() / len(private_rows)
    ratio = (private_share / oof_share).replace([np.inf, -np.inf], np.nan).fillna(0)
    ratio = ratio.clip(lower=0.20, upper=4.0).to_dict()
    result = []
    for values in oof_rows[columns].itertuples(index=False, name=None):
        key = values[0] if len(columns) == 1 else tuple(values)
        result.append(ratio.get(key, 0.20))
    weights = np.asarray(result, dtype=float)
    return weights / weights.mean()


def main() -> None:
    train = pd.read_csv(TRAIN_PATH, parse_dates=[DATE_COL])
    private = pd.read_csv(TEST_PATH, parse_dates=[DATE_COL])
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

    oof_rows = pd.DataFrame({
        "crop": meta.crop_type.astype(str),
        "month": pd.to_datetime(meta.date).dt.month,
        "gap": pd.cut(X.target_span_days, [0, 5, 10, 20, 40, np.inf], labels=["0-5", "6-10", "11-20", "21-40", "40+"]).astype(str),
    })

    train_context = train.copy(); train_context["_source"] = "train"
    private_context = private.copy(); private_context["_source"] = "private"
    combined = pd.concat([train_context, private_context], ignore_index=True, sort=False)
    query = combined._source.eq("private") & combined.is_synthetic_gap.eq(True)
    built = build_gap_features(combined, query)
    private_rows = pd.DataFrame({
        "crop": built.meta.crop_type.astype(str).to_numpy(),
        "month": pd.to_datetime(built.meta.date).dt.month.to_numpy(),
        "gap": pd.cut(built.features.target_span_days, [0, 5, 10, 20, 40, np.inf], labels=["0-5", "6-10", "11-20", "21-40", "40+"]).astype(str).to_numpy(),
    })

    schemes = {
        "crop": ["crop"],
        "crop_month": ["crop", "month"],
        "crop_month_gap": ["crop", "month", "gap"],
    }
    results = []
    splitter = GroupKFold(n_splits=min(5, groups.nunique()))
    splits = list(splitter.split(X, y_series, groups))
    for scheme, columns in schemes.items():
        sample_weights = ratio_weights(oof_rows, private_rows, columns)
        oof_residual = np.full(len(X), np.nan)
        fold_ids = np.full(len(X), -1, dtype=int)
        for fold, (train_idx, val_idx) in enumerate(splits):
            fold_ids[val_idx] = fold
            model = _new_estimator(RANDOM_SEED + 700 + fold)
            model.fit(
                X.iloc[train_idx], residual[train_idx],
                sample_weight=sample_weights[train_idx],
            )
            oof_residual[val_idx] = model.predict(X.iloc[val_idx])

        best = None
        for rw in np.linspace(0.0, 1.4, 29):
            alternative = baseline + rw * oof_residual
            for blend in np.linspace(0.0, 1.0, 21):
                pred = np.clip((1.0 - blend) * base + blend * alternative, -1.0, 1.0)
                score = weighted_rmse(y, pred, sample_weights)
                if best is None or score < best["weighted_oof_rmse"]:
                    best = {
                        "weighted_oof_rmse": score,
                        "unweighted_oof_rmse": rmse(y, pred),
                        "residual_weight": float(rw),
                        "blend_weight": float(blend),
                        "prediction": pred,
                    }
        assert best is not None
        folds=[]; improved=0
        for fold in sorted(np.unique(fold_ids)):
            val=fold_ids==fold
            before=weighted_rmse(y[val],base[val],sample_weights[val])
            after=weighted_rmse(y[val],best['prediction'][val],sample_weights[val])
            improved += int(after < before)
            folds.append({'fold':int(fold),'base_weighted_rmse':before,'candidate_weighted_rmse':after,'improvement':before-after})
        result={
            'scheme':scheme,
            'columns':columns,
            'base_weighted_rmse':weighted_rmse(y,base,sample_weights),
            **{k:v for k,v in best.items() if k!='prediction'},
            'improved_folds':improved,
            'folds':folds,
        }
        results.append(result)
        print(json.dumps(result,ensure_ascii=False,indent=2))

    best=min(results,key=lambda x:x['weighted_oof_rmse'])
    output={'base_unweighted_rmse':rmse(y,base),'best':best,'candidates':results}
    OUTPUT_PATH.write_text(json.dumps(output,ensure_ascii=False,indent=2),encoding='utf-8')
    print('\nBEST',json.dumps(best,ensure_ascii=False,indent=2))


if __name__ == '__main__':
    main()
