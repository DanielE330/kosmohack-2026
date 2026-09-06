"""Мост к Google Earth Engine (`../ml/webapp/gee_utils.py`) — реальный
многоисточниковый сбор данных (Sentinel-2/Landsat/MODIS/ERA5) в дополнение
к офлайн-модели на `data/train_dataset.csv` (см. `ml_bridge.py`). Как и там,
путь до `ml/` — абсолютный (не зависит от текущей директории запуска), а
любая ошибка инициализации/сети превращается в `GEE_AVAILABLE = False` и
понятную ошибку у вызывающего кода, а не в падение веб-сервиса: GEE — это
внешний живой сервис, который может быть недоступен (нет кредов, квота,
сеть), и это никогда не должно ронять остальной функционал."""

from __future__ import annotations

import logging
import sys
import time
from pathlib import Path
from typing import Any

from app.config import settings

_ML_DIR = Path(__file__).resolve().parents[2] / "ml"
_ML_WEBAPP_DIR = _ML_DIR / "webapp"

logger = logging.getLogger(__name__)

GEE_AVAILABLE = True
_IMPORT_ERROR: str | None = None

# Earth Engine ограничивает число одновременных агрегаций на аккаунт и
# отвечает "Too many concurrent aggregations" — это временная ошибка, а не
# отказ: тот же запрос через пару секунд проходит. Без ретрая пользователь
# получал 500 при попытке подтянуть данные по полигону.
_RETRIES = 4
_RETRY_BASE_DELAY = 3.0

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
    ndvi = _with_retries(
        "get_ndvi_timeseries", lambda: gee_utils.get_ndvi_timeseries(geometry, date_from, date_to)
    )
    weather = _with_retries(
        "get_era5_weather", lambda: gee_utils.get_era5_weather(geometry, date_from, date_to)
    )
    return {"ndvi": ndvi, "weather": weather}


def _with_retries(what: str, call):
    """Повторяет запрос к GEE при временных ошибках сервиса.

    Исчерпав попытки, отдаёт `GEEUnavailable`, а не исходное исключение:
    для вызывающего кода недоступность GEE по квоте ничем не отличается от
    недоступности по отсутствию кредов — и то, и другое должно стать
    понятной 503, а не 500 «Internal Server Error»."""
    last: Exception | None = None
    for attempt in range(_RETRIES):
        try:
            return call()
        except gee_utils.GEEDataError as exc:
            last = exc
            if attempt == _RETRIES - 1:
                break
            delay = _RETRY_BASE_DELAY * (2**attempt)
            logger.warning(
                "GEE %s: попытка %d/%d не удалась (%s), повтор через %.0f с",
                what,
                attempt + 1,
                _RETRIES,
                exc,
                delay,
            )
            time.sleep(delay)
    raise GEEUnavailable(f"Google Earth Engine временно недоступен ({what}): {last}") from last
