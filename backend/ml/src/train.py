"""Обучение модели на реалистичных synthetic gaps и GroupKFold-валидация."""
from __future__ import annotations

import json

import pandas as pd

from config import (
    DATE_COL,
    METRICS_PATH,
    MODEL_PATH,
    OOF_PATH,
    RANDOM_SEED,
    SYNTHETIC_MASK_RATE,
    SYNTHETIC_SEEDS,
    TRAIN_PATH,
)
from modeling import build_training_samples, cross_validate, fit_bundle, save_bundle


def main() -> None:
    train = pd.read_csv(TRAIN_PATH, parse_dates=[DATE_COL])
    print(f"Train: {train.shape[0]:,} строк, {train.anon_polygon_id.nunique()} полигонов")
    print(
        "Создаём synthetic gaps: "
        f"rate={SYNTHETIC_MASK_RATE:.0%}, seeds={SYNTHETIC_SEEDS}"
    )

    X, y, groups, meta = build_training_samples(
        train,
        seeds=SYNTHETIC_SEEDS,
        mask_rate=SYNTHETIC_MASK_RATE,
    )
    print(f"Матрица обучения: {X.shape[0]:,} строк x {X.shape[1]} признаков")

    metrics, oof = cross_validate(X, y, groups, meta, seed=RANDOM_SEED)
    print("\nOOF-результаты (полигоны не пересекаются между train/validation):")
    print(f"  Среднее двух соседей RMSE: {metrics['baseline_mean_rmse']:.5f}")
    print(f"  Линейная интерполяция RMSE: {metrics['baseline_linear_rmse']:.5f}")
    print(f"  Гибридный baseline RMSE:    {metrics['baseline_rmse']:.5f}")
    print(f"  Baseline + ML RMSE:         {metrics['oof_rmse']:.5f}")
    print(f"  Ожидаемый GapScore:         {metrics['oof_gapscore']:.2f} / 30")
    print(f"  Вес ML-коррекции:           {metrics['residual_weight']:.2f}")

    bundle = fit_bundle(X, y, meta, metrics, seed=RANDOM_SEED)
    save_bundle(bundle, MODEL_PATH)

    METRICS_PATH.parent.mkdir(parents=True, exist_ok=True)
    METRICS_PATH.write_text(
        json.dumps(metrics, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    oof_table = meta.copy()
    oof_table["target_true"] = y.to_numpy()
    oof_table["prediction"] = oof
    oof_table["absolute_error"] = (oof_table["target_true"] - oof_table["prediction"]).abs()
    oof_table[DATE_COL] = pd.to_datetime(oof_table[DATE_COL]).dt.strftime("%Y-%m-%d")
    oof_table.to_csv(OOF_PATH, index=False)

    print(f"\nМодель: {MODEL_PATH}")
    print(f"Метрики: {METRICS_PATH}")
    print(f"OOF-прогнозы: {OOF_PATH}")


if __name__ == "__main__":
    main()
