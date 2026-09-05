"""Мультимодельная архитектура на дообученных глобальных моделях.

Старые специалисты (wheat/extra_trees/reweighted) обучены только на
train_dataset. После того как глобальная модель дообучилась на видимых точках
тестовых полигонов, честный подбор весов отдаёт ей 0.7, а reweighted получает
ровно 0 — специалисты перестали нести полезный сигнал.

Здесь они заменяются на несколько дообученных глобальных моделей, обученных на
разных наборах синтетических масок и с разными сидами регрессора. Усреднение
таких участников снижает дисперсию, не жертвуя адаптацией к тестовым
полигонам.

Протокол честный: маски 0-2 -- подбор весов и коррекций, маска 3 -- оценка,
ни одна из них не была видна моделям при обучении. Ground truth платформы не
используется.
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
CACHE_DIR = ROOT / "reports/calibration_cache"
MEMBERS = {
    "private_a": ROOT / "models/gap_model_private_a.joblib",
    "private_b": ROOT / "models/gap_model_private_b.joblib",
    "private_c": ROOT / "models/gap_model_private_c.joblib",
}


def rmse(truth: np.ndarray, prediction: np.ndarray) -> float:
    return float(np.sqrt(np.mean((truth - prediction) ** 2)))


def gapscore(value: float) -> float:
    return round(30 * max(0.0, 1.0 - value / 0.10), 2)


def calibration_table(tag: str, global_path: Path, train, private) -> pd.DataFrame:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cache = CACHE_DIR / f"{tag}.pkl"
    if cache.exists():
        print(f"[{tag}] беру из кэша", flush=True)
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


def search_weights(matrix: np.ndarray, truth: np.ndarray, steps: int = 10) -> np.ndarray:
    """Симплексный перебор неотрицательных весов, сумма равна единице."""
    grid = np.arange(0, steps + 1)
    best_score, best_weights = np.inf, None
    for combo in product(grid, repeat=matrix.shape[1] - 1):
        if sum(combo) > steps:
            continue
        weights = np.array([*combo, steps - sum(combo)], dtype=float) / steps
        score = rmse(truth, np.clip(matrix @ weights, -1.0, 1.0))
        if score < best_score:
            best_score, best_weights = score, weights
    return best_weights


def correction_chain(base: np.ndarray, tables: dict, key: str) -> dict[str, float]:
    """Прогоняет базовый прогноз через v4/v5/v7 и возвращает RMSE каждого шага."""
    fit_rows, holdout, truth = tables["fit"], tables["holdout"], tables["truth"]
    fit_rows = fit_rows.copy()
    holdout = holdout.copy()
    fit_rows["v3_prediction"] = tables["fit_base"]
    holdout["v3_prediction"] = base

    scores = {f"{key}: база": rmse(truth, np.clip(base, -1.0, 1.0))}
    local = apply_polygon_calibration(holdout, fit_rows)[0]
    scores[f"{key}: v4 (+ полигон)"] = rmse(
        truth, local["v4_prediction"].to_numpy(dtype=float)
    )
    with_global = apply_global_calibration(local, fit_rows)
    scores[f"{key}: v5 (+ Ridge)"] = rmse(
        truth, with_global["v5_prediction"].to_numpy(dtype=float)
    )
    with_tree = apply_nonlinear_global_calibration(local, fit_rows)
    scores[f"{key}: v7 (+ Ridge и ExtraTrees)"] = rmse(
        truth, with_tree["v7_prediction"].to_numpy(dtype=float)
    )
    return scores


def main() -> None:
    train = pd.read_csv(TRAIN_PATH, parse_dates=[DATE_COL])
    private = pd.read_csv(TEST_PATH, parse_dates=[DATE_COL])

    missing = [str(path) for path in MEMBERS.values() if not path.exists()]
    if missing:
        raise FileNotFoundError(
            "Сначала обучите участников через scripts/train_with_private_visible.py "
            f"--out ...: не найдены {missing}"
        )

    tables = {
        tag: calibration_table(tag, path, train, private)
        for tag, path in MEMBERS.items()
    }
    reference = tables["private_a"]
    is_holdout = reference["calibration_mask"].eq(HOLDOUT_MASK).to_numpy()
    truth = reference.loc[is_holdout, "target_true"].to_numpy(dtype=float)

    # Все таблицы построены на одних и тех же масках и в одном порядке строк,
    # иначе усреднять по позициям нельзя.
    for tag, table in tables.items():
        if not table["_private_row"].equals(reference["_private_row"]):
            raise AssertionError(f"Порядок строк в таблице {tag} не совпадает с эталоном")

    member_holdout = np.column_stack(
        [table.loc[is_holdout, "global_prediction"].to_numpy(dtype=float)
         for table in tables.values()]
    )
    member_fit = np.column_stack(
        [table.loc[~is_holdout, "global_prediction"].to_numpy(dtype=float)
         for table in tables.values()]
    )

    print("\nОтдельные участники на отложенной маске:")
    for index, tag in enumerate(tables):
        print(f"  {tag:<12} RMSE {rmse(truth, member_holdout[:, index]):.5f}")

    chain_input = {
        "fit": reference[~is_holdout],
        "holdout": reference[is_holdout],
        "truth": truth,
    }

    results: dict[str, float] = {}

    # 1. Равное усреднение участников -- самый устойчивый вариант.
    chain_input["fit_base"] = member_fit.mean(axis=1)
    results.update(correction_chain(member_holdout.mean(axis=1), chain_input, "среднее"))

    # 2. Веса участников, подобранные на масках 0-2.
    fit_truth = reference.loc[~is_holdout, "target_true"].to_numpy(dtype=float)
    weights = search_weights(member_fit, fit_truth)
    print("\nПодобранные веса участников: " + ", ".join(
        f"{tag}={weight:.1f}" for tag, weight in zip(tables, weights)
    ))
    chain_input["fit_base"] = member_fit @ weights
    results.update(correction_chain(member_holdout @ weights, chain_input, "веса"))

    width = max(len(name) for name in results)
    print()
    for name, value in results.items():
        print(f"{name:<{width}}  RMSE {value:.5f}  GapScore {gapscore(value):5.2f}")
    print("\nОриентир: одиночная дообученная модель + v7 = 0.06619")


if __name__ == "__main__":
    main()
