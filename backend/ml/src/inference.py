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

# Платформа реально требует эту колонку (проверено на submission_ensemble_v9,
# который команда уже успешно проверила) — в самом тексте ТЗ написано
# "primary_ndvi_pred" (см. страницу "ФОРМАТ SUBMISSION.CSV"), но платформа на
# практике ждёт "primary_ndvi_true". Внутри модуля используется прежнее имя
# ("предсказание", не "истина") — переименование только на границе экспорта.
PLATFORM_TARGET_COL = "primary_ndvi_true"

# Порядок колонок тоже важен для платформы — сверено построчно с
# submission_h6_residual.csv (файл, который уже подтверждённо прошёл
# проверку): date, primary_ndvi_true, anon_polygon_id. НЕ тот порядок,
# что в тексте ТЗ (anon_polygon_id, date, primary_ndvi_pred).
PLATFORM_COLUMN_ORDER = [DATE_COL, PLATFORM_TARGET_COL, ID_COL]


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
    submission = submission.rename(columns={"primary_ndvi_pred": PLATFORM_TARGET_COL})

    assert len(submission) == expected_rows
    assert submission[PLATFORM_TARGET_COL].notna().all()
    assert not submission.duplicated([ID_COL, DATE_COL]).any()

    submission = submission[PLATFORM_COLUMN_ORDER]
    assert list(submission.columns) == PLATFORM_COLUMN_ORDER

    submission.to_csv(SUBMISSION_PATH, index=False, encoding="utf-8")
    print(f"submission.csv: {SUBMISSION_PATH} ({len(submission):,} строк)")
    print(submission[PLATFORM_TARGET_COL].describe().to_string())


if __name__ == "__main__":
    main()
