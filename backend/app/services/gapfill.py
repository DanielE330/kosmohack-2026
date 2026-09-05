"""Восстановление пропусков `primary_ndvi`.

`interpolate` — чистая функция без зависимости от ORM/БД (линейная
интерполяция между ближайшими известными наблюдениями по времени). Она
остаётся как fallback: используется отдельным batch-инференсом
(`inference/run_inference.py`) и как аварийный откат в `fill_gaps`, если
ML-модель недоступна или не смогла построить прогноз.

`fill_gaps` теперь в первую очередь использует реальную обученную модель
из `backend/ml/` (`app/services/ml_bridge.predict_primary_ndvi` — контракт
`backend/ml/src/pipeline.restore_and_analyze`, обученную на
`backend/ml/data/train_dataset.csv`, OOF RMSE 0.0633 против 0.0886 у
линейной интерполяции, см. `backend/ml/README.md`). Публичная сигнатура
`fill_gaps(observations) -> None` (мутирует `primary_ndvi_pred`) не менялась.
"""

from __future__ import annotations

import logging
from datetime import date

from app.services import ml_bridge

logger = logging.getLogger(__name__)


def interpolate(dates: list[date], values: list[float | None]) -> list[float]:
    n = len(values)
    if n == 0:
        return []

    prev_idx = [-1] * n
    last = -1
    for i in range(n):
        if values[i] is not None:
            last = i
        prev_idx[i] = last

    next_idx = [-1] * n
    nxt = -1
    for i in range(n - 1, -1, -1):
        if values[i] is not None:
            nxt = i
        next_idx[i] = nxt

    predicted = [0.0] * n
    for i in range(n):
        if values[i] is not None:
            predicted[i] = values[i]
            continue
        left, right = prev_idx[i], next_idx[i]
        if left == -1 and right == -1:
            predicted[i] = 0.0
        elif left == -1:
            predicted[i] = values[right]
        elif right == -1:
            predicted[i] = values[left]
        else:
            span = (dates[right] - dates[left]).days or 1
            weight = (dates[i] - dates[left]).days / span
            predicted[i] = values[left] + (values[right] - values[left]) * weight
    return predicted


def fill_gaps(observations: list) -> None:
    """Заполняет `primary_ndvi_pred` у переданных ORM-объектов `NdviObservation`
    (для всех строк, не только пропусков — контракт с фронтендом требует
    непустого `primary_ndvi_pred` в каждой точке ряда).

    Сначала пробует реальную ML-модель (см. модуль docstring); при любой
    проблеме (модель/зависимости недоступны, на вход пришло слишком мало
    точек и т.п.) молча откатывается на линейную интерполяцию, чтобы
    эндпоинты никогда не падали из-за ML."""
    if not observations:
        return
    ordered = sorted(observations, key=lambda o: o.date)

    predicted_map = ml_bridge.predict_primary_ndvi(ordered)
    if predicted_map is not None:
        for obs in ordered:
            obs.primary_ndvi_pred = predicted_map[obs.date]
        return

    logger.info("ML gap-fill недоступен для полигона %s — линейная интерполяция", ordered[0].polygon_id)
    dates = [o.date for o in ordered]
    values = [o.primary_ndvi for o in ordered]
    predicted = interpolate(dates, values)
    for obs, pred in zip(ordered, predicted):
        obs.primary_ndvi_pred = pred
