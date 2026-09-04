"""Восстановление пропусков `primary_ndvi`.

`interpolate` — чистая функция без зависимости от ORM/БД, поэтому её
использует и веб-сервис (`fill_gaps`), и отдельный batch-инференс
(`inference/run_inference.py`). Это baseline для хакатона (линейная
интерполяция между ближайшими известными наблюдениями по времени) —
замените на Savitzky-Golay/Whittaker/ML-модель, не меняя сигнатуру
`(dates, values) -> predicted`, и вызывающий код останется рабочим.
"""

from __future__ import annotations

from datetime import date


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
    непустого `primary_ndvi_pred` в каждой точке ряда)."""
    ordered = sorted(observations, key=lambda o: o.date)
    dates = [o.date for o in ordered]
    values = [o.primary_ndvi for o in ordered]
    predicted = interpolate(dates, values)
    for obs, pred in zip(ordered, predicted):
        obs.primary_ndvi_pred = pred
