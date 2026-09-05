"""Leakage-safe calendar-window weather summaries for arbitrary query dates."""
from __future__ import annotations

import numpy as np
import pandas as pd


ID_COL = "anon_polygon_id"
DATE_COL = "date"
WINDOWS = (7, 14, 30, 60)


def _window_stats(
    days: np.ndarray,
    values: np.ndarray,
    query_day: int,
    window: int,
) -> tuple[float, float, float]:
    left = np.searchsorted(days, query_day - window, side="left")
    right = np.searchsorted(days, query_day, side="left")
    part = values[left:right]
    finite = part[np.isfinite(part)]
    if not len(finite):
        return np.nan, np.nan, 0.0
    return float(np.sum(finite)), float(np.mean(finite)), float(len(finite))


def build_weather_window_features(
    data: pd.DataFrame,
    query: pd.DataFrame,
) -> pd.DataFrame:
    """Summarize visible weather strictly before each query calendar date."""
    work = data.copy().reset_index(drop=True)
    work[DATE_COL] = pd.to_datetime(work[DATE_COL])
    result = query[[ID_COL, DATE_COL]].copy().reset_index(drop=True)
    result[DATE_COL] = pd.to_datetime(result[DATE_COL])
    feature_names = []
    for window in WINDOWS:
        feature_names.extend(
            [
                f"weather_temp_mean_{window}d",
                f"weather_gdd5_{window}d",
                f"weather_precip_sum_{window}d",
                f"weather_temp_count_{window}d",
                f"weather_precip_count_{window}d",
            ]
        )
    feature_names.extend(
        [
            "weather_gdd5_season_to_date",
            "weather_precip_season_to_date",
            "weather_season_temp_count",
            "weather_season_precip_count",
        ]
    )
    for name in feature_names:
        result[name] = np.nan

    for polygon_id, query_indices in result.groupby(ID_COL, sort=False).groups.items():
        rows = np.asarray(list(query_indices), dtype=int)
        history = work[work[ID_COL].eq(polygon_id)].sort_values(DATE_COL)
        if history.empty:
            continue
        day = history[DATE_COL].to_numpy(dtype="datetime64[D]").astype("int64")
        temp = pd.to_numeric(history["era5_temp_c"], errors="coerce").to_numpy(float)
        rain = pd.to_numeric(history["era5_precip_mm"], errors="coerce").to_numpy(float)
        rain = np.where(np.isfinite(rain), np.maximum(rain, 0.0), np.nan)
        gdd = np.where(np.isfinite(temp), np.maximum(temp - 5.0, 0.0), np.nan)

        for row in rows:
            date = result.at[row, DATE_COL]
            query_day = int(np.datetime64(date, "D").astype("int64"))
            for window in WINDOWS:
                _, temp_mean, temp_count = _window_stats(day, temp, query_day, window)
                gdd_sum, _, _ = _window_stats(day, gdd, query_day, window)
                rain_sum, _, rain_count = _window_stats(day, rain, query_day, window)
                result.at[row, f"weather_temp_mean_{window}d"] = temp_mean
                result.at[row, f"weather_gdd5_{window}d"] = gdd_sum
                result.at[row, f"weather_precip_sum_{window}d"] = rain_sum
                result.at[row, f"weather_temp_count_{window}d"] = temp_count
                result.at[row, f"weather_precip_count_{window}d"] = rain_count

            season_start = pd.Timestamp(year=date.year, month=4, day=1)
            season_day = int(np.datetime64(season_start, "D").astype("int64"))
            left = np.searchsorted(day, season_day, side="left")
            right = np.searchsorted(day, query_day, side="left")
            season_temp = gdd[left:right]
            season_rain = rain[left:right]
            finite_temp = season_temp[np.isfinite(season_temp)]
            finite_rain = season_rain[np.isfinite(season_rain)]
            result.at[row, "weather_gdd5_season_to_date"] = (
                float(finite_temp.sum()) if len(finite_temp) else np.nan
            )
            result.at[row, "weather_precip_season_to_date"] = (
                float(finite_rain.sum()) if len(finite_rain) else np.nan
            )
            result.at[row, "weather_season_temp_count"] = len(finite_temp)
            result.at[row, "weather_season_precip_count"] = len(finite_rain)
    return result

