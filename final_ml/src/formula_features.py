"""Leakage-safe formula transforms for gap reconstruction meta-models.

The input frames already contain values computed exclusively from visible
neighbours.  This module only combines those columns row-wise, so it cannot
reintroduce a hidden target.
"""
from __future__ import annotations

from collections.abc import Iterable

import numpy as np
import pandas as pd


FEATURE_GROUPS = ("harmonic_gap", "sensor", "weather", "reliability")


def _numeric(frame: pd.DataFrame, name: str) -> pd.Series:
    if name in frame:
        return pd.to_numeric(frame[name], errors="coerce")
    return pd.Series(np.nan, index=frame.index, dtype=float)


def _safe_ratio(a: pd.Series, b: pd.Series, floor: float = 0.05) -> pd.Series:
    denominator = np.maximum(np.abs(b.to_numpy(dtype=float)), floor)
    sign = np.where(b.to_numpy(dtype=float) < 0.0, -1.0, 1.0)
    return pd.Series(a.to_numpy(dtype=float) / (denominator * sign), index=a.index)


def _symmetric_difference(a: pd.Series, b: pd.Series) -> pd.Series:
    return (a - b) / (a.abs() + b.abs() + 0.05)


def _add_harmonic_gap(out: pd.DataFrame) -> None:
    doy = _numeric(out, "doy")
    angle = 2.0 * np.pi * doy / 365.25
    for harmonic in (2, 3):
        out[f"formula_doy_sin_{harmonic}"] = np.sin(harmonic * angle)
        out[f"formula_doy_cos_{harmonic}"] = np.cos(harmonic * angle)

    dprev = _numeric(out, "target_days_prev1")
    dnext = _numeric(out, "target_days_next1")
    prev = _numeric(out, "target_prev1")
    nxt = _numeric(out, "target_next1")
    total = dprev + dnext
    out["formula_gap_nearest_days"] = pd.concat([dprev, dnext], axis=1).min(axis=1)
    out["formula_gap_farthest_days"] = pd.concat([dprev, dnext], axis=1).max(axis=1)
    out["formula_gap_log_span"] = np.log1p(total.clip(lower=0.0))
    out["formula_gap_asymmetry"] = (dprev - dnext) / (total + 1.0)
    out["formula_gap_prev_fraction"] = dprev / total.replace(0.0, np.nan)
    out["formula_gap_neighbor_abs_delta"] = (nxt - prev).abs()
    out["formula_gap_secant_slope"] = (nxt - prev) / total.replace(0.0, np.nan)

    # Linear interpolation is mathematically equivalent to inverse-distance
    # weighting; exponential kernels provide genuinely different candidates.
    for half_life in (3.0, 7.0, 14.0, 30.0):
        wprev = np.exp(-np.log(2.0) * dprev / half_life)
        wnext = np.exp(-np.log(2.0) * dnext / half_life)
        out[f"formula_target_exp_h{int(half_life)}"] = (
            wprev * prev + wnext * nxt
        ) / (wprev + wnext).replace(0.0, np.nan)

    slope_before = _numeric(out, "target_slope_before")
    slope_after = _numeric(out, "target_slope_after")
    from_prev = prev + slope_before * dprev
    from_next = nxt - slope_after * dnext
    out["formula_slope_from_prev"] = from_prev
    out["formula_slope_from_next"] = from_next
    out["formula_slope_bridge"] = (from_prev + from_next) / 2.0
    out["formula_slope_change"] = slope_after - slope_before


def _add_sensor(out: pd.DataFrame) -> None:
    ndvi_names = ["s2_ndvi", "landsat_ndvi", "modis_ndvi"]
    ndvi = {name: _numeric(out, f"{name}_linear") for name in ndvi_names}
    matrix = pd.concat(ndvi.values(), axis=1)
    out["formula_sensor_ndvi_median"] = matrix.median(axis=1)
    out["formula_sensor_ndvi_mean"] = matrix.mean(axis=1)
    out["formula_sensor_ndvi_std"] = matrix.std(axis=1, ddof=0)
    out["formula_sensor_ndvi_range"] = matrix.max(axis=1) - matrix.min(axis=1)

    for left, right in (
        ("s2_ndvi", "landsat_ndvi"),
        ("s2_ndvi", "modis_ndvi"),
        ("landsat_ndvi", "modis_ndvi"),
    ):
        a, b = ndvi[left], ndvi[right]
        key = f"{left}_vs_{right}"
        out[f"formula_{key}_diff"] = a - b
        out[f"formula_{key}_ratio"] = _safe_ratio(a, b)
        out[f"formula_{key}_symdiff"] = _symmetric_difference(a, b)

    target_linear = _numeric(out, "target_linear")
    baseline = _numeric(out, "base_prediction")
    for name, values in ndvi.items():
        out[f"formula_{name}_minus_target_linear"] = values - target_linear
        out[f"formula_{name}_minus_base"] = values - baseline

    # Cross-index relations help distinguish real vegetation movement from a
    # sensor-specific atmospheric artefact.
    index_pairs = (
        ("s2_ndvi", "s2_evi"),
        ("landsat_ndvi", "landsat_evi"),
        ("modis_ndvi", "modis_evi"),
        ("s2_ndvi", "s2_ndwi"),
        ("landsat_ndvi", "landsat_ndwi"),
    )
    for ndvi_name, other_name in index_pairs:
        a = _numeric(out, f"{ndvi_name}_linear")
        b = _numeric(out, f"{other_name}_linear")
        out[f"formula_{ndvi_name}_minus_{other_name}"] = a - b
        out[f"formula_{ndvi_name}_to_{other_name}_symdiff"] = (
            _symmetric_difference(a, b)
        )


def _add_weather(out: pd.DataFrame) -> None:
    temp = _numeric(out, "era5_temp_c_linear")
    precip = _numeric(out, "era5_precip_mm_linear").clip(lower=0.0)
    span = _numeric(out, "target_span_days").clip(lower=0.0, upper=60.0)
    out["formula_gdd5_local"] = (temp - 5.0).clip(lower=0.0)
    out["formula_gdd10_local"] = (temp - 10.0).clip(lower=0.0)
    out["formula_precip_log1p"] = np.log1p(precip)
    out["formula_temp_gap_exposure"] = (temp - 5.0).clip(lower=0.0) * span
    out["formula_precip_gap_exposure"] = precip * span

    temp_prev = _numeric(out, "era5_temp_c_prev1")
    temp_next = _numeric(out, "era5_temp_c_next1")
    rain_prev = _numeric(out, "era5_precip_mm_prev1").clip(lower=0.0)
    rain_next = _numeric(out, "era5_precip_mm_next1").clip(lower=0.0)
    out["formula_temp_abs_change"] = (temp_next - temp_prev).abs()
    out["formula_rain_neighbour_sum"] = rain_prev + rain_next
    out["formula_rain_neighbour_max"] = pd.concat(
        [rain_prev, rain_next], axis=1
    ).max(axis=1)

    # Explicit seasonal interaction: the same temperature means something
    # different during green-up and senescence.
    out["formula_temp_x_doy_sin"] = temp * _numeric(out, "doy_sin")
    out["formula_temp_x_doy_cos"] = temp * _numeric(out, "doy_cos")


def _add_reliability(out: pd.DataFrame) -> None:
    nref = _numeric(out, "n_reference_years_linear").clip(lower=0.0)
    out["formula_climatology_reliability"] = nref / (nref + 2.0)
    out["formula_climatology_low_support"] = (nref < 3.0).astype(float)

    hist_count = _numeric(out, "hist_doy_count").clip(lower=0.0)
    hist_mean = _numeric(out, "hist_doy_mean")
    hist_std = _numeric(out, "hist_doy_std").clip(lower=0.03)
    base = _numeric(out, "base_prediction")
    out["formula_history_reliability"] = hist_count / (hist_count + 3.0)
    out["formula_base_hist_z"] = (base - hist_mean) / hist_std

    clim_mean = _numeric(out, "ndvi_climatology_mean_linear")
    clim_std = _numeric(out, "ndvi_climatology_std_linear").clip(lower=0.04)
    out["formula_base_climatology_z"] = (base - clim_mean) / clim_std
    out["formula_target_linear_climatology_z"] = (
        _numeric(out, "target_linear") - clim_mean
    ) / clim_std

    # Disagreement between independent baselines is also an uncertainty proxy.
    components = pd.concat(
        [
            _numeric(out, "baseline_mean"),
            _numeric(out, "baseline_linear"),
            _numeric(out, "sensor_expert_prediction"),
            _numeric(out, "base_prediction"),
        ],
        axis=1,
    )
    out["formula_model_disagreement_std"] = components.std(axis=1, ddof=0)
    out["formula_model_disagreement_range"] = (
        components.max(axis=1) - components.min(axis=1)
    )


def add_formula_features(
    frame: pd.DataFrame,
    groups: Iterable[str] = FEATURE_GROUPS,
) -> pd.DataFrame:
    """Return a copy with selected deterministic feature groups appended."""
    selected = tuple(groups)
    unknown = set(selected) - set(FEATURE_GROUPS)
    if unknown:
        raise ValueError(f"Unknown formula feature groups: {sorted(unknown)}")
    out = frame.copy()
    if "harmonic_gap" in selected:
        _add_harmonic_gap(out)
    if "sensor" in selected:
        _add_sensor(out)
    if "weather" in selected:
        _add_weather(out)
    if "reliability" in selected:
        _add_reliability(out)
    formula = [column for column in out if column.startswith("formula_")]
    out[formula] = out[formula].replace([np.inf, -np.inf], np.nan)
    return out

