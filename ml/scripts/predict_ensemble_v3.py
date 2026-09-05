"""Submission v3: v2 ensemble + private-distribution weighted HGB."""

import sys
from pathlib import Path

import joblib
import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from config import DATE_COL, GAP_FLAG_COL, ID_COL, MODEL_PATH, TEST_PATH, TRAIN_PATH  # noqa: E402
from extra_trees_model import predict_private_gaps_extra_trees  # noqa: E402
from reweighted_hgb_model import predict_private_gaps_reweighted  # noqa: E402
from wheat_model import predict_private_gaps_ensemble  # noqa: E402


WHEAT_MODEL_PATH = ROOT / "models/wheat_gap_model.joblib"
EXTRA_MODEL_PATH = ROOT / "models/extra_trees_gap_model.joblib"
REWEIGHTED_MODEL_PATH = ROOT / "models/reweighted_hgb_model.joblib"
SUBMISSION_PATH = ROOT / "submission_ensemble_v3.csv"
OUTPUT_COL = "primary_ndvi_true"


def main() -> None:
    paths = [MODEL_PATH, WHEAT_MODEL_PATH, EXTRA_MODEL_PATH, REWEIGHTED_MODEL_PATH]
    missing = [str(path) for path in paths if not path.exists()]
    if missing:
        raise FileNotFoundError(f"Не найдены модели: {missing}")
    train = pd.read_csv(TRAIN_PATH, parse_dates=[DATE_COL])
    private = pd.read_csv(TEST_PATH, parse_dates=[DATE_COL])
    global_bundle = joblib.load(MODEL_PATH)
    wheat_bundle = joblib.load(WHEAT_MODEL_PATH)
    extra_bundle = joblib.load(EXTRA_MODEL_PATH)
    reweighted_bundle = joblib.load(REWEIGHTED_MODEL_PATH)

    hgb = predict_private_gaps_ensemble(
        private, global_bundle, wheat_bundle, reference=train,
        prediction_col="hgb_prediction",
    )
    extra = predict_private_gaps_extra_trees(
        private, extra_bundle, reference=train,
        prediction_col="extra_prediction",
    )
    reweighted = predict_private_gaps_reweighted(
        private, reweighted_bundle, reference=train,
        prediction_col="reweighted_prediction",
    )
    result = hgb.merge(extra, on=[ID_COL, DATE_COL], validate="one_to_one")
    result = result.merge(reweighted, on=[ID_COL, DATE_COL], validate="one_to_one")

    extra_weight = float(extra_bundle["blend_weight"])
    result["v2_prediction"] = (
        (1.0 - extra_weight) * result["hgb_prediction"]
        + extra_weight * result["extra_prediction"]
    )
    reweighted_weight = float(reweighted_bundle["blend_weight"])
    result[OUTPUT_COL] = (
        (1.0 - reweighted_weight) * result["v2_prediction"]
        + reweighted_weight * result["reweighted_prediction"]
    )
    result[OUTPUT_COL] = np.clip(result[OUTPUT_COL], -1.0, 1.0)
    submission = result[[ID_COL, DATE_COL, OUTPUT_COL]].copy()

    expected = int(private[GAP_FLAG_COL].eq(True).sum())
    if len(submission) != expected or submission[OUTPUT_COL].isna().any():
        raise AssertionError("Неверное число строк или NaN в submission")
    if submission.duplicated([ID_COL, DATE_COL]).any():
        raise AssertionError("В submission есть дубликаты")
    submission.to_csv(SUBMISSION_PATH, index=False, encoding="utf-8")
    print(f"submission: {SUBMISSION_PATH} ({len(submission):,} строк)")
    print(submission[OUTPUT_COL].describe().to_string())
    print(f"ExtraTrees weight: {extra_weight:.2f}")
    print(f"Reweighted HGB weight: {reweighted_weight:.2f}")


if __name__ == "__main__":
    main()
