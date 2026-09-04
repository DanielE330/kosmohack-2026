"""FastAPI service for live vegetation monitoring with Google Earth Engine."""
from __future__ import annotations

import sys
from functools import lru_cache
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent / "src"))

import pandas as pd
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from config import MODEL_PATH, TRAIN_PATH  # noqa: E402
from pipeline import restore_and_analyze  # noqa: E402

try:  # Works under uvicorn and when this file is run directly.
    from . import gee_utils
except ImportError:  # pragma: no cover
    import gee_utils  # type: ignore


app = FastAPI(title="Мониторинг вегетационной динамики", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Restrict to the Flutter Web origin before production.
    allow_methods=["*"],
    allow_headers=["*"],
)


@lru_cache(maxsize=1)
def get_reference_data() -> pd.DataFrame | None:
    if not TRAIN_PATH.exists():
        return None
    return pd.read_csv(TRAIN_PATH, parse_dates=["date"])


def get_climatology_std_floor(reference: pd.DataFrame | None, crop_type: str) -> float:
    """Match live z-score scale to the climatology scale used in train."""
    if reference is None or "ndvi_climatology_std" not in reference:
        return 0.10
    values = reference["ndvi_climatology_std"].dropna()
    if "crop_type" in reference:
        crop_values = reference.loc[
            reference["crop_type"].eq(crop_type), "ndvi_climatology_std"
        ].dropna()
        if len(crop_values) >= 100:
            values = crop_values
    return float(values.median()) if not values.empty else 0.10


class PolygonRequest(BaseModel):
    geojson: dict
    date_from: str
    date_to: str
    crop_type: str = "unknown"
    cadence_days: int = Field(default=5, ge=1, le=30)
    climatology_years: int = Field(default=5, ge=2, le=10)


@app.get("/health")
def health():
    return {
        "status": "ok",
        "model_ready": MODEL_PATH.exists(),
        "gee_initialized": gee_utils.is_initialized(),
    }


@app.get("/find-polygons")
def find_polygons(min_lon: float, min_lat: float, max_lon: float, max_lat: float):
    """Find approximate cropland contours inside a small bounding box."""
    try:
        polygons = gee_utils.find_field_polygons((min_lon, min_lat, max_lon, max_lat))
        return {"polygons": polygons, "count": len(polygons)}
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    except gee_utils.GEEConfigurationError as exc:
        raise HTTPException(503, str(exc)) from exc
    except gee_utils.GEEDataError as exc:
        raise HTTPException(502, str(exc)) from exc


@app.post("/analyze")
def analyze(req: PolygonRequest):
    """Collect satellite/weather data, reconstruct gaps and detect anomalies."""
    try:
        reference = get_reference_data()
        climatology_std_floor = get_climatology_std_floor(reference, req.crop_type)
        geometry = gee_utils.to_ee_geometry(req.geojson)
        date_from = pd.Timestamp(req.date_from)
        date_to = pd.Timestamp(req.date_to)
        if date_to < date_from:
            raise ValueError("date_to не может быть раньше date_from")

        history_from = (date_from - pd.DateOffset(years=req.climatology_years)).date().isoformat()
        history_records = gee_utils.get_ndvi_timeseries(
            geometry, history_from, date_to.date().isoformat()
        )
        live_records = gee_utils.prepare_live_records(
            history_records,
            date_from.date().isoformat(),
            date_to.date().isoformat(),
            cadence_days=req.cadence_days,
            climatology_std_floor=climatology_std_floor,
        )
        weather_records = gee_utils.get_era5_weather(
            geometry, date_from.date().isoformat(), date_to.date().isoformat()
        )
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    except gee_utils.GEEConfigurationError as exc:
        raise HTTPException(503, str(exc)) from exc
    except gee_utils.GEEDataError as exc:
        raise HTTPException(502, str(exc)) from exc

    frame = pd.DataFrame(live_records)
    if frame.empty:
        raise HTTPException(404, "Для выбранного периода не удалось построить временной ряд")
    frame["date"] = pd.to_datetime(frame["date"])

    weather = pd.DataFrame(weather_records)
    if not weather.empty:
        weather["date"] = pd.to_datetime(weather["date"])
        weather = weather.sort_values("date")
        indexed_weather = weather.set_index("date")
        weather["precip_14d"] = indexed_weather["era5_precip_mm"].rolling(
            "14D", min_periods=1
        ).sum().to_numpy()
        weather["temp_7d"] = indexed_weather["era5_temp_c"].rolling(
            "7D", min_periods=1
        ).mean().to_numpy()
        frame = frame.merge(weather, on="date", how="left")

    # These columns reproduce the contract of private_features.csv.
    numeric_columns = [
        "s2_ndvi",
        "s2_evi",
        "s2_ndwi",
        "landsat_ndvi",
        "landsat_evi",
        "landsat_ndwi",
        "modis_ndvi",
        "modis_evi",
        "era5_temp_c",
        "era5_precip_mm",
        "ndvi_climatology_mean",
        "ndvi_climatology_std",
        "n_reference_years",
        "sensor_spread",
        "precip_14d",
        "temp_7d",
    ]
    for column in numeric_columns:
        if column not in frame:
            frame[column] = float("nan")

    frame["anon_polygon_id"] = "live_request"
    frame["crop_type"] = req.crop_type
    frame["year"] = frame["date"].dt.year
    frame["doy"] = frame["date"].dt.dayofyear
    frame["value_kind"] = frame["primary_ndvi"].notna().map(
        {True: "measured", False: "reconstructed"}
    )

    if not MODEL_PATH.exists():
        raise HTTPException(500, "Модель не найдена. Запусти python src/train.py")
    try:
        result = restore_and_analyze(frame, reference=reference)
    except Exception as exc:
        raise HTTPException(500, f"Ошибка ML-инференса: {exc}") from exc

    series = result["series"]
    result["summary"] = {
        "rows": len(series),
        "measured": sum(row.get("value_kind") == "measured" for row in series),
        "reconstructed": sum(row.get("value_kind") == "reconstructed" for row in series),
        "anomaly_periods": len(result["anomaly_periods"]),
        "measured_anomaly_points": sum(
            row.get("value_kind") == "measured"
            and row.get("anomaly_status") in {"Угнетение биомассы", "Критическая аномалия"}
            for row in series
        ),
        "periods_requiring_review": sum(
            bool(period.get("requires_review")) for period in result["anomaly_periods"]
        ),
        "climatology_std_floor": round(climatology_std_floor, 4),
    }
    return result
