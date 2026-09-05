"""Создание отдельного submission глобальной + wheat specialist моделей."""
from __future__ import annotations

import joblib
import pandas as pd

from config import (
    DATE_COL,
    GAP_FLAG_COL,
    ID_COL,
    MODEL_PATH,
    ROOT_DIR,
    TEST_PATH,
    TRAIN_PATH,
)
from wheat_specialist import predict_private_gaps_ensemble


WHEAT_MODEL_PATH = ROOT_DIR / "models/wheat_gap_model.joblib"
ENSEMBLE_SUBMISSION_PATH = ROOT_DIR / "submission_wheat_ensemble.csv"
PLATFORM_TARGET_COL = "primary_ndvi_true"


def main() -> None:
    if not MODEL_PATH.exists():
        raise FileNotFoundError(
            f"Не найдена global-модель {MODEL_PATH}. Запусти python src/train.py"
        )
    if not WHEAT_MODEL_PATH.exists():
        raise FileNotFoundError(
            f"Не найдена wheat-модель {WHEAT_MODEL_PATH}. "
            "Запусти python src/train_wheat_experiment.py"
        )

    train = pd.read_csv(TRAIN_PATH, parse_dates=[DATE_COL])
    private = pd.read_csv(TEST_PATH, parse_dates=[DATE_COL])
    if GAP_FLAG_COL not in private:
        raise ValueError(f"В private_features отсутствует {GAP_FLAG_COL}")

    global_bundle = joblib.load(MODEL_PATH)
    wheat_bundle = joblib.load(WHEAT_MODEL_PATH)
    submission = predict_private_gaps_ensemble(
        private=private,
        global_bundle=global_bundle,
        wheat_bundle=wheat_bundle,
        reference=train,
        prediction_col=PLATFORM_TARGET_COL,
    )

    expected_rows = int(private[GAP_FLAG_COL].eq(True).sum())
    if len(submission) != expected_rows:
        raise AssertionError(f"Ожидалось {expected_rows}, получено {len(submission)}")
    if submission[PLATFORM_TARGET_COL].isna().any():
        raise AssertionError("В submission есть NaN")
    if submission.duplicated([ID_COL, DATE_COL]).any():
        raise AssertionError("В submission есть дубликаты polygon + date")
    if list(submission.columns) != [ID_COL, DATE_COL, PLATFORM_TARGET_COL]:
        raise AssertionError(f"Неверные колонки: {list(submission.columns)}")

    submission.to_csv(ENSEMBLE_SUBMISSION_PATH, index=False, encoding="utf-8")
    print(
        f"submission: {ENSEMBLE_SUBMISSION_PATH} "
        f"({len(submission):,} строк)"
    )
    print(submission[PLATFORM_TARGET_COL].describe().to_string())
    print(
        f"Specialist blend weight: {wheat_bundle.get('blend_weight', 0.0):.2f}"
    )


if __name__ == "__main__":
    main()
