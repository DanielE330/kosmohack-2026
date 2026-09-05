"""Формирование submission.csv для контрольных synthetic gaps."""
from __future__ import annotations

import joblib
import pandas as pd

from config import (
    DATE_COL,
    GAP_FLAG_COL,
    ID_COL,
    MODEL_PATH,
    SUBMISSION_PATH,
    TEST_PATH,
    TRAIN_PATH,
)
from modeling import predict_private_gaps


def main() -> None:
    if not MODEL_PATH.exists():
        raise FileNotFoundError(
            f"Модель не найдена: {MODEL_PATH}. Сначала запусти: python src/train.py"
        )

    train = pd.read_csv(TRAIN_PATH, parse_dates=[DATE_COL])
    private = pd.read_csv(TEST_PATH, parse_dates=[DATE_COL])
    if GAP_FLAG_COL not in private:
        raise ValueError(f"В private_features отсутствует колонка {GAP_FLAG_COL}")

    expected_rows = int(private[GAP_FLAG_COL].sum())
    bundle = joblib.load(MODEL_PATH)
    submission = predict_private_gaps(private, bundle, reference=train)

    assert len(submission) == expected_rows
    assert submission["primary_ndvi_pred"].notna().all()
    assert not submission.duplicated([ID_COL, DATE_COL]).any()
    assert list(submission.columns) == [ID_COL, DATE_COL, "primary_ndvi_pred"]

    submission.to_csv(SUBMISSION_PATH, index=False, encoding="utf-8")
    print(f"submission.csv: {SUBMISSION_PATH} ({len(submission):,} строк)")
    print(submission["primary_ndvi_pred"].describe().to_string())


if __name__ == "__main__":
    main()
