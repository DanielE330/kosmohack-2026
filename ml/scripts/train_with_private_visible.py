"""Дообучение глобальной модели на видимых точках тестовых полигонов.

Модели из `train.py` учатся только на `train_dataset.csv` и ни разу не видят
20 полигонов из `test_features.csv` — отсюда основной разрыв между OOF по
train (лёгкая задача: те же полигоны, другие даты) и реальным приватным
скором (новые полигоны). При этом видимые точки тестовых полигонов
(`is_synthetic_gap = False`, `primary_ndvi` заполнен) выданы всем открыто,
и учиться на них законно.

Утечки нет: у настоящих контрольных строк `primary_ndvi` пуст изначально,
а строки отложенной проверки здесь дополнительно затираются (иначе они
попали бы в обучение и как цель, и как значение соседа, что завысило бы
оценку).
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from config import (  # noqa: E402
    DATE_COL,
    RANDOM_SEED,
    SYNTHETIC_MASK_RATE,
    SYNTHETIC_SEEDS,
    TARGET_COL,
    TEST_PATH,
    TRAIN_PATH,
)
from modeling import build_training_samples, cross_validate, fit_bundle, save_bundle  # noqa: E402
from private_adaptation import make_disjoint_calibration_masks  # noqa: E402

OUTPUT_MODEL_PATH = ROOT / "models/gap_model_with_private.joblib"


def _lightgbm_estimator(seed: int):
    """Алгоритмический сосед HGB: другой способ строить деревья (leaf-wise,
    гистограммный) даёт менее коррелированные ошибки, чем просто другой сид
    того же алгоритма — источник настоящей диверсификации для мультимодели."""
    from lightgbm import LGBMRegressor

    return LGBMRegressor(
        objective="regression",
        n_estimators=600,
        learning_rate=0.03,
        num_leaves=23,
        min_child_samples=24,
        reg_lambda=0.35,
        subsample=0.85,
        subsample_freq=1,
        colsample_bytree=0.85,
        random_state=seed,
        verbosity=-1,
    )


ESTIMATOR_FACTORIES = {
    "hgb": None,  # значение по умолчанию из modeling._new_estimator
    "lightgbm": _lightgbm_estimator,
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--seeds",
        type=int,
        nargs="+",
        default=list(SYNTHETIC_SEEDS),
        help="сиды синтетических масок; больше сидов = больше обучающих примеров",
    )
    parser.add_argument("--out", type=Path, default=OUTPUT_MODEL_PATH)
    parser.add_argument(
        "--model-seed",
        type=int,
        default=RANDOM_SEED,
        help="сид самого регрессора; разные сиды дают участников мультимодели",
    )
    parser.add_argument(
        "--algo",
        choices=sorted(ESTIMATOR_FACTORIES),
        default="hgb",
        help="алгоритм регрессора остатка (hgb по умолчанию, lightgbm — для"
        " алгоритмической диверсификации мультимодели)",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    train = pd.read_csv(TRAIN_PATH, parse_dates=[DATE_COL])
    private = pd.read_csv(TEST_PATH, parse_dates=[DATE_COL])

    # Прячем ВСЕ калибровочные маски, а не только отложенную: на масках 0-2
    # подгоняются коррекции v4/v5/v7, и если модель видела их метки при
    # обучении, остатки на них окажутся заниженными, а масштаб коррекции —
    # недооценённым. Ценой ~60% видимых точек получаем честную цепочку.
    masks = make_disjoint_calibration_masks(private, n_masks=4, rate=0.15, seed=2026)
    hidden = np.zeros(len(private), dtype=bool)
    for mask in masks:
        hidden |= mask
    private_for_training = private.copy()
    private_for_training.loc[hidden, TARGET_COL] = np.nan
    print(
        f"Тестовых полигонов: {private['anon_polygon_id'].nunique()}, "
        f"видимых точек: {int(private[TARGET_COL].notna().sum()):,}, "
        f"скрыто под калибровку и проверку: {int(hidden.sum()):,}"
    )

    combined = pd.concat([train, private_for_training], ignore_index=True, sort=False)
    print(f"Обучающая таблица: {len(combined):,} строк, "
          f"{combined['anon_polygon_id'].nunique()} полигонов")

    X, y, groups, meta = build_training_samples(
        combined, seeds=tuple(args.seeds), mask_rate=SYNTHETIC_MASK_RATE
    )
    print(
        f"Синтетические сиды: {args.seeds}, сид модели: {args.model_seed}, "
        f"алгоритм: {args.algo}"
    )
    print(f"Матрица обучения: {X.shape[0]:,} строк x {X.shape[1]} признаков")

    factory = ESTIMATOR_FACTORIES[args.algo]
    kwargs = {} if factory is None else {"estimator_factory": factory}
    metrics, _ = cross_validate(X, y, groups, meta, seed=args.model_seed, **kwargs)
    print(f"  Гибридный baseline RMSE: {metrics['baseline_rmse']:.5f}")
    print(f"  Baseline + ML RMSE:      {metrics['oof_rmse']:.5f}")
    print(f"  Ожидаемый GapScore:      {metrics['oof_gapscore']:.2f} / 30")

    bundle = fit_bundle(X, y, meta, metrics, seed=args.model_seed, **kwargs)
    save_bundle(bundle, args.out)
    print(f"\nМодель: {args.out}")


if __name__ == "__main__":
    main()
