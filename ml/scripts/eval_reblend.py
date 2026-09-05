"""Перевзвешивание ансамбля под дообученную глобальную модель.

Веса блендинга (`blend_weight` в bundle-ах wheat/extra/reweighted) подбирались
по OOF train при старой глобальной модели. После дообучения глобальной модели
на видимых точках тестовых полигонов она стала сильнее специалистов, и старые
веса тянут ансамбль вниз (v3 хуже, чем одна глобальная модель).

Здесь веса подбираются заново — на калибровочных масках 0-2, оценка на маске 3.
Модель этих масок при обучении не видела, ground truth не используется.

Калибровочная таблица кэшируется: её построение занимает минуты.
"""
from __future__ import annotations

import sys
from itertools import product
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
CACHE_DIR = ROOT / "reports/calibration_cache"
COMPONENTS = [
    "global_prediction",
    "wheat_prediction",
    "extra_trees_prediction",
    "reweighted_prediction",
]


def rmse(truth: np.ndarray, prediction: np.ndarray) -> float:
    return float(np.sqrt(np.mean((truth - prediction) ** 2)))


def gapscore(value: float) -> float:
    return round(30 * max(0.0, 1.0 - value / 0.10), 2)


def calibration_table(tag: str, global_path: Path, train, private) -> pd.DataFrame:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cache = CACHE_DIR / f"{tag}.pkl"
    if cache.exists():
        print(f"[{tag}] беру из кэша {cache.name}", flush=True)
        return pd.read_pickle(cache)
    print(f"[{tag}] строю калибровочную таблицу...", flush=True)
    bundles = V3Bundles(
        global_bundle=joblib.load(global_path),
        wheat_bundle=joblib.load(ROOT / "models/wheat_gap_model.joblib"),
        extra_bundle=joblib.load(ROOT / "models/extra_trees_gap_model.joblib"),
        reweighted_bundle=joblib.load(ROOT / "models/reweighted_hgb_model.joblib"),
    )
    table = build_private_calibration_table(
        private, bundles, reference=train, n_masks=4, rate=0.15, seed=2026
    )
    table.to_pickle(cache)
    return table


def search_weights(fit_rows: pd.DataFrame) -> np.ndarray:
    """Симплексный перебор неотрицательных весов с шагом 0.1."""
    truth = fit_rows["target_true"].to_numpy(dtype=float)
    matrix = fit_rows[COMPONENTS].to_numpy(dtype=float)
    steps = np.arange(0, 11)
    best_score, best_weights = np.inf, None
    for combo in product(steps, repeat=len(COMPONENTS) - 1):
        if sum(combo) > 10:
            continue
        weights = np.array([*combo, 10 - sum(combo)], dtype=float) / 10.0
        score = rmse(truth, np.clip(matrix @ weights, -1.0, 1.0))
        if score < best_score:
            best_score, best_weights = score, weights
    return best_weights


def main() -> None:
    train = pd.read_csv(TRAIN_PATH, parse_dates=[DATE_COL])
    private = pd.read_csv(TEST_PATH, parse_dates=[DATE_COL])

    for tag, path in (("train_only", MODEL_PATH), ("with_private", PRIVATE_MODEL_PATH)):
        table = calibration_table(tag, path, train, private)
        fit_rows = table[table["calibration_mask"] != HOLDOUT_MASK].copy()
        holdout = table[table["calibration_mask"] == HOLDOUT_MASK].copy()
        truth = holdout["target_true"].to_numpy(dtype=float)

        weights = search_weights(fit_rows)
        print(f"\n=== {tag} ===")
        print("подобранные веса: " + ", ".join(
            f"{name.replace('_prediction', '')}={weight:.1f}"
            for name, weight in zip(COMPONENTS, weights)
        ))

        for frame in (fit_rows, holdout):
            frame["v3_prediction"] = np.clip(
                frame[COMPONENTS].to_numpy(dtype=float) @ weights, -1.0, 1.0
            )

        results = {
            "v3 со старыми весами": rmse(
                truth, table[table["calibration_mask"] == HOLDOUT_MASK][
                    "v3_prediction"
                ].to_numpy(dtype=float)
            ),
            "v3 с новыми весами": rmse(truth, holdout["v3_prediction"].to_numpy(dtype=float)),
        }
        local = apply_polygon_calibration(holdout, fit_rows)[0]
        results["v4 (+ полигон)"] = rmse(truth, local["v4_prediction"].to_numpy(dtype=float))
        with_global = apply_global_calibration(local, fit_rows)
        results["v5 (+ Ridge)"] = rmse(truth, with_global["v5_prediction"].to_numpy(dtype=float))
        with_tree = apply_nonlinear_global_calibration(local, fit_rows)
        results["v7 (+ Ridge и ExtraTrees)"] = rmse(
            truth, with_tree["v7_prediction"].to_numpy(dtype=float)
        )

        width = max(len(name) for name in results)
        for name, value in results.items():
            print(f"  {name:<{width}}  RMSE {value:.5f}  GapScore {gapscore(value):5.2f}")


if __name__ == "__main__":
    main()
