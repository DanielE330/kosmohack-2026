"""Валидация и обучение private-distribution weighted HGB."""

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from config import DATE_COL, RANDOM_SEED, REPORTS_DIR, SYNTHETIC_MASK_RATE, SYNTHETIC_SEEDS, TEST_PATH, TRAIN_PATH  # noqa: E402
from global_model import build_training_samples  # noqa: E402
from reweighted_hgb_model import (  # noqa: E402
    cross_validate_reweighted_hgb,
    fit_reweighted_bundle,
    make_crop_sample_weights,
    save_reweighted_bundle,
)


BASE_OOF_PATH = REPORTS_DIR / "extra_trees_oof_predictions.csv"
MODEL_PATH = ROOT / "models/reweighted_hgb_model.joblib"
METRICS_PATH = REPORTS_DIR / "reweighted_hgb_metrics.json"
OOF_PATH = REPORTS_DIR / "reweighted_hgb_oof_predictions.csv"


def load_base_oof(meta: pd.DataFrame, y: pd.Series) -> np.ndarray:
    old = pd.read_csv(BASE_OOF_PATH)
    aligned = meta[["synthetic_seed", "row_id"]].merge(
        old[["synthetic_seed", "row_id", "target_true", "ensemble_prediction"]],
        on=["synthetic_seed", "row_id"], how="left", validate="one_to_one", sort=False
    )
    if aligned.isna().any().any() or not np.allclose(aligned["target_true"], y):
        raise ValueError("Не удалось выровнять ExtraTrees ensemble OOF")
    return aligned["ensemble_prediction"].to_numpy(dtype=float)


def main() -> None:
    train = pd.read_csv(TRAIN_PATH, parse_dates=[DATE_COL])
    private = pd.read_csv(TEST_PATH, parse_dates=[DATE_COL])
    X, y, groups, meta = build_training_samples(
        train, seeds=SYNTHETIC_SEEDS, mask_rate=SYNTHETIC_MASK_RATE
    )
    base_oof = load_base_oof(meta, y)
    sample_weights, crop_weight_map = make_crop_sample_weights(meta, private)
    print("Crop weights:", crop_weight_map)
    metrics, ensemble_oof, alternative_oof = cross_validate_reweighted_hgb(
        X, y, groups, meta, sample_weights, base_oof, crop_weight_map, RANDOM_SEED
    )
    print("\nReweighted HGB:")
    print(f"  v2 OOF:             {metrics['base_oof_rmse']:.6f}")
    print(f"  v3 OOF:             {metrics['ensemble_oof_rmse']:.6f}")
    print(f"  weighted v2 OOF:    {metrics['base_weighted_oof_rmse']:.6f}")
    print(f"  weighted v3 OOF:    {metrics['ensemble_weighted_oof_rmse']:.6f}")
    print(f"  Reweighted weight:  {metrics['blend_weight']:.2f}")
    print(f"  Weighted folds:     {metrics['improved_weighted_folds']}/5")
    print(f"  Accepted:           {metrics['accepted']}")

    bundle = fit_reweighted_bundle(
        X, y, meta, sample_weights, metrics, seed=RANDOM_SEED
    )
    save_reweighted_bundle(bundle, MODEL_PATH)
    METRICS_PATH.write_text(json.dumps(metrics, ensure_ascii=False, indent=2), encoding="utf-8")
    report = meta.copy().reset_index(drop=True)
    report["target_true"] = y.to_numpy(dtype=float)
    report["base_prediction"] = base_oof
    report["reweighted_prediction"] = alternative_oof
    report["ensemble_prediction"] = ensemble_oof
    report.to_csv(OOF_PATH, index=False)
    print("\nСоздано:")
    print(MODEL_PATH)
    print(METRICS_PATH)
    print(OOF_PATH)


if __name__ == "__main__":
    main()
