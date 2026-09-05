"""Проверка гипотезы: взвешивание по ширине пропуска (--span-reweight).

Реальные пропуски private в большинстве однодневные (медиана расстояния до
соседа — 2 дня, 67% с span<=2), а синтетические маски, на которых учится
модель, заметно шире (медиана 7 дней, только 8% с span<=2) — модель может
систематически недооценивать надёжность ближайшего соседа.

Сравнивает одну и ту же модель (те же сиды масок, тот же сид регрессора)
с включённым --span-reweight и без него. Оценка — на калибровочной маске 3,
построенной из реальных дат private (естественно реалистичное распределение
ширины), поэтому корректно отражает эффект гипотезы. Ничего из ground truth
не используется.
"""
from __future__ import annotations

import sys
from pathlib import Path

import joblib
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from config import DATE_COL, TEST_PATH, TRAIN_PATH  # noqa: E402
from private_adaptation import (  # noqa: E402
    V3Bundles,
    apply_global_calibration,
    apply_nonlinear_global_calibration,
    apply_polygon_calibration,
    build_private_calibration_table,
)

HOLDOUT_MASK = 3
CACHE_DIR = ROOT / "reports/calibration_cache"
VARIANTS = {
    "baseline (без reweight)": ("private_a", ROOT / "models/gap_model_private_a.joblib"),
    "span-reweight": ("private_a_reweighted", ROOT / "models/gap_model_private_a_reweighted.joblib"),
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


def main() -> None:
    train = pd.read_csv(TRAIN_PATH, parse_dates=[DATE_COL])
    private = pd.read_csv(TEST_PATH, parse_dates=[DATE_COL])

    missing = [str(path) for _, path in VARIANTS.values() if not path.exists()]
    if missing:
        raise FileNotFoundError(f"Не найдены модели: {missing}")

    for tag, (cache_key, path) in VARIANTS.items():
        table = calibration_table(cache_key, path, train, private)
        fit_rows = table[table["calibration_mask"] != HOLDOUT_MASK].copy()
        holdout = table[table["calibration_mask"] == HOLDOUT_MASK].copy()
        truth = holdout["target_true"].to_numpy(dtype=float)

        results = {}
        results[f"{tag}: одна модель"] = rmse(
            truth, holdout["global_prediction"].to_numpy(dtype=float)
        )
        if "target_span_days" in holdout:
            narrow = holdout["target_span_days"].to_numpy(dtype=float) <= 2
            for label, sel in (("узкие span<=2", narrow), ("широкие span>2", ~narrow)):
                if sel.sum() >= 20:
                    results[f"{tag}: одна модель, {label} (n={int(sel.sum())})"] = rmse(
                        truth[sel], holdout["global_prediction"].to_numpy(dtype=float)[sel]
                    )
        local = apply_polygon_calibration(holdout, fit_rows)[0]
        results[f"{tag}: v4"] = rmse(truth, local["v4_prediction"].to_numpy(dtype=float))
        with_global = apply_global_calibration(local, fit_rows)
        results[f"{tag}: v5"] = rmse(truth, with_global["v5_prediction"].to_numpy(dtype=float))
        with_tree = apply_nonlinear_global_calibration(local, fit_rows)
        results[f"{tag}: v7"] = rmse(truth, with_tree["v7_prediction"].to_numpy(dtype=float))

        width = max(len(name) for name in results)
        for name, value in results.items():
            print(f"  {name:<{width}}  RMSE {value:.5f}  GapScore {gapscore(value):5.2f}")
        print()


if __name__ == "__main__":
    main()
