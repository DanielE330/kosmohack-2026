"""Простой контракт ML-ядра для интеграции с FastAPI/Flutter-бэкендом."""
from __future__ import annotations

from pathlib import Path

import joblib
import numpy as np
import pandas as pd

from anomalies import add_anomaly_status, add_interpretation, detect_anomaly_periods
from config import DATE_COL, ID_COL, MODEL_PATH, TARGET_COL
from modeling import predict_private_gaps


def _fill_context_for_anomalies(df: pd.DataFrame) -> pd.DataFrame:
    result = df.copy()
    result[DATE_COL] = pd.to_datetime(result[DATE_COL])
    result = result.sort_values([ID_COL, DATE_COL])
    for col in (
        "ndvi_climatology_mean",
        "ndvi_climatology_std",
        "n_reference_years",
        "sensor_spread",
        "era5_temp_c",
        "era5_precip_mm",
        "precip_14d",
        "temp_7d",
    ):
        if col in result:
            result[col] = pd.to_numeric(result[col], errors="coerce")
            result[col] = result.groupby(ID_COL)[col].transform(
                lambda s: s.interpolate(limit_direction="both")
            )
    return result


def restore_and_analyze(
    data: pd.DataFrame,
    reference: pd.DataFrame | None = None,
    model_path: str | Path = MODEL_PATH,
) -> dict:
    """Восстанавливает gaps и возвращает ряд плюс интервалы аномалий.

    ``data`` должен содержать тот же контракт колонок, что private_features.csv,
    включая boolean-флаг is_synthetic_gap.
    """
    source = data.copy()
    source[DATE_COL] = pd.to_datetime(source[DATE_COL])
    gap_mask = source["is_synthetic_gap"].fillna(False).astype(bool)
    if gap_mask.any():
        bundle = joblib.load(model_path)
        prediction = predict_private_gaps(source, bundle, reference=reference)
        prediction[DATE_COL] = pd.to_datetime(prediction[DATE_COL])
        restored = source.merge(
            prediction,
            on=[ID_COL, DATE_COL],
            how="left",
            validate="one_to_one",
        )
        restored[TARGET_COL] = restored[TARGET_COL].fillna(restored["primary_ndvi_pred"])
    else:
        # A short period can consist only of clear satellite observations.
        # In that case anomaly analysis should still work without asking the
        # gap model to predict an empty query set.
        restored = source.copy()
        restored["primary_ndvi_pred"] = np.nan
    restored = _fill_context_for_anomalies(restored)
    restored = add_anomaly_status(restored)
    restored = add_interpretation(restored)
    periods = detect_anomaly_periods(restored)

    series_cols = [
        ID_COL,
        DATE_COL,
        TARGET_COL,
        "is_synthetic_gap",
        "value_kind",
        "observation_source",
        "s2_ndvi",
        "landsat_ndvi",
        "modis_ndvi",
        "s2_valid_fraction",
        "landsat_valid_fraction",
        "modis_valid_fraction",
        "ndvi_climatology_mean",
        "ndvi_climatology_std",
        "n_reference_years",
        "sensor_spread",
        "era5_temp_c",
        "era5_precip_mm",
        "precip_14d",
        "temp_7d",
        "anomaly_status",
        "z_score",
        "anomaly_confidence",
        "anomaly_cause",
        "cause_confidence",
        "cause_evidence",
        "requires_review",
        "anomaly_reason",
    ]
    available = [col for col in series_cols if col in restored]
    series = restored[available].copy()
    series[DATE_COL] = series[DATE_COL].dt.strftime("%Y-%m-%d")
    series = series.replace([np.inf, -np.inf], np.nan).astype(object)
    series = series.where(pd.notna(series), None)
    periods = periods.replace([np.inf, -np.inf], np.nan).astype(object)
    periods = periods.where(pd.notna(periods), None)
    return {
        "series": series.to_dict(orient="records"),
        "anomaly_periods": periods.to_dict(orient="records"),
    }
