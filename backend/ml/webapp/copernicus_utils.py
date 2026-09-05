"""Copernicus Data Space Ecosystem integration for the live vegetation monitor.

Drop-in replacement for ``gee_utils`` when Google Earth Engine isn't
available (e.g. Cloud billing/registration isn't set up). Sentinel-2
NDVI/EVI/NDWI comes from the free Sentinel Hub Statistical API on
Copernicus Data Space; weather comes from the free Open-Meteo historical
archive (no API key, no billing). Landsat/MODIS/ESA WorldCover have no
equivalent free source here, so this backend only ever reports Sentinel-2
observations and does not implement ``find_field_polygons``.
"""
from __future__ import annotations

import math
import os
import threading
import time
from datetime import date, timedelta
from typing import Any

import requests

from . import gee_utils as _gee

GEEConfigurationError = _gee.GEEConfigurationError
GEEDataError = _gee.GEEDataError
normalize_geojson_geometry = _gee.normalize_geojson_geometry
prepare_live_records = _gee.prepare_live_records
_validate_dates = _gee._validate_dates
_collapse_by_date = _gee._collapse_by_date

TOKEN_URL = "https://identity.dataspace.copernicus.eu/auth/realms/CDSE/protocol/openid-connect/token"
STATISTICS_URL = "https://sh.dataspace.copernicus.eu/api/v1/statistics"
OPEN_METEO_URL = "https://archive-api.open-meteo.com/v1/archive"

_token_lock = threading.Lock()
_token_cache: dict[str, Any] = {"access_token": None, "expires_at": 0.0}

# Cloud/shadow/snow SCL classes to mask out (matches gee_utils._sentinel_records).
_EVALSCRIPT = """
//VERSION=3
function setup() {
  return {
    input: [{ bands: ["B02", "B03", "B04", "B08", "SCL", "dataMask"] }],
    output: [
      { id: "ndvi", bands: 1, sampleType: "FLOAT32" },
      { id: "evi", bands: 1, sampleType: "FLOAT32" },
      { id: "ndwi", bands: 1, sampleType: "FLOAT32" },
      { id: "dataMask", bands: 1, sampleType: "UINT8" }
    ]
  };
}

function evaluatePixel(s) {
  var badScl = [1, 2, 3, 7, 8, 9, 10, 11].indexOf(s.SCL) !== -1;
  var mask = badScl ? 0 : s.dataMask;
  return {
    ndvi: [(s.B08 - s.B04) / (s.B08 + s.B04)],
    evi: [2.5 * (s.B08 - s.B04) / (s.B08 + 6 * s.B04 - 7.5 * s.B02 + 1)],
    ndwi: [(s.B03 - s.B08) / (s.B03 + s.B08)],
    dataMask: [mask]
  };
}
"""


def _client_id() -> str | None:
    return os.getenv("CDSE_CLIENT_ID")


def _client_secret() -> str | None:
    return os.getenv("CDSE_CLIENT_SECRET")


def is_initialized() -> bool:
    return bool(_client_id() and _client_secret())


def _get_token() -> str:
    client_id, client_secret = _client_id(), _client_secret()
    if not client_id or not client_secret:
        raise GEEConfigurationError(
            "Не заданы CDSE_CLIENT_ID / CDSE_CLIENT_SECRET. Создай OAuth-клиент "
            "в личном кабинете Copernicus Data Space (dataspace.copernicus.eu -> "
            "Account settings -> OAuth clients)."
        )
    with _token_lock:
        if _token_cache["access_token"] and _token_cache["expires_at"] > time.time() + 30:
            return _token_cache["access_token"]
        try:
            response = requests.post(
                TOKEN_URL,
                data={
                    "grant_type": "client_credentials",
                    "client_id": client_id,
                    "client_secret": client_secret,
                },
                timeout=30,
            )
            response.raise_for_status()
            payload = response.json()
        except requests.RequestException as exc:
            raise GEEConfigurationError(
                f"Не удалось получить токен Copernicus Data Space: {exc}"
            ) from exc
        _token_cache["access_token"] = payload["access_token"]
        _token_cache["expires_at"] = time.time() + float(payload.get("expires_in", 600))
        return _token_cache["access_token"]


def to_geometry(payload: dict[str, Any]) -> dict[str, Any]:
    return normalize_geojson_geometry(payload)


def _polygon_bounds(geometry: dict[str, Any]) -> tuple[float, float, float, float]:
    lons: list[float] = []
    lats: list[float] = []

    def walk(value: Any) -> None:
        if (
            isinstance(value, (list, tuple))
            and len(value) >= 2
            and isinstance(value[0], (int, float))
        ):
            lons.append(float(value[0]))
            lats.append(float(value[1]))
            return
        for item in value:
            walk(item)

    walk(geometry["coordinates"])
    return min(lons), min(lats), max(lons), max(lats)


def _centroid(geometry: dict[str, Any]) -> tuple[float, float]:
    min_lon, min_lat, max_lon, max_lat = _polygon_bounds(geometry)
    return (min_lat + max_lat) / 2, (min_lon + max_lon) / 2


def _grid_size(geometry: dict[str, Any]) -> tuple[int, int]:
    """Pick a pixel grid so the Statistics API samples at roughly 10 m/px."""
    min_lon, min_lat, max_lon, max_lat = _polygon_bounds(geometry)
    lat_mid = (min_lat + max_lat) / 2
    meters_per_deg_lon = 111_320 * max(0.1, math.cos(math.radians(lat_mid)))
    width_m = max(20.0, (max_lon - min_lon) * meters_per_deg_lon)
    height_m = max(20.0, (max_lat - min_lat) * 111_320)
    width = min(512, max(16, round(width_m / 10)))
    height = min(512, max(16, round(height_m / 10)))
    return width, height


def get_ndvi_timeseries(geometry: dict[str, Any], date_from: str, date_to: str) -> list[dict[str, Any]]:
    """Return cloud-masked Sentinel-2 NDVI/EVI/NDWI by date (no Landsat/MODIS here)."""
    start, end_exclusive = _validate_dates(date_from, date_to)
    width, height = _grid_size(geometry)
    token = _get_token()

    body = {
        "input": {
            "bounds": {
                "geometry": geometry,
                "properties": {"crs": "http://www.opengis.net/def/crs/OGC/1.3/CRS84"},
            },
            "data": [
                {
                    "type": "sentinel-2-l2a",
                    "dataFilter": {"maxCloudCoverage": 80},
                }
            ],
        },
        "aggregation": {
            "timeRange": {"from": f"{start}T00:00:00Z", "to": f"{end_exclusive}T00:00:00Z"},
            "aggregationInterval": {"of": "P1D"},
            "width": width,
            "height": height,
            "evalscript": _EVALSCRIPT,
        },
    }
    try:
        response = requests.post(
            STATISTICS_URL,
            json=body,
            headers={"Authorization": f"Bearer {token}"},
            timeout=60,
        )
        response.raise_for_status()
        payload = response.json()
    except requests.RequestException as exc:
        raise GEEDataError(f"Ошибка запроса к Copernicus Data Space: {exc}") from exc

    records: list[dict[str, Any]] = []
    for interval in payload.get("data", []):
        day = str(interval.get("interval", {}).get("from", ""))[:10]
        if not day:
            continue
        outputs = interval.get("outputs", {})
        row: dict[str, Any] = {"date": day}
        sample_count = 0
        no_data_count = 0
        for key, column in (("ndvi", "s2_ndvi"), ("evi", "s2_evi"), ("ndwi", "s2_ndwi")):
            stats = outputs.get(key, {}).get("bands", {}).get("B0", {}).get("stats", {})
            if not stats or not stats.get("sampleCount"):
                continue
            mean = stats.get("mean")
            if mean is not None and math.isfinite(mean):
                row[column] = mean
            sample_count = stats.get("sampleCount", sample_count)
            no_data_count = stats.get("noDataCount", no_data_count)
        if "s2_ndvi" not in row:
            continue
        row["s2_valid_fraction"] = (
            (sample_count - no_data_count) / sample_count if sample_count else 0.0
        )
        records.append(row)
    return _collapse_by_date(records)


def get_weather(geometry: dict[str, Any], date_from: str, date_to: str) -> list[dict[str, Any]]:
    """Return daily mean temperature (C) and precipitation (mm) via Open-Meteo."""
    start, end_exclusive = _validate_dates(date_from, date_to)
    end = (date.fromisoformat(end_exclusive) - timedelta(days=1)).isoformat()
    lat, lon = _centroid(geometry)

    try:
        response = requests.get(
            OPEN_METEO_URL,
            params={
                "latitude": lat,
                "longitude": lon,
                "start_date": start,
                "end_date": end,
                "daily": "temperature_2m_mean,precipitation_sum",
                "timezone": "UTC",
            },
            timeout=30,
        )
        response.raise_for_status()
        payload = response.json()
    except requests.RequestException as exc:
        raise GEEDataError(f"Ошибка запроса к Open-Meteo: {exc}") from exc

    daily = payload.get("daily", {})
    records = [
        {"date": day, "era5_temp_c": temp, "era5_precip_mm": precip}
        for day, temp, precip in zip(
            daily.get("time", []),
            daily.get("temperature_2m_mean", []),
            daily.get("precipitation_sum", []),
        )
    ]
    return _collapse_by_date(records)


# `main.py` calls this name regardless of which backend is active; the
# columns produced (era5_temp_c/era5_precip_mm) match the model's feature
# contract even though the values here come from Open-Meteo, not ERA5 directly.
get_era5_weather = get_weather
