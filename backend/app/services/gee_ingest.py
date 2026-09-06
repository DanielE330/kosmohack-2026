"""Заполнение временного ряда полигона реальными данными из Google Earth
Engine.

Зачем: `POST /polygons/custom` раньше только сохранял контур, и у только что
нарисованного полигона не было ни одного наблюдения — карточка участка
показывала «Нет данных за выбранный период», хотя сервис умеет тянуть живые
данные (Sentinel-2/Landsat/MODIS + погода ERA5) через `gee_bridge`. Здесь
эти данные превращаются в строки `NdviObservation` (имена полей у GEE и у
модели совпадают не случайно — см. `ml/webapp/gee_utils.py`) и прогоняются
через тот же конвейер, что и `POST /timeseries/{id}/upload`: восстановление
пропусков моделью (`gapfill.fill_gaps`) и пересчёт аномалий
(`anomaly_detection.rebuild_anomalies`).

Отдельный модуль, а не код внутри роутера: то же самое нужно и при создании
полигона, и при явном обновлении данных по кнопке, и потенциально из
фоновой задачи.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import date, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.polygon import Polygon
from app.models.timeseries import NdviObservation
from app.services import anomaly_detection, gapfill, gee_bridge

logger = logging.getLogger(__name__)

# Колонки, которые реально приходят из GEE и один в один ложатся в модель.
_GEE_FIELDS = (
    "s2_ndvi",
    "s2_evi",
    "s2_ndwi",
    "landsat_ndvi",
    "landsat_evi",
    "landsat_ndwi",
    "modis_ndvi",
    "modis_evi",
)
_WEATHER_FIELDS = ("era5_temp_c", "era5_precip_mm")

# Приоритет источника для `primary_ndvi`: Sentinel-2 (10 м) точнее Landsat
# (30 м), Landsat точнее MODIS (250 м) — тот же порядок, что и в датасете
# соревнования.
_PRIMARY_PRIORITY = ("s2_ndvi", "landsat_ndvi", "modis_ndvi")

DEFAULT_LOOKBACK_DAYS = 365


def _parse_date(value) -> date | None:
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        try:
            return datetime.strptime(value[:10], "%Y-%m-%d").date()
        except ValueError:
            return None
    return None


def _merge_gee_rows(ndvi_rows: list[dict], weather_rows: list[dict]) -> dict[date, dict]:
    """GEE отдаёт индексы и погоду отдельными списками — сводим их по дате."""
    merged: dict[date, dict] = {}
    for row in ndvi_rows:
        day = _parse_date(row.get("date"))
        if day is None:
            continue
        target = merged.setdefault(day, {})
        for field in _GEE_FIELDS:
            value = row.get(field)
            if value is not None:
                target[field] = float(value)
    for row in weather_rows:
        day = _parse_date(row.get("date"))
        if day is None:
            continue
        target = merged.setdefault(day, {})
        for field in _WEATHER_FIELDS:
            value = row.get(field)
            if value is not None:
                target[field] = float(value)
    return merged


async def fetch_and_store(
    db: AsyncSession,
    polygon: Polygon,
    date_from: str | None = None,
    date_to: str | None = None,
) -> int:
    """Тянет данные из GEE за период и сохраняет их как наблюдения полигона.

    Возвращает число дат, по которым появились данные. Поднимает
    [gee_bridge.GEEUnavailable], если GEE не настроен/недоступен — вызывающий
    код сам решает, это фатально (явная кнопка «обновить данные») или нет
    (создание полигона: контур сохранить всё равно надо).
    """
    if date_to is None:
        date_to = date.today().isoformat()
    if date_from is None:
        date_from = (date.today() - timedelta(days=DEFAULT_LOOKBACK_DAYS)).isoformat()

    points = [(float(p[0]), float(p[1])) for p in polygon.points]
    # GEE-запрос синхронный и при квоте/сети сидит в ретраях с time.sleep
    # (см. gee_bridge._with_retries) — без to_thread это блокирует весь
    # event loop uvicorn, и сервис переставал отвечать даже на /health
    # на десятки секунд для ВСЕХ пользователей разом, а не только для
    # того, чей полигон сейчас грузится.
    live = await asyncio.to_thread(gee_bridge.fetch_live_sources, points, date_from, date_to)
    merged = _merge_gee_rows(live.get("ndvi") or [], live.get("weather") or [])
    if not merged:
        return 0

    existing = await db.execute(
        select(NdviObservation).where(NdviObservation.polygon_id == polygon.id)
    )
    by_date = {obs.date: obs for obs in existing.scalars().all()}

    for day, values in merged.items():
        obs = by_date.get(day)
        if obs is None:
            obs = NdviObservation(polygon_id=polygon.id, date=day)
            db.add(obs)
            by_date[day] = obs
        for field, value in values.items():
            setattr(obs, field, value)
        obs.doy = day.timetuple().tm_yday
        # `primary_ndvi` — значение того сенсора, который реально снял сцену
        # в этот день (а не среднее по всем): пустые дни останутся пропусками
        # и будут восстановлены моделью ниже, как и в обучающем датасете.
        if obs.primary_ndvi is None:
            for field in _PRIMARY_PRIORITY:
                if values.get(field) is not None:
                    obs.primary_ndvi = values[field]
                    break
        if polygon.crop_type and not obs.crop_type:
            obs.crop_type = polygon.crop_type

    await db.flush()
    all_observations = sorted(by_date.values(), key=lambda o: o.date)
    gapfill.fill_gaps(all_observations)
    await anomaly_detection.rebuild_anomalies(db, polygon.id, all_observations)
    await db.commit()
    logger.info(
        "GEE: полигон %s — сохранено дат: %d (период %s..%s)",
        polygon.id,
        len(merged),
        date_from,
        date_to,
    )
    return len(merged)


async def try_fetch_and_store(
    db: AsyncSession,
    polygon: Polygon,
    date_from: str | None = None,
    date_to: str | None = None,
) -> int | None:
    """То же самое, но никогда не бросает: возвращает `None`, если данные не
    удалось получить (GEE не настроен, квота, сетевая ошибка). Нужен там,
    где основная операция важнее данных — например при создании полигона:
    контур обязан сохраниться, даже если GEE сейчас недоступен."""
    try:
        return await fetch_and_store(db, polygon, date_from, date_to)
    except gee_bridge.GEEUnavailable as exc:
        logger.warning("GEE недоступен, полигон %s остаётся без данных: %s", polygon.id, exc)
        return None
    except Exception:  # noqa: BLE001 — внешний сервис, любая ошибка не должна ронять создание
        logger.exception("Не удалось получить данные GEE для полигона %s", polygon.id)
        return None
