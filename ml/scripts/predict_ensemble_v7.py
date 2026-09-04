"""Submission v7: v4 plus Ridge and ExtraTrees private residual corrections."""
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
    DEFAULT_GLOBAL_BLEND,
    GLOBAL_BLEND_BY_CROP,
    NONLINEAR_BLEND_BY_CROP,
    V3Bundles,
    apply_nonlinear_global_calibration,
    apply_polygon_calibration,
    build_private_calibration_table,
    predict_v3_components,
)


WHEAT_MODEL_PATH = ROOT / "models/wheat_gap_model.joblib"
EXTRA_MODEL_PATH = ROOT / "models/extra_trees_gap_model.joblib"
REWEIGHTED_MODEL_PATH = ROOT / "models/reweighted_hgb_model.joblib"
SUBMISSION_PATH = ROOT / "submission_ensemble_v7.csv"
DIAGNOSTICS_PATH = ROOT / "reports/private_adaptation_v7.csv"
SUMMARY_PATH = ROOT / "reports/private_adaptation_v7.json"
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
    print("Строим компоненты v3 для настоящих private gaps...", flush=True)
    actual = predict_v3_components(private, actual_gap, bundles, reference=train)
    print("Создаём private pseudo-gaps для двух корректоров...", flush=True)
    calibration = build_private_calibration_table(
        private,
        bundles,
        reference=train,
        n_masks=4,
        rate=0.15,
        seed=2026,
    )
    print(f"Calibration rows: {len(calibration):,}", flush=True)

    v4, local_diagnostics = apply_polygon_calibration(actual, calibration)
    v7 = apply_nonlinear_global_calibration(v4, calibration)
    submission = v7[[ID_COL, DATE_COL]].copy()
    submission[OUTPUT_COL] = v7["v7_prediction"].to_numpy(dtype=float)
    submission[DATE_COL] = submission[DATE_COL].dt.strftime("%Y-%m-%d")

    expected = int(actual_gap.sum())
    if len(submission) != expected or submission[OUTPUT_COL].isna().any():
        raise AssertionError("Неверное число строк или NaN в v7 submission")
    if submission.duplicated([ID_COL, DATE_COL]).any():
        raise AssertionError("В v7 submission есть дубликаты")
    if not np.isfinite(submission[OUTPUT_COL]).all():
        raise AssertionError("В v7 submission есть inf")

    submission.to_csv(SUBMISSION_PATH, index=False, encoding="utf-8")
    diagnostics = v7[
        [
            ID_COL,
            DATE_COL,
            "crop_type",
            "v3_prediction",
            "v4_prediction",
            "global_correction_raw",
            "global_blend_weight",
            "tree_correction_raw",
            "tree_blend_weight",
            "v7_prediction",
        ]
    ].copy()
    diagnostics.to_csv(DIAGNOSTICS_PATH, index=False, encoding="utf-8")

    summary = {
        "submission_rows": len(submission),
        "calibration_rows": len(calibration),
        "polygons": int(private[ID_COL].nunique()),
        "locally_adapted_polygons": int(
            local_diagnostics["status"].eq("adapted").sum()
        ),
        "nonlinear_blend_by_crop": NONLINEAR_BLEND_BY_CROP,
        "mean_abs_v7_minus_v5": float(
            np.mean(np.abs(v7["v7_prediction"] - (
                v7["v4_prediction"]
                + v7["crop_type"].map(GLOBAL_BLEND_BY_CROP)
                .fillna(DEFAULT_GLOBAL_BLEND)
                * v7["global_correction_raw"]
            )))
        ),
    }
    SUMMARY_PATH.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"submission: {SUBMISSION_PATH} ({len(submission):,} строк)")
    print(submission[OUTPUT_COL].describe().to_string())
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(f"diagnostics: {DIAGNOSTICS_PATH}")


if __name__ == "__main__":
    main()
