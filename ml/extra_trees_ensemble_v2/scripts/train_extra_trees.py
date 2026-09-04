"""Валидация и обучение ExtraTrees для ансамбля v2."""

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
    REPORTS_DIR,
    SYNTHETIC_MASK_RATE,
    SYNTHETIC_SEEDS,
    TRAIN_PATH,
)
from extra_trees_model import (  # noqa: E402
    cross_validate_extra_trees,
    fit_extra_trees_bundle,
    save_extra_trees_bundle,
)
from global_model import build_training_samples  # noqa: E402


BASE_OOF_PATH = REPORTS_DIR / "wheat_oof_predictions.csv"
MODEL_PATH = ROOT / "models/extra_trees_gap_model.joblib"
METRICS_PATH = REPORTS_DIR / "extra_trees_validation_metrics.json"
OOF_PATH = REPORTS_DIR / "extra_trees_oof_predictions.csv"


def load_base_oof(meta: pd.DataFrame, y: pd.Series) -> np.ndarray:
    if not BASE_OOF_PATH.exists():
        raise FileNotFoundError(
            f"Не найден {BASE_OOF_PATH}. Сначала запусти python scripts/train_wheat.py"
        )
    old = pd.read_csv(BASE_OOF_PATH)
    needed = {"synthetic_seed", "row_id", "target_true", "ensemble_prediction"}
    missing = needed.difference(old.columns)
    if missing:
        raise ValueError(f"В wheat OOF отсутствуют: {sorted(missing)}")

    aligned = meta[["synthetic_seed", "row_id"]].merge(
        old[list(needed)],
        on=["synthetic_seed", "row_id"],
        how="left",
        validate="one_to_one",
        sort=False,
    )
    if aligned[["target_true", "ensemble_prediction"]].isna().any().any():
        raise ValueError("Не удалось выровнять wheat OOF")
    if not np.allclose(aligned["target_true"], y):
        raise ValueError("Target wheat OOF не совпадает с training samples")
    return aligned["ensemble_prediction"].to_numpy(dtype=float)


def main() -> None:
    train = pd.read_csv(TRAIN_PATH, parse_dates=[DATE_COL])
    print(f"Train: {len(train):,} строк")
    print("Собираем synthetic gaps...")
    X, y, groups, meta = build_training_samples(
        train,
        seeds=SYNTHETIC_SEEDS,
        mask_rate=SYNTHETIC_MASK_RATE,
    )
    base_oof = load_base_oof(meta, y)

    print("Запускаем ExtraTrees GroupKFold...")
    metrics, ensemble_oof, extra_oof = cross_validate_extra_trees(
        X=X,
        y=y,
        groups=groups,
        meta=meta,
        base_oof_prediction=base_oof,
        seed=RANDOM_SEED,
    )
    print("\nExtraTrees experiment:")
    print(f"  Текущий ensemble:  {metrics['base_oof_rmse']:.6f}")
    print(f"  Новый ensemble:    {metrics['ensemble_oof_rmse']:.6f}")
    print(f"  Улучшение:         {metrics['absolute_improvement']:.6f}")
    print(f"  ExtraTrees weight: {metrics['blend_weight']:.2f}")
    print(f"  Улучшено фолдов:   {metrics['improved_folds']}/5")
    print(f"  Принят:            {metrics['accepted']}")

    bundle = fit_extra_trees_bundle(X, y, meta, metrics, seed=RANDOM_SEED)
    save_extra_trees_bundle(bundle, MODEL_PATH)
    METRICS_PATH.write_text(
        json.dumps(metrics, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    report = meta.copy().reset_index(drop=True)
    report["target_true"] = y.to_numpy(dtype=float)
    report["base_prediction"] = base_oof
    report["extra_trees_prediction"] = extra_oof
    report["ensemble_prediction"] = ensemble_oof
    report["absolute_error"] = np.abs(
        report["target_true"] - report["ensemble_prediction"]
    )
    report.to_csv(OOF_PATH, index=False)

    print("\nСоздано:")
    print(MODEL_PATH)
    print(METRICS_PATH)
    print(OOF_PATH)


if __name__ == "__main__":
    main()
