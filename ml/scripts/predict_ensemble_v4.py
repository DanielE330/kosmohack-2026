"""Submission v4: v3 plus self-supervised per-private-polygon calibration."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import joblib
import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from config import DATE_COL, GAP_FLAG_COL, ID_COL, MODEL_PATH, TEST_PATH, TRAIN_PATH  # noqa: E402
from private_adaptation import (  # noqa: E402
    V3Bundles,
    apply_polygon_calibration,
    build_private_calibration_table,
    predict_v3_components,
)


WHEAT_MODEL_PATH = ROOT / "models/wheat_gap_model.joblib"
EXTRA_MODEL_PATH = ROOT / "models/extra_trees_gap_model.joblib"
REWEIGHTED_MODEL_PATH = ROOT / "models/reweighted_hgb_model.joblib"
SUBMISSION_PATH = ROOT / "submission_ensemble_v4.csv"
CALIBRATION_REPORT_PATH = ROOT / "reports/private_adaptation_v4.csv"
SUMMARY_PATH = ROOT / "reports/private_adaptation_v4.json"
OUTPUT_COL = "primary_ndvi_true"


def main() -> None:
    paths = [MODEL_PATH, WHEAT_MODEL_PATH, EXTRA_MODEL_PATH, REWEIGHTED_MODEL_PATH]
    missing = [str(path) for path in paths if not path.exists()]
    if missing:
        raise FileNotFoundError(f"Не найдены модели: {missing}")

    train = pd.read_csv(TRAIN_PATH, parse_dates=[DATE_COL])
    private = pd.read_csv(TEST_PATH, parse_dates=[DATE_COL])
    bundles = V3Bundles(
        global_bundle=joblib.load(MODEL_PATH),
        wheat_bundle=joblib.load(WHEAT_MODEL_PATH),
        extra_bundle=joblib.load(EXTRA_MODEL_PATH),
        reweighted_bundle=joblib.load(REWEIGHTED_MODEL_PATH),
    )

    actual_gap = private[GAP_FLAG_COL].fillna(False).astype(bool).to_numpy()
    print("Строим базовый v3 для настоящих private gaps...", flush=True)
    actual = predict_v3_components(
        private, actual_gap, bundles, reference=train
    )

    print("Создаём локальные pseudo-gaps на видимых private значениях...", flush=True)
    calibration = build_private_calibration_table(
        private,
        bundles,
        reference=train,
        n_masks=4,
        rate=0.15,
        seed=2026,
    )
    print(f"Calibration rows: {len(calibration):,}", flush=True)

    adapted, diagnostics = apply_polygon_calibration(actual, calibration)
    submission = adapted[[ID_COL, DATE_COL]].copy()
    submission[OUTPUT_COL] = adapted["v4_prediction"].to_numpy(dtype=float)
    submission[DATE_COL] = pd.to_datetime(submission[DATE_COL]).dt.strftime("%Y-%m-%d")

    expected = int(actual_gap.sum())
    if len(submission) != expected or submission[OUTPUT_COL].isna().any():
        raise AssertionError("Неверное число строк или NaN в v4 submission")
    if submission.duplicated([ID_COL, DATE_COL]).any():
        raise AssertionError("В v4 submission есть дубликаты")
    if not np.isfinite(submission[OUTPUT_COL]).all():
        raise AssertionError("В v4 submission есть inf")

    submission.to_csv(SUBMISSION_PATH, index=False, encoding="utf-8")
    diagnostics.to_csv(CALIBRATION_REPORT_PATH, index=False, encoding="utf-8")
    summary = {
        "submission_rows": len(submission),
        "calibration_rows": len(calibration),
        "polygons": int(private[ID_COL].nunique()),
        "adapted_polygons": int(diagnostics["status"].eq("adapted").sum()),
        "fallback_polygons": int(diagnostics["status"].eq("fallback_v3").sum()),
        "mean_abs_v4_minus_v3": float(
            np.mean(np.abs(adapted["v4_prediction"] - adapted["v3_prediction"]))
        ),
        "max_abs_v4_minus_v3": float(
            np.max(np.abs(adapted["v4_prediction"] - adapted["v3_prediction"]))
        ),
    }
    SUMMARY_PATH.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    print(f"submission: {SUBMISSION_PATH} ({len(submission):,} строк)")
    print(submission[OUTPUT_COL].describe().to_string())
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(f"diagnostics: {CALIBRATION_REPORT_PATH}")


if __name__ == "__main__":
    main()
