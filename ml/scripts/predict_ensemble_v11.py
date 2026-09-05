"""Submission v11: мультимодель из дообученных глобальных моделей + коррекции.

Отличие от v7: базовый прогноз даёт не ансамбль «глобальная + три специалиста,
обученные лишь на train_dataset», а среднее нескольких глобальных моделей,
дообученных на видимых точках самих тестовых полигонов (разные наборы
синтетических масок, разные сиды регрессора). Поверх — та же цепочка
самообучаемых коррекций v4 (по полигону) и v7 (Ridge + ExtraTrees).

Ничего из private_test_ground_truth.csv не используется: обучение и калибровка
опираются только на открыто выданные видимые точки test_features.csv.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import joblib
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from config import DATE_COL, GAP_FLAG_COL, ID_COL, TEST_PATH, TRAIN_PATH  # noqa: E402
from private_adaptation import (  # noqa: E402
    V3Bundles,
    apply_nonlinear_global_calibration,
    apply_polygon_calibration,
    build_private_calibration_table,
    predict_v3_components,
)

MEMBER_PATHS = {
    "private_a": ROOT / "models/gap_model_private_a.joblib",
    "private_b": ROOT / "models/gap_model_private_b.joblib",
    "private_c": ROOT / "models/gap_model_private_c.joblib",
}
SUBMISSION_PATH = ROOT / "submission_ensemble_v11.csv"
SUMMARY_PATH = ROOT / "reports/private_adaptation_v11.json"
DIAGNOSTICS_PATH = ROOT / "reports/private_adaptation_v11.csv"
OUTPUT_COL = "primary_ndvi_true"


def member_bundles(path: Path) -> V3Bundles:
    """Специалисты нужны лишь как заглушки: базой служит global_prediction."""
    return V3Bundles(
        global_bundle=joblib.load(path),
        wheat_bundle=joblib.load(ROOT / "models/wheat_gap_model.joblib"),
        extra_bundle=joblib.load(ROOT / "models/extra_trees_gap_model.joblib"),
        reweighted_bundle=joblib.load(ROOT / "models/reweighted_hgb_model.joblib"),
    )


def averaged(frames: list[pd.DataFrame]) -> pd.DataFrame:
    """Среднее global_prediction участников, записанное как база v3."""
    reference = frames[0]
    for frame in frames[1:]:
        if not frame["_private_row"].equals(reference["_private_row"]):
            raise AssertionError("Участники вернули строки в разном порядке")
    stacked = np.column_stack(
        [frame["global_prediction"].to_numpy(dtype=float) for frame in frames]
    )
    result = reference.copy()
    result["v3_prediction"] = np.clip(stacked.mean(axis=1), -1.0, 1.0)
    return result


def main() -> None:
    missing = [str(path) for path in MEMBER_PATHS.values() if not path.exists()]
    if missing:
        raise FileNotFoundError(f"Не найдены участники мультимодели: {missing}")

    train = pd.read_csv(TRAIN_PATH, parse_dates=[DATE_COL])
    private = pd.read_csv(TEST_PATH, parse_dates=[DATE_COL])
    actual_gap = private[GAP_FLAG_COL].fillna(False).astype(bool).to_numpy()

    actual_frames: list[pd.DataFrame] = []
    calibration_frames: list[pd.DataFrame] = []
    for tag, path in MEMBER_PATHS.items():
        bundles = member_bundles(path)
        print(f"[{tag}] прогноз настоящих пропусков...", flush=True)
        actual_frames.append(
            predict_v3_components(private, actual_gap, bundles, reference=train)
        )
        print(f"[{tag}] калибровочные псевдо-пропуски...", flush=True)
        calibration_frames.append(
            build_private_calibration_table(
                private, bundles, reference=train, n_masks=4, rate=0.15, seed=2026
            )
        )

    actual = averaged(actual_frames)
    calibration = averaged(calibration_frames)
    print(f"Calibration rows: {len(calibration):,}", flush=True)

    v4, local_diagnostics = apply_polygon_calibration(actual, calibration)
    v11 = apply_nonlinear_global_calibration(v4, calibration)

    submission = v11[[ID_COL, DATE_COL]].copy()
    submission[OUTPUT_COL] = v11["v7_prediction"].to_numpy(dtype=float)
    submission[DATE_COL] = submission[DATE_COL].dt.strftime("%Y-%m-%d")

    expected = int(actual_gap.sum())
    if len(submission) != expected or submission[OUTPUT_COL].isna().any():
        raise AssertionError("Неверное число строк или NaN в v11 submission")
    if submission.duplicated([ID_COL, DATE_COL]).any():
        raise AssertionError("В v11 submission есть дубликаты")
    if not np.isfinite(submission[OUTPUT_COL]).all():
        raise AssertionError("В v11 submission есть inf")

    # Порядок сверен с submission_h6_residual.csv — файлом, подтверждённо
    # прошедшим проверку платформы (не тот порядок, что в тексте ТЗ).
    submission = submission[[DATE_COL, OUTPUT_COL, ID_COL]]
    submission.to_csv(SUBMISSION_PATH, index=False, encoding="utf-8")

    v11[
        [ID_COL, DATE_COL, "crop_type", "v3_prediction", "v4_prediction", "v7_prediction"]
    ].to_csv(DIAGNOSTICS_PATH, index=False, encoding="utf-8")
    summary = {
        "submission_rows": len(submission),
        "calibration_rows": len(calibration),
        "members": sorted(MEMBER_PATHS),
        "polygons": int(private[ID_COL].nunique()),
        "locally_adapted_polygons": int(local_diagnostics["status"].eq("adapted").sum()),
    }
    SUMMARY_PATH.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    print(f"submission: {SUBMISSION_PATH} ({len(submission):,} строк)")
    print(submission[OUTPUT_COL].describe().to_string())
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
