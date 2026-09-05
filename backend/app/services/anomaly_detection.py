"""Детекция и интерпретация аномалий вегетации по Z-score.

Пороги (Z >= -1 — норма, -2 <= Z < -1 — угнетение биомассы, Z < -2 —
критическая аномалия) зафиксированы в ТЗ и продублированы во Flutter
(`frontend/lib/models/ndvi_point.dart`, `ndviStatusForZ`) — менять только
синхронно с фронтендом. `status_for_zscore` эту формулу не трогает.

`explain_anomaly` теперь в первую очередь использует реальный причинный
анализ из `backend/ml/src/anomalies.py` (через `app/services/ml_bridge`) —
heat_and_drought/moisture_deficit/heat_stress/cold_stress/possible_harvest/
weather_or_harvest/sensor_conflict/unconfirmed, с confidence и
`requires_review`, вместо прежней грубой эвристики "осадки+температура за
весь период". Сам факт аномалии (statuses/z-score) ML не пересчитывает —
только объясняет причину уже готового статуса. Эвристика по ERA5 оставлена
как fallback на случай, если ML недоступен. Сигнатура `group_into_periods`
и вызывающий код (`app/ingestion/load_train_dataset.py`,
`app/api/routes/timeseries.py`) не менялись.
"""

from __future__ import annotations

import statistics
from collections import defaultdict

import pandas as pd
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.anomaly import AnomalyPeriod
from app.models.enums import NdviStatus
from app.models.timeseries import NdviObservation
from app.services import ml_bridge

ANOMALOUS_STATUSES = (NdviStatus.suppression, NdviStatus.critical)

_STATUS_TO_ML = {
    NdviStatus.normal: ml_bridge.ML_NORMAL,
    NdviStatus.suppression: ml_bridge.ML_MODERATE,
    NdviStatus.critical: ml_bridge.ML_CRITICAL,
}


def status_for_zscore(z: float) -> NdviStatus:
    if z < -2:
        return NdviStatus.critical
    if z < -1:
        return NdviStatus.suppression
    return NdviStatus.normal


def compute_climatology(observations: list[NdviObservation]) -> dict[int, tuple[float, float, int]]:
    """doy -> (mean, std, кол-во лет наблюдений), по всем известным `primary_ndvi`."""
    by_doy: dict[int, list[float]] = defaultdict(list)
    for obs in observations:
        if obs.primary_ndvi is not None and obs.doy is not None:
            by_doy[obs.doy].append(obs.primary_ndvi)

    result: dict[int, tuple[float, float, int]] = {}
    for doy, values in by_doy.items():
        mean = statistics.mean(values)
        std = statistics.pstdev(values) if len(values) > 1 else 0.0
        result[doy] = (mean, std, len(values))
    return result


def apply_climatology(observations: list[NdviObservation]) -> None:
    """Досчитывает climatology/Z-score/status для строк, у которых их ещё
    нет (например, вручную загруженные наблюдения). Готовые значения
    организаторов (из `train_dataset.csv`) не перезаписывает."""
    climatology = compute_climatology(observations)
    for obs in observations:
        if obs.ndvi_climatology_mean is None and obs.doy in climatology:
            mean, std, n = climatology[obs.doy]
            obs.ndvi_climatology_mean = mean
            obs.ndvi_climatology_std = std
            obs.n_reference_years = n

        value = obs.primary_ndvi if obs.primary_ndvi is not None else obs.primary_ndvi_pred
        if value is not None and obs.ndvi_climatology_mean is not None and obs.ndvi_climatology_std is not None:
            std = obs.ndvi_climatology_std
            z = 0.0 if std == 0 else (value - obs.ndvi_climatology_mean) / std
            obs.ndvi_zscore = z
            obs.status = status_for_zscore(z)


def _explain_anomaly_heuristic(worst: NdviObservation, run: list[NdviObservation]) -> str:
    """Эвристика-заглушка по ERA5 (осадки/температура за весь период) —
    fallback на случай, если ML-интерпретация недоступна."""
    value = worst.primary_ndvi if worst.primary_ndvi is not None else worst.primary_ndvi_pred
    deviation = (value or 0.0) - (worst.ndvi_climatology_mean or 0.0)
    parts = [f"NDVI ниже климатической нормы на {abs(deviation):.2f}"]

    precip = [o.era5_precip_mm for o in run if o.era5_precip_mm is not None]
    temps = [o.era5_temp_c for o in run if o.era5_temp_c is not None]
    if precip and sum(precip) < 5:
        parts.append(f"осадков за период почти не было ({sum(precip):.1f} мм) — вероятна почвенная засуха")
    if temps and (sum(temps) / len(temps)) > 28:
        parts.append(f"средняя температура {sum(temps) / len(temps):.1f}°C — возможен тепловой стресс")
    if len(parts) == 1:
        parts.append("явной метеопричины по ERA5 не выявлено — возможны облачность/помехи сенсора/смена агрофазы")
    return "; ".join(parts) + "."


def explain_anomaly(
    worst: NdviObservation,
    run: list[NdviObservation],
    interpretation: "pd.DataFrame | None" = None,
) -> str:
    """Текстовая интерпретация причины периода аномалии.

    ``interpretation`` — результат `ml_bridge.interpret_anomaly_causes` по
    ВСЕМУ ряду полигона (см. `group_into_periods`), с реальными причинами
    (heat_and_drought, moisture_deficit, ...), confidence и требованием
    проверки. Если для даты ``worst`` там нет надёжной причины (ML недоступен,
    упал, либо `anomaly_reason` пуст), используется старая ERA5-эвристика.
    """
    if interpretation is not None:
        key = worst.date.isoformat()
        if key in interpretation.index:
            row = interpretation.loc[key]
            reason = row.get("anomaly_reason")
            if isinstance(reason, str) and reason:
                parts = [reason]
                confidence = row.get("cause_confidence")
                if confidence is not None and not pd.isna(confidence):
                    parts.append(f"уверенность в причине {float(confidence):.2f}")
                if bool(row.get("requires_review")):
                    parts.append("требуется проверка")
                return "; ".join(parts) + "."

    return _explain_anomaly_heuristic(worst, run)


def group_into_periods(polygon_id: str, observations: list[NdviObservation]) -> list[AnomalyPeriod]:
    """Группирует подряд идущие даты со статусом suppression/critical в
    периоды (не по точке, а по непрерывному отрезку), как того требует
    контракт `GET /anomalies`."""
    ordered = sorted(observations, key=lambda o: o.date)
    periods: list[AnomalyPeriod] = []
    run: list[NdviObservation] = []

    # Считаем причины один раз по всему ряду полигона (не по точке/периоду) —
    # весь ряд нужен ML для скользящих окон осадков/температуры (14/7 дней).
    status_lookup = {id(obs): _STATUS_TO_ML.get(obs.status) for obs in ordered}
    interpretation = ml_bridge.interpret_anomaly_causes(ordered, status_lookup)

    def flush() -> None:
        if not run:
            return
        worst = min(run, key=lambda o: o.ndvi_zscore if o.ndvi_zscore is not None else 0.0)
        severity = NdviStatus.critical if (worst.ndvi_zscore or 0.0) < -2 else NdviStatus.suppression
        value = worst.primary_ndvi if worst.primary_ndvi is not None else worst.primary_ndvi_pred
        periods.append(
            AnomalyPeriod(
                id=f"{polygon_id}-{run[0].date.isoformat()}",
                polygon_id=polygon_id,
                start_date=run[0].date,
                end_date=run[-1].date,
                severity=severity,
                min_z_score=worst.ndvi_zscore or 0.0,
                deviation=(value or 0.0) - (worst.ndvi_climatology_mean or 0.0),
                explanation=explain_anomaly(worst, run, interpretation),
            )
        )
        run.clear()

    for obs in ordered:
        if obs.status in ANOMALOUS_STATUSES:
            run.append(obs)
        else:
            flush()
    flush()
    return periods


async def rebuild_anomalies(db: AsyncSession, polygon_id: str, observations: list[NdviObservation]) -> None:
    """Пересчитывает климатологию/Z-score там, где их не было, и
    перематериализует `anomaly_periods` для полигона."""
    apply_climatology(observations)
    await db.execute(delete(AnomalyPeriod).where(AnomalyPeriod.polygon_id == polygon_id))
    for period in group_into_periods(polygon_id, observations):
        db.add(period)
