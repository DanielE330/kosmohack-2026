"""Мост к Google Earth Engine (`../ml/webapp/gee_utils.py`) — реальный
многоисточниковый сбор данных (Sentinel-2/Landsat/MODIS/ERA5) в дополнение
к офлайн-модели на `data/train_dataset.csv` (см. `ml_bridge.py`). Как и там,
путь до `ml/` — абсолютный (не зависит от текущей директории запуска), а
любая ошибка инициализации/сети превращается в `GEE_AVAILABLE = False` и
понятную ошибку у вызывающего кода, а не в падение веб-сервиса: GEE — это
внешний живой сервис, который может быть недоступен (нет кредов, квота,
сеть), и это никогда не должно ронять остальной функционал."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

from app.config import settings

_ML_DIR = Path(__file__).resolve().parents[2] / "ml"
_ML_WEBAPP_DIR = _ML_DIR / "webapp"

GEE_AVAILABLE = True
_IMPORT_ERROR: str | None = None

try:
    if str(_ML_WEBAPP_DIR) not in sys.path:
        sys.path.insert(0, str(_ML_WEBAPP_DIR))
    import gee_utils  # type: ignore
except Exception as exc:  # noqa: BLE001 — любая причина недоступности одинаково фатальна
    GEE_AVAILABLE = False
    _IMPORT_ERROR = str(exc)
    gee_utils = None  # type: ignore


class GEEUnavailable(RuntimeError):
    """GEE не установлен/не настроен/недоступен — сообщение годится для 503."""


def _ensure_ready() -> None:
    if not GEE_AVAILABLE:
        raise GEEUnavailable(
            f"Google Earth Engine недоступен на сервере: {_IMPORT_ERROR}"
        )
    if not settings.earthengine_project:
        raise GEEUnavailable(
            "Не задан EARTHENGINE_PROJECT — GEE не инициализирован."
        )
    try:
        gee_utils.init_gee(project=settings.earthengine_project)
    except gee_utils.GEEConfigurationError as exc:
        raise GEEUnavailable(str(exc)) from exc


def points_to_geojson(points: list[tuple[float, float]]) -> dict[str, Any]:
    """`points` — как хранятся в БД: `[lat, lon]`. GeoJSON требует `[lon, lat]`
    и замкнутое кольцо (первая точка повторена в конце)."""
    ring = [[lon, lat] for lat, lon in points]
    if ring[0] != ring[-1]:
        ring = ring + [ring[0]]
    return {"type": "Polygon", "coordinates": [ring]}


def fetch_live_sources(
    points: list[tuple[float, float]], date_from: str, date_to: str
) -> dict[str, Any]:
    """Реальные NDVI (Sentinel-2/Landsat/MODIS, что реально снимало сцену) и
    погода ERA5 для контура полигона за период — живой запрос к GEE, а не к
    статичному `train_dataset.csv`. Поднимает [GEEUnavailable], если GEE не
    настроен/недоступен, или исходную ошибку GEE (некорректный полигон/даты,
    квота) — вызывающий код должен превратить их в понятный HTTP-ответ, не
    роняя остальной сервис."""
    _ensure_ready()
    geometry = gee_utils.to_ee_geometry(points_to_geojson(points))
    ndvi = gee_utils.get_ndvi_timeseries(geometry, date_from, date_to)
    weather = gee_utils.get_era5_weather(geometry, date_from, date_to)
    return {"ndvi": ndvi, "weather": weather}
