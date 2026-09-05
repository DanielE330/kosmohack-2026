"""OOF-эксперимент и обучение specialist-модели для озимой пшеницы."""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from config import (
    DATE_COL,
    OOF_PATH,
    RANDOM_SEED,
    REPORTS_DIR,
    ROOT_DIR,
    SYNTHETIC_MASK_RATE,
    SYNTHETIC_SEEDS,
    TRAIN_PATH,
)
from modeling import build_training_samples
from wheat_specialist import (
    cross_validate_wheat_specialist,
    fit_wheat_bundle,
    save_wheat_bundle,
)


WHEAT_MODEL_PATH = ROOT_DIR / "models/wheat_gap_model.joblib"
WHEAT_METRICS_PATH = REPORTS_DIR / "wheat_validation_metrics.json"
WHEAT_OOF_PATH = REPORTS_DIR / "wheat_oof_predictions.csv"


def load_aligned_global_oof(meta: pd.DataFrame, y: pd.Series) -> np.ndarray:
    """Выравнивает существующие global OOF по seed + исходному row_id."""
    if not OOF_PATH.exists():
        raise FileNotFoundError(
            f"Не найден {OOF_PATH}. Сначала запусти: python src/train.py"
        )

    old_oof = pd.read_csv(OOF_PATH)
    required = {"synthetic_seed", "row_id", "target_true", "prediction"}
    missing = required.difference(old_oof.columns)
    if missing:
        raise ValueError(f"В global OOF отсутствуют колонки: {sorted(missing)}")

    lookup = old_oof[
        ["synthetic_seed", "row_id", "target_true", "prediction"]
    ].copy()
    if lookup.duplicated(["synthetic_seed", "row_id"]).any():
        raise ValueError("В global OOF есть дубликаты seed + row_id")

    aligned = meta[["synthetic_seed", "row_id"]].merge(
        lookup,
        on=["synthetic_seed", "row_id"],
        how="left",
        validate="one_to_one",
        sort=False,
    )
    if aligned[["target_true", "prediction"]].isna().any().any():
        raise ValueError(
            "Global OOF не соответствует текущим seeds/mask_rate. "
            "Снова запусти python src/train.py"
        )
    if not np.allclose(
        aligned["target_true"].to_numpy(dtype=float),
        y.to_numpy(dtype=float),
        equal_nan=False,
    ):
        raise ValueError("Порядок/target global OOF не совпал с текущей выборкой")
    return aligned["prediction"].to_numpy(dtype=float)


def main() -> None:
    train = pd.read_csv(TRAIN_PATH, parse_dates=[DATE_COL])
    print(f"Train: {len(train):,} строк")
    print("Собираем те же synthetic gaps, что использовались global-моделью...")

    X, y, groups, meta = build_training_samples(
        train,
        seeds=SYNTHETIC_SEEDS,
        mask_rate=SYNTHETIC_MASK_RATE,
    )
    global_oof = load_aligned_global_oof(meta, y)

    metrics, ensemble_oof, wheat_oof = cross_validate_wheat_specialist(
        X=X,
        y=y,
        groups=groups,
        meta=meta,
        global_oof_prediction=global_oof,
        seed=RANDOM_SEED,
    )

    print("\nРезультат wheat-эксперимента:")
    print(f"  Global OOF RMSE:      {metrics['global_oof_rmse']:.6f}")
    print(f"  Ensemble OOF RMSE:    {metrics['ensemble_oof_rmse']:.6f}")
    print(f"  Улучшение:             {metrics['absolute_improvement']:.6f}")
    print(f"  Wheat global RMSE:     {metrics['wheat_global_rmse']:.6f}")
    print(f"  Wheat specialist RMSE: {metrics['wheat_specialist_rmse']:.6f}")
    print(f"  Wheat ensemble RMSE:   {metrics['wheat_ensemble_rmse']:.6f}")
    print(f"  Вес specialist:        {metrics['wheat_blend_weight']:.2f}")
    print(f"  Принят:                {metrics['accepted']}")

    bundle = fit_wheat_bundle(X, y, meta, metrics, seed=RANDOM_SEED)
    save_wheat_bundle(bundle, WHEAT_MODEL_PATH)

    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    WHEAT_METRICS_PATH.write_text(
        json.dumps(metrics, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    report = meta.copy().reset_index(drop=True)
    report["target_true"] = y.to_numpy(dtype=float)
    report["global_prediction"] = global_oof
    report["wheat_prediction"] = wheat_oof
    report["ensemble_prediction"] = ensemble_oof
    report["global_absolute_error"] = np.abs(y.to_numpy(dtype=float) - global_oof)
    report["ensemble_absolute_error"] = np.abs(
        y.to_numpy(dtype=float) - ensemble_oof
    )
    report.to_csv(WHEAT_OOF_PATH, index=False)

    print("\nСоздано:")
    print(WHEAT_MODEL_PATH)
    print(WHEAT_METRICS_PATH)
    print(WHEAT_OOF_PATH)
    if not metrics["accepted"]:
        print(
            "\nSpecialist не улучшил OOF: submission ансамбля будет фактически "
            "равен global-прогнозу. Это нормальный отрицательный эксперимент."
        )


if __name__ == "__main__":
    main()
