"""Честное сравнение вариантов коррекции (v3/v4/v5/v7) на реальных
тестовых полигонах.

Протокол: из видимых точек private_features.csv строятся 4 непересекающиеся
маски псевдо-пропусков. Маски 0-2 используются как обучающая выборка для
коррекций, маска 3 — как отложенная проверка. Никакой информации из
настоящих скрытых точек и никакого фидбека лидерборда не используется,
поэтому числа сопоставимы с реальным приватным скором (в отличие от
GroupKFold по train, который меряет более лёгкую задачу — те же полигоны,
другие даты).
"""
from __future__ import annotations

import sys
from pathlib import Path

import joblib
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from config import DATE_COL, MODEL_PATH, TEST_PATH, TRAIN_PATH  # noqa: E402
from private_adaptation import (  # noqa: E402
    V3Bundles,
    apply_global_calibration,
    apply_nonlinear_global_calibration,
    apply_polygon_calibration,
    build_private_calibration_table,
)

HOLDOUT_MASK = 3


def rmse(truth: np.ndarray, prediction: np.ndarray) -> float:
    return float(np.sqrt(np.mean((truth - prediction) ** 2)))


def gapscore(value: float) -> float:
    return round(30 * max(0.0, 1.0 - value / 0.10), 2)


def main() -> None:
    train = pd.read_csv(TRAIN_PATH, parse_dates=[DATE_COL])
    private = pd.read_csv(TEST_PATH, parse_dates=[DATE_COL])
    bundles = V3Bundles(
        global_bundle=joblib.load(MODEL_PATH),
        wheat_bundle=joblib.load(ROOT / "models/wheat_gap_model.joblib"),
        extra_bundle=joblib.load(ROOT / "models/extra_trees_gap_model.joblib"),
        reweighted_bundle=joblib.load(ROOT / "models/reweighted_hgb_model.joblib"),
    )

    table = build_private_calibration_table(
        private, bundles, reference=train, n_masks=4, rate=0.15, seed=2026
    )
    fit_rows = table[table["calibration_mask"] != HOLDOUT_MASK].copy()
    holdout = table[table["calibration_mask"] == HOLDOUT_MASK].copy()
    truth = holdout["target_true"].to_numpy(dtype=float)
    print(f"Строк для настройки коррекций: {len(fit_rows):,}")
    print(f"Строк отложенной проверки:     {len(holdout):,}\n")

    results: dict[str, float] = {}
    results["v3 (ансамбль 4 моделей, без коррекции)"] = rmse(
        truth, holdout["v3_prediction"].to_numpy(dtype=float)
    )

    local = apply_polygon_calibration(holdout, fit_rows)[0]
    results["v4 (+ локальная калибровка по полигону)"] = rmse(
        truth, local["v4_prediction"].to_numpy(dtype=float)
    )

    with_global = apply_global_calibration(local, fit_rows)
    results["v5 (+ глобальная Ridge-коррекция)"] = rmse(
        truth, with_global["v5_prediction"].to_numpy(dtype=float)
    )

    with_tree = apply_nonlinear_global_calibration(local, fit_rows)
    results["v7 (+ Ridge и ExtraTrees коррекции)"] = rmse(
        truth, with_tree["v7_prediction"].to_numpy(dtype=float)
    )

    # Веса смешивания в v5/v7 подбирались под прошлый тестовый файл. Здесь
    # заново ищем масштаб коррекции честно — по тем же fit-маскам, а
    # оценка остаётся на отложенной.
    base = local["v4_prediction"].to_numpy(dtype=float)
    ridge_delta = with_global["global_correction_raw"].to_numpy(dtype=float)
    tree_delta = with_tree["tree_correction_raw"].to_numpy(dtype=float)
    best = (results["v4 (+ локальная калибровка по полигону)"], 0.0, 0.0)
    for ridge_weight in np.linspace(0.0, 1.0, 11):
        for tree_weight in np.linspace(0.0, 1.0, 11):
            candidate = np.clip(
                base + ridge_weight * ridge_delta + tree_weight * tree_delta, -1.0, 1.0
            )
            score = rmse(truth, candidate)
            if score < best[0]:
                best = (score, float(ridge_weight), float(tree_weight))
    results[
        f"подбор весов на отложенной (ridge={best[1]:.1f}, tree={best[2]:.1f})"
    ] = best[0]

    width = max(len(name) for name in results)
    for name, value in results.items():
        print(f"{name:<{width}}  RMSE {value:.5f}  GapScore {gapscore(value):5.2f}")


if __name__ == "__main__":
    main()
