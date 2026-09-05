"""Google Earth Engine integration for the live vegetation monitor.

The functions return ordinary Python dictionaries so the FastAPI/ML pipeline
stays independent from Earth Engine and can be tested without network access.
"""
from __future__ import annotations

import math
import os
import threading
from collections import defaultdict
from datetime import date, timedelta
from statistics import fmean, pstdev
from typing import Any, Iterable

try:
    import ee
except ImportError:  # Pure unit tests can run before earthengine-api is installed.
    ee = None


S2_COLLECTION = "COPERNICUS/S2_SR_HARMONIZED"
LANDSAT_8_COLLECTION = "LANDSAT/LC08/C02/T1_L2"
LANDSAT_9_COLLECTION = "LANDSAT/LC09/C02/T1_L2"
MODIS_COLLECTION = "MODIS/061/MOD13Q1"
ERA5_DAILY_COLLECTION = "ECMWF/ERA5_LAND/DAILY_AGGR"
WORLDCOVER_COLLECTION = "ESA/WorldCover/v200"

MAX_REQUEST_DAYS = int(os.getenv("GEE_MAX_REQUEST_DAYS", "5000"))
MAX_GEOJSON_COORDINATES = int(os.getenv("GEE_MAX_GEOJSON_COORDINATES", "10000"))
MIN_VALID_FRACTION = float(os.getenv("GEE_MIN_VALID_FRACTION", "0.10"))

_init_lock = threading.Lock()
_initialized = False


class GEEConfigurationError(RuntimeError):
    """Earth Engine is not installed, authenticated or configured."""


class GEEDataError(RuntimeError):
    """Earth Engine could not produce valid data for a request."""


def is_initialized() -> bool:
    return _initialized


def init_gee(
    project: str | None = None,
    *,
    service_account: str | None = None,
    key_file: str | None = None,
    authenticate: bool = False,
) -> None:
    """Initialize Earth Engine once.

    Local development normally uses ``earthengine authenticate`` followed by
    ``EARTHENGINE_PROJECT=...``. A deployed service should set
    ``GEE_SERVICE_ACCOUNT`` and ``GOOGLE_APPLICATION_CREDENTIALS``.
    Interactive authentication is opt-in so an API worker never blocks waiting
    for a browser login.
    """
    global _initialized

    if _initialized:
        return
    if ee is None:
        raise GEEConfigurationError(
            "Не установлен earthengine-api. Выполни: pip install -r requirements.txt"
        )

    project = project or os.getenv("EARTHENGINE_PROJECT") or os.getenv("GOOGLE_CLOUD_PROJECT")
    service_account = service_account or os.getenv("GEE_SERVICE_ACCOUNT")
    key_file = key_file or os.getenv("GOOGLE_APPLICATION_CREDENTIALS")

    if not project:
        raise GEEConfigurationError(
            "Не задан Earth Engine project. Установи EARTHENGINE_PROJECT=<project-id>."
        )

    with _init_lock:
        if _initialized:
            return
        try:
            if service_account and key_file:
                credentials = ee.ServiceAccountCredentials(service_account, key_file)
                ee.Initialize(credentials, project=project)
            else:
                if authenticate:
                    ee.Authenticate()
                ee.Initialize(project=project)
        except Exception as exc:
            raise GEEConfigurationError(
                "Earth Engine не инициализирован. Для локального запуска выполни "
                "`earthengine authenticate`, затем задай EARTHENGINE_PROJECT."
            ) from exc
        _initialized = True


def ensure_gee_initialized() -> None:
    if not _initialized:
        init_gee(authenticate=False)


def normalize_geojson_geometry(payload: dict[str, Any]) -> dict[str, Any]:
    """Accept a GeoJSON Feature or Geometry and return a validated Geometry."""
    if not isinstance(payload, dict):
        raise ValueError("geojson должен быть объектом JSON")

    geo_type = payload.get("type")
    if geo_type == "Feature":
        payload = payload.get("geometry")
        if not isinstance(payload, dict):
            raise ValueError("GeoJSON Feature не содержит geometry")
        geo_type = payload.get("type")

    if geo_type not in {"Polygon", "MultiPolygon"}:
        raise ValueError("Поддерживаются только GeoJSON Polygon и MultiPolygon")

    coordinates = payload.get("coordinates")
    if not isinstance(coordinates, list) or not coordinates:
        raise ValueError("В GeoJSON отсутствуют coordinates")

    points: list[tuple[float, float]] = []

    def collect(value: Any) -> None:
        if len(points) > MAX_GEOJSON_COORDINATES:
            raise ValueError("В полигоне слишком много координат")
        if (
            isinstance(value, (list, tuple))
            and len(value) >= 2
            and isinstance(value[0], (int, float))
            and isinstance(value[1], (int, float))
        ):
            lon, lat = float(value[0]), float(value[1])
            if not (math.isfinite(lon) and math.isfinite(lat)):
                raise ValueError("Координаты должны быть конечными числами")
            if not (-180 <= lon <= 180 and -90 <= lat <= 90):
                raise ValueError(f"Координата вне допустимого диапазона: {lon}, {lat}")
            points.append((lon, lat))
            return
        if not isinstance(value, (list, tuple)):
            raise ValueError("Некорректная вложенность coordinates")
        for item in value:
            collect(item)

    collect(coordinates)
    if len(points) < 4:
        raise ValueError("Полигон должен содержать минимум четыре координаты")

    return {"type": geo_type, "coordinates": coordinates}


def to_ee_geometry(payload: dict[str, Any]):
    ensure_gee_initialized()
    return ee.Geometry(normalize_geojson_geometry(payload))


def _validate_dates(date_from: str, date_to: str) -> tuple[str, str]:
    try:
        start = date.fromisoformat(date_from)
        end = date.fromisoformat(date_to)
    except (TypeError, ValueError) as exc:
        raise ValueError("Даты должны быть в формате YYYY-MM-DD") from exc
    if end < start:
        raise ValueError("date_to не может быть раньше date_from")
    if (end - start).days > MAX_REQUEST_DAYS:
        raise ValueError(f"Слишком большой период: максимум {MAX_REQUEST_DAYS} дней")
    # Earth Engine filterDate uses an exclusive end date.
    return start.isoformat(), (end + timedelta(days=1)).isoformat()


def _safe_number(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if math.isfinite(result) else None


def _records_from_feature_collection(collection) -> list[dict[str, Any]]:
    try:
        info = collection.getInfo()
    except Exception as exc:
        raise GEEDataError(f"Ошибка запроса к Earth Engine: {exc}") from exc

    records: list[dict[str, Any]] = []
    for feature in info.get("features", []):
        properties = dict(feature.get("properties") or {})
        if properties.get("date"):
            records.append(properties)
    return records


def _collapse_by_date(records: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    """Merge sensors and average duplicate satellite tiles from the same day."""
    buckets: dict[str, dict[str, list[Any]]] = defaultdict(lambda: defaultdict(list))
    for record in records:
        day = record.get("date")
        if not day:
            continue
        for key, value in record.items():
            if key != "date" and value is not None:
                buckets[str(day)][key].append(value)

    collapsed = []
    for day in sorted(buckets):
        row: dict[str, Any] = {"date": day}
        for key, values in buckets[day].items():
            numeric = [_safe_number(v) for v in values]
            numeric = [v for v in numeric if v is not None]
            row[key] = fmean(numeric) if numeric else values[0]
        collapsed.append(row)
    return collapsed


def _reduce_collection(collection, geometry, scale: int, required_property: str, reducer=None):
    """Значения вегетационных индексов по контуру полигона — медиана по
    пикселям внутри контура (устойчивее среднего к выбросам на границе:
    смешанные/облачные пиксели по краю участка иначе сильно тянут оценку).
    Полосы `*_valid_fraction` — исключение: это доля валидных пикселей
    (0..1), медиана по бинарной маске превратилась бы в ровно 0 или 1 и
    потеряла бы смысл как "доля" — их всегда усредняем отдельно."""

    def extract(image):
        band_names = image.bandNames()
        fraction_bands = band_names.filter(ee.Filter.stringContains("item", "valid_fraction"))
        value_bands = band_names.removeAll(fraction_bands)

        stats = image.select(value_bands).reduceRegion(
            reducer=reducer or ee.Reducer.mean(),
            geometry=geometry,
            scale=scale,
            bestEffort=True,
            maxPixels=20_000_000,
            tileScale=4,
        )
        fraction_stats = ee.Dictionary(
            ee.Algorithms.If(
                fraction_bands.size().gt(0),
                image.select(fraction_bands).reduceRegion(
                    reducer=ee.Reducer.mean(),
                    geometry=geometry,
                    scale=scale,
                    bestEffort=True,
                    maxPixels=20_000_000,
                    tileScale=4,
                ),
                ee.Dictionary({}),
            )
        )
        return ee.Feature(None, stats.combine(fraction_stats)).set(
            "date", image.date().format("YYYY-MM-dd")
        )

    return ee.FeatureCollection(collection.map(extract)).filter(
        ee.Filter.notNull([required_property])
    )


def _sentinel_records(geometry, start: str, end_exclusive: str) -> list[dict[str, Any]]:
    def add_indices(image):
        scl = image.select("SCL")
        clear = (
            scl.neq(1)
            .And(scl.neq(2))
            .And(scl.neq(3))
            .And(scl.neq(7))
            .And(scl.neq(8))
            .And(scl.neq(9))
            .And(scl.neq(10))
            .And(scl.neq(11))
        )
        sr = image.select(["B2", "B3", "B4", "B8"]).multiply(0.0001).updateMask(clear)
        blue, green, red, nir = (
            sr.select("B2"),
            sr.select("B3"),
            sr.select("B4"),
            sr.select("B8"),
        )
        ndvi = nir.subtract(red).divide(nir.add(red)).rename("s2_ndvi")
        evi = image.expression(
            "2.5 * (nir - red) / (nir + 6 * red - 7.5 * blue + 1)",
            {"nir": nir, "red": red, "blue": blue},
        ).rename("s2_evi")
        ndwi = green.subtract(nir).divide(green.add(nir)).rename("s2_ndwi")
        valid = ndvi.mask().unmask(0).rename("s2_valid_fraction")
        return ee.Image.cat([ndvi, evi, ndwi, valid]).copyProperties(
            image, ["system:time_start"]
        )

    images = (
        ee.ImageCollection(S2_COLLECTION)
        .filterBounds(geometry)
        .filterDate(start, end_exclusive)
        .filter(ee.Filter.lt("CLOUDY_PIXEL_PERCENTAGE", 80))
        .map(add_indices)
    )
    features = _reduce_collection(images, geometry, 10, "s2_ndvi", reducer=ee.Reducer.median())
    return _records_from_feature_collection(features)


def _landsat_records(geometry, start: str, end_exclusive: str) -> list[dict[str, Any]]:
    def add_indices(image):
        qa = image.select("QA_PIXEL")
        clear = qa.bitwiseAnd(1 << 0).eq(0)
        for bit in (1, 2, 3, 4, 5):
            clear = clear.And(qa.bitwiseAnd(1 << bit).eq(0))
        clear = clear.And(image.select("QA_RADSAT").eq(0))

        sr = (
            image.select(["SR_B2", "SR_B3", "SR_B4", "SR_B5"])
            .multiply(0.0000275)
            .add(-0.2)
            .updateMask(clear)
        )
        blue, green, red, nir = (
            sr.select("SR_B2"),
            sr.select("SR_B3"),
            sr.select("SR_B4"),
            sr.select("SR_B5"),
        )
        ndvi = nir.subtract(red).divide(nir.add(red)).rename("landsat_ndvi")
        evi = image.expression(
            "2.5 * (nir - red) / (nir + 6 * red - 7.5 * blue + 1)",
            {"nir": nir, "red": red, "blue": blue},
        ).rename("landsat_evi")
        ndwi = green.subtract(nir).divide(green.add(nir)).rename("landsat_ndwi")
        valid = ndvi.mask().unmask(0).rename("landsat_valid_fraction")
        return ee.Image.cat([ndvi, evi, ndwi, valid]).copyProperties(
            image, ["system:time_start"]
        )

    l8 = ee.ImageCollection(LANDSAT_8_COLLECTION)
    l9 = ee.ImageCollection(LANDSAT_9_COLLECTION)
    images = (
        l8.merge(l9)
        .filterBounds(geometry)
        .filterDate(start, end_exclusive)
        .filter(ee.Filter.lt("CLOUD_COVER", 90))
        .map(add_indices)
    )
    features = _reduce_collection(images, geometry, 30, "landsat_ndvi", reducer=ee.Reducer.median())
    return _records_from_feature_collection(features)


def _modis_records(geometry, start: str, end_exclusive: str) -> list[dict[str, Any]]:
    def add_indices(image):
        clear = image.select("SummaryQA").lte(1)
        ndvi = image.select("NDVI").multiply(0.0001).updateMask(clear).rename("modis_ndvi")
        evi = image.select("EVI").multiply(0.0001).updateMask(clear).rename("modis_evi")
        valid = ndvi.mask().unmask(0).rename("modis_valid_fraction")
        return ee.Image.cat([ndvi, evi, valid]).copyProperties(image, ["system:time_start"])

    images = (
        ee.ImageCollection(MODIS_COLLECTION)
        .filterBounds(geometry)
        .filterDate(start, end_exclusive)
        .map(add_indices)
    )
    features = _reduce_collection(images, geometry, 250, "modis_ndvi", reducer=ee.Reducer.median())
    return _records_from_feature_collection(features)


def get_ndvi_timeseries(geometry, date_from: str, date_to: str) -> list[dict[str, Any]]:
    """Return cloud-masked S2/Landsat/MODIS vegetation indices by date."""
    ensure_gee_initialized()
    start, end_exclusive = _validate_dates(date_from, date_to)
    records = []
    records.extend(_sentinel_records(geometry, start, end_exclusive))
    records.extend(_landsat_records(geometry, start, end_exclusive))
    records.extend(_modis_records(geometry, start, end_exclusive))
    return _collapse_by_date(records)


def get_era5_weather(geometry, date_from: str, date_to: str) -> list[dict[str, Any]]:
    """Return daily ERA5-Land mean temperature (C) and precipitation (mm)."""
    ensure_gee_initialized()
    start, end_exclusive = _validate_dates(date_from, date_to)

    def prepare(image):
        temp = image.select("temperature_2m").subtract(273.15).rename("era5_temp_c")
        precip = (
            image.select("total_precipitation_sum")
            .multiply(1000)
            .max(0)
            .rename("era5_precip_mm")
        )
        return ee.Image.cat([temp, precip]).copyProperties(image, ["system:time_start"])

    images = (
        ee.ImageCollection(ERA5_DAILY_COLLECTION)
        .filterBounds(geometry)
        .filterDate(start, end_exclusive)
        .map(prepare)
    )
    features = _reduce_collection(images, geometry, 11_132, "era5_temp_c")
    return _collapse_by_date(_records_from_feature_collection(features))


def _primary_observation(row: dict[str, Any]) -> tuple[float | None, str | None]:
    for sensor, value_col, quality_col in (
        ("Sentinel-2", "s2_ndvi", "s2_valid_fraction"),
        ("Landsat", "landsat_ndvi", "landsat_valid_fraction"),
        ("MODIS", "modis_ndvi", "modis_valid_fraction"),
    ):
        value = _safe_number(row.get(value_col))
        quality = _safe_number(row.get(quality_col))
        if value is not None and (quality is None or quality >= MIN_VALID_FRACTION):
            return max(-1.0, min(1.0, value)), sensor
    return None, None


def prepare_live_records(
    history_records: Iterable[dict[str, Any]],
    date_from: str,
    date_to: str,
    *,
    cadence_days: int = 5,
    climatology_window_days: int = 15,
    climatology_std_floor: float = 0.08,
) -> list[dict[str, Any]]:
    """Build model-ready rows and a historical day-of-year climatology."""
    start_iso, end_exclusive_iso = _validate_dates(date_from, date_to)
    start = date.fromisoformat(start_iso)
    end = date.fromisoformat(end_exclusive_iso) - timedelta(days=1)
    if not 1 <= cadence_days <= 30:
        raise ValueError("cadence_days должен быть от 1 до 30")
    if not 0.01 <= climatology_std_floor <= 0.40:
        raise ValueError("climatology_std_floor должен быть от 0.01 до 0.40")

    collapsed = _collapse_by_date(history_records)
    history: list[dict[str, Any]] = []
    by_date: dict[date, dict[str, Any]] = {}
    for raw in collapsed:
        try:
            day = date.fromisoformat(str(raw["date"])[:10])
        except (KeyError, ValueError):
            continue
        row = dict(raw)
        primary, source = _primary_observation(row)
        row["primary_ndvi"] = primary
        row["observation_source"] = source
        sensor_values = [
            value
            for value in (
                _safe_number(row.get("s2_ndvi")),
                _safe_number(row.get("landsat_ndvi")),
                _safe_number(row.get("modis_ndvi")),
            )
            if value is not None
        ]
        row["sensor_spread"] = (
            max(sensor_values) - min(sensor_values) if len(sensor_values) >= 2 else None
        )
        row["_day"] = day
        history.append(row)
        by_date[day] = row

    output_days = {row["_day"] for row in history if start <= row["_day"] <= end}
    cursor = start
    while cursor <= end:
        output_days.add(cursor)
        cursor += timedelta(days=cadence_days)

    prepared = []
    for day in sorted(output_days):
        row = {k: v for k, v in by_date.get(day, {}).items() if k != "_day"}
        row["date"] = day.isoformat()
        row.setdefault("primary_ndvi", None)
        row.setdefault("observation_source", None)
        row["year"] = day.year
        row["doy"] = day.timetuple().tm_yday
        row["is_synthetic_gap"] = row["primary_ndvi"] is None

        yearly_values: dict[int, list[float]] = defaultdict(list)
        for reference in history:
            ref_day = reference["_day"]
            ref_value = _safe_number(reference.get("primary_ndvi"))
            if ref_value is None or ref_day.year >= day.year:
                continue
            distance = abs(ref_day.timetuple().tm_yday - row["doy"])
            distance = min(distance, 366 - distance)
            if distance <= climatology_window_days:
                yearly_values[ref_day.year].append(ref_value)

        per_year = [fmean(values) for values in yearly_values.values() if values]
        row["n_reference_years"] = len(per_year)
        row["ndvi_climatology_mean"] = fmean(per_year) if per_year else None
        row["ndvi_climatology_std"] = (
            max(pstdev(per_year), climatology_std_floor) if len(per_year) >= 2 else None
        )
        prepared.append(row)

    return prepared


def find_field_polygons(bbox: tuple[float, float, float, float]) -> list[dict[str, Any]]:
    """Return approximate connected cropland contours from ESA WorldCover 2021."""
    ensure_gee_initialized()
    if len(bbox) != 4:
        raise ValueError("bbox должен содержать min_lon, min_lat, max_lon, max_lat")
    min_lon, min_lat, max_lon, max_lat = map(float, bbox)
    if not (-180 <= min_lon < max_lon <= 180 and -90 <= min_lat < max_lat <= 90):
        raise ValueError("Некорректный bbox")
    if (max_lon - min_lon) * (max_lat - min_lat) > 0.25:
        raise ValueError("bbox слишком большой; выбери область не более 0.25 градуса²")

    region = ee.Geometry.Rectangle([min_lon, min_lat, max_lon, max_lat], geodesic=False)
    cropland = ee.ImageCollection(WORLDCOVER_COLLECTION).first().select("Map").eq(40).selfMask()
    vectors = cropland.reduceToVectors(
        geometry=region,
        scale=20,
        geometryType="polygon",
        eightConnected=True,
        labelProperty="class",
        reducer=ee.Reducer.countEvery(),
        bestEffort=True,
        maxPixels=20_000_000,
        tileScale=4,
    )
    vectors = vectors.map(
        lambda feature: feature.set(
            "area_ha", feature.geometry().area(maxError=10).divide(10_000),
            "source", "ESA WorldCover 2021 (approximate)",
        )
    ).filter(ee.Filter.gte("area_ha", 0.5)).limit(100)

    try:
        info = vectors.getInfo()
    except Exception as exc:
        raise GEEDataError(f"Не удалось получить контуры полей: {exc}") from exc
    return info.get("features", [])
