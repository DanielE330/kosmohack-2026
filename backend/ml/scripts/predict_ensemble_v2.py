"""Submission v2: 70% текущего HGB-ансамбля + 30% ExtraTrees."""

import sys
from pathlib import Path

import joblib
import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from config import DATE_COL, GAP_FLAG_COL, ID_COL, MODEL_PATH, TEST_PATH, TRAIN_PATH  # noqa: E402
from extra_trees_model import predict_private_gaps_extra_trees  # noqa: E402
from wheat_model import predict_private_gaps_ensemble  # noqa: E402


WHEAT_MODEL_PATH = ROOT / "models/wheat_gap_model.joblib"
EXTRA_MODEL_PATH = ROOT / "models/extra_trees_gap_model.joblib"
SUBMISSION_PATH = ROOT / "submission_ensemble_v2.csv"
TARGET_OUTPUT_COL = "primary_ndvi_true"


def main() -> None:
    required_models = [MODEL_PATH, WHEAT_MODEL_PATH, EXTRA_MODEL_PATH]
    missing = [str(path) for path in required_models if not path.exists()]
    if missing:
        raise FileNotFoundError(f"Не найдены модели: {missing}")

    train = pd.read_csv(TRAIN_PATH, parse_dates=[DATE_COL])
    private = pd.read_csv(TEST_PATH, parse_dates=[DATE_COL])
    global_bundle = joblib.load(MODEL_PATH)
    wheat_bundle = joblib.load(WHEAT_MODEL_PATH)
    extra_bundle = joblib.load(EXTRA_MODEL_PATH)

    base = predict_private_gaps_ensemble(
        private=private,
        global_bundle=global_bundle,
        wheat_bundle=wheat_bundle,
        reference=train,
        prediction_col="base_prediction",
    )
    extra = predict_private_gaps_extra_trees(
        private=private,
        bundle=extra_bundle,
        reference=train,
        prediction_col="extra_prediction",
    )
    result = base.merge(
        extra,
        on=[ID_COL, DATE_COL],
        how="inner",
        validate="one_to_one",
    )
    blend = float(extra_bundle["blend_weight"])
    result[TARGET_OUTPUT_COL] = (
        (1.0 - blend) * result["base_prediction"]
        + blend * result["extra_prediction"]
    )
    if extra_bundle.get("clip_predictions", True):
        result[TARGET_OUTPUT_COL] = np.clip(result[TARGET_OUTPUT_COL], -1.0, 1.0)

    submission = result[[ID_COL, DATE_COL, TARGET_OUTPUT_COL]].copy()
    expected_rows = int(private[GAP_FLAG_COL].eq(True).sum())
    if len(submission) != expected_rows:
        raise AssertionError(f"Ожидалось {expected_rows}, получено {len(submission)}")
    if submission[TARGET_OUTPUT_COL].isna().any():
        raise AssertionError("В submission есть NaN")
    if submission.duplicated([ID_COL, DATE_COL]).any():
        raise AssertionError("В submission есть дубликаты")

    submission.to_csv(SUBMISSION_PATH, index=False, encoding="utf-8")
    print(f"submission: {SUBMISSION_PATH} ({len(submission):,} строк)")
    print(submission[TARGET_OUTPUT_COL].describe().to_string())
    print(f"ExtraTrees blend weight: {blend:.2f}")


if __name__ == "__main__":
    main()
