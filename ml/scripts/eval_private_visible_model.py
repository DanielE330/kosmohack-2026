"""Стоит ли дообучать глобальную модель на видимых точках тестовых полигонов.

Сравнивает две сборки v3, отличающиеся только глобальной моделью:
  * `models/gap_model.joblib`              — обучена лишь на train_dataset;
  * `models/gap_model_with_private.joblib` — плюс видимые точки 20 тестовых
    полигонов (все четыре калибровочные маски при обучении спрятаны).

Оценка честная: маска 3 не участвовала ни в обучении модели, ни в подгонке
коррекций. Ничего из `private_test_ground_truth.csv` не используется.
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
PRIVATE_MODEL_PATH = ROOT / "models/gap_model_with_private.joblib"


def rmse(truth: np.ndarray, prediction: np.ndarray) -> float:
    return float(np.sqrt(np.mean((truth - prediction) ** 2)))


def gapscore(value: float) -> float:
    return round(30 * max(0.0, 1.0 - value / 0.10), 2)


def evaluate(label: str, global_bundle: dict, train, private) -> dict[str, float]:
    bundles = V3Bundles(
        global_bundle=global_bundle,
        wheat_bundle=joblib.load(ROOT / "models/wheat_gap_model.joblib"),
        extra_bundle=joblib.load(ROOT / "models/extra_trees_gap_model.joblib"),
        reweighted_bundle=joblib.load(ROOT / "models/reweighted_hgb_model.joblib"),
    )
    print(f"[{label}] строим калибровочную таблицу...", flush=True)
    table = build_private_calibration_table(
        private, bundles, reference=train, n_masks=4, rate=0.15, seed=2026
    )
    fit_rows = table[table["calibration_mask"] != HOLDOUT_MASK].copy()
    holdout = table[table["calibration_mask"] == HOLDOUT_MASK].copy()
    truth = holdout["target_true"].to_numpy(dtype=float)

    scores: dict[str, float] = {}
    scores["одна глобальная модель"] = rmse(
        truth, holdout["global_prediction"].to_numpy(dtype=float)
    )
    scores["v3 (ансамбль 4 моделей)"] = rmse(
        truth, holdout["v3_prediction"].to_numpy(dtype=float)
    )
    local = apply_polygon_calibration(holdout, fit_rows)[0]
    scores["v4 (+ калибровка по полигону)"] = rmse(
        truth, local["v4_prediction"].to_numpy(dtype=float)
    )
    with_global = apply_global_calibration(local, fit_rows)
    scores["v5 (+ глобальный Ridge)"] = rmse(
        truth, with_global["v5_prediction"].to_numpy(dtype=float)
    )
    with_tree = apply_nonlinear_global_calibration(local, fit_rows)
    scores["v7 (+ Ridge и ExtraTrees)"] = rmse(
        truth, with_tree["v7_prediction"].to_numpy(dtype=float)
    )
    return scores


def main() -> None:
    train = pd.read_csv(TRAIN_PATH, parse_dates=[DATE_COL])
    private = pd.read_csv(TEST_PATH, parse_dates=[DATE_COL])
    if not PRIVATE_MODEL_PATH.exists():
        raise FileNotFoundError(
            f"Сначала запустите scripts/train_with_private_visible.py "
            f"(нет {PRIVATE_MODEL_PATH})"
        )

    baseline = evaluate("train-only", joblib.load(MODEL_PATH), train, private)
    adapted = evaluate("+private-visible", joblib.load(PRIVATE_MODEL_PATH), train, private)

    width = max(len(name) for name in baseline)
    print(f"\n{'':<{width}}  {'train-only':>12}  {'+private':>12}  {'дельта':>8}")
    for name in baseline:
        before, after = baseline[name], adapted[name]
        print(
            f"{name:<{width}}  {before:>12.5f}  {after:>12.5f}  {after - before:>+8.5f}"
        )
    print(
        f"\nGapScore v7: {gapscore(baseline['v7 (+ Ridge и ExtraTrees)'])} -> "
        f"{gapscore(adapted['v7 (+ Ridge и ExtraTrees)'])}"
    )


if __name__ == "__main__":
    main()
