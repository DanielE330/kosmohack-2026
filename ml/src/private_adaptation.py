"""Self-supervised per-polygon calibration for the v3 ensemble.

The private table contains many visible ``primary_ndvi`` values around the real
gaps.  We can hide a subset of those visible values, obtain honest pseudo-gap
predictions, and learn a small local correction for each polygon.  Real private
targets are never used.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import ExtraTreesRegressor
from sklearn.impute import SimpleImputer
from sklearn.linear_model import Ridge
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from config import DATE_COL, GAP_FLAG_COL, ID_COL, TARGET_COL
from gap_features import align_feature_columns, build_gap_features


LOCAL_HISTORY_FEATURES = [
    "climatology_plus_residual",
    "hist_doy_median",
    "hist_doy_mean",
    "hist_doy_std",
    "hist_doy_count",
    "hist_residual_mean",
    "date_target_median",
    "date_target_mean",
    "date_target_count",
    "date_crop_target_median",
    "date_s2_ndvi_availability",
    "date_s2_ndvi_median",
    "date_landsat_ndvi_availability",
    "date_landsat_ndvi_median",
    "date_modis_ndvi_availability",
    "date_modis_ndvi_median",
]

CALIBRATION_FEATURES = [
    "v3_prediction",
    "v2_prediction",
    "reweighted_prediction",
    "global_prediction",
    "wheat_prediction",
    "extra_trees_prediction",
    "baseline",
    "baseline_mean",
    "baseline_linear",
    "baseline_climatology",
    "year",
    "doy_sin",
    "doy_cos",
    *LOCAL_HISTORY_FEATURES,
]

GLOBAL_CONTEXT_FEATURES = [
    "target_days_prev1",
    "target_days_next1",
    "target_span_days",
]

GLOBAL_CALIBRATION_FEATURES = [
    *CALIBRATION_FEATURES,
    *GLOBAL_CONTEXT_FEATURES,
]

GLOBAL_CATEGORICAL_FEATURES = [ID_COL, "crop_type"]

RIDGE_ALPHA = 1.0
MAX_LOCAL_BLEND = 0.33
BLEND_PER_CALIBRATION_ROW = 0.0025
MAX_ABS_LOCAL_CORRECTION = 0.10
MIN_CALIBRATION_ROWS = 12

# The global correction complements the local per-polygon Ridge.  Its weights
# were selected on OOF pseudo-gaps and checked with an outer GroupKFold split.
GLOBAL_RIDGE_ALPHA = 0.1
MAX_ABS_GLOBAL_CORRECTION = 0.12
DEFAULT_GLOBAL_BLEND = 0.35
GLOBAL_BLEND_BY_CROP = {
    "зерновые": 0.65,
    "озимая пшеница": 0.35,
    "пастбища/зерновые": 0.30,
    "подсолнечник": 0.35,
}

TREE_N_ESTIMATORS = 160
TREE_MIN_SAMPLES_LEAF = 3
TREE_MAX_FEATURES = 0.70
TREE_RANDOM_STATE = 42
MAX_ABS_TREE_CORRECTION = 0.12

# (global Ridge weight, global ExtraTrees weight).  These were selected on the
# complete OOF table only after nested outer-fold checks improved all 5 folds.
NONLINEAR_BLEND_BY_CROP = {
    "зерновые": (0.45, 0.45),
    "озимая пшеница": (0.30, 0.20),
    "пастбища/зерновые": (0.15, 0.45),
    "подсолнечник": (0.20, 0.30),
}
DEFAULT_NONLINEAR_BLEND = (0.30, 0.20)


@dataclass(frozen=True)
class V3Bundles:
    global_bundle: dict
    wheat_bundle: dict
    extra_bundle: dict
    reweighted_bundle: dict


def _bundle_prediction(features: pd.DataFrame, meta: pd.DataFrame, bundle: dict) -> np.ndarray:
    matrix = align_feature_columns(features, bundle["feature_columns"]).replace(
        [np.inf, -np.inf], np.nan
    )
    baseline = (
        meta["baseline"].astype(float).fillna(bundle["target_median"]).to_numpy()
    )
    return baseline + float(bundle["residual_weight"]) * bundle["model"].predict(matrix)


def predict_v3_components(
    private: pd.DataFrame,
    query_mask: Iterable[bool],
    bundles: V3Bundles,
    *,
    reference: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """Predict arbitrary private rows once and return all v3 components."""
    data = private.copy().reset_index(drop=True)
    data[DATE_COL] = pd.to_datetime(data[DATE_COL])
    mask = np.asarray(list(query_mask), dtype=bool)
    if len(mask) != len(data) or not mask.any():
        raise ValueError("query_mask должен совпадать с private и содержать True")

    data["_private_row"] = np.arange(len(data))
    data["_source"] = "private"
    data["_requested_query"] = mask
    frames = []
    if reference is not None:
        ref = reference.copy().reset_index(drop=True)
        ref[DATE_COL] = pd.to_datetime(ref[DATE_COL])
        ref["_private_row"] = -1
        ref["_source"] = "reference"
        ref["_requested_query"] = False
        frames.append(ref)
    frames.append(data)
    combined = pd.concat(frames, ignore_index=True, sort=False)
    combined_query = combined["_source"].eq("private") & combined[
        "_requested_query"
    ].fillna(False)
    built = build_gap_features(combined, combined_query)

    global_prediction = _bundle_prediction(
        built.features, built.meta, bundles.global_bundle
    )
    if bundles.global_bundle.get("clip_predictions", False):
        global_prediction = np.clip(global_prediction, -1.0, 1.0)

    # Store global as the neutral wheat feature for all non-wheat rows.  This
    # matches the OOF calibration experiment where a specialist is absent.
    wheat_prediction = global_prediction.copy()
    hgb_prediction = global_prediction.copy()
    special_crop = bundles.wheat_bundle.get("special_crop", "озимая пшеница")
    wheat_mask = (
        built.meta["crop_type"].fillna("unknown").astype(str).eq(special_crop).to_numpy()
    )
    if wheat_mask.any() and float(bundles.wheat_bundle.get("blend_weight", 0.0)) > 0:
        wheat_all = _bundle_prediction(
            built.features, built.meta, bundles.wheat_bundle
        )
        wheat_prediction[wheat_mask] = wheat_all[wheat_mask]
        wheat_blend = float(bundles.wheat_bundle["blend_weight"])
        hgb_prediction[wheat_mask] = (
            (1.0 - wheat_blend) * global_prediction[wheat_mask]
            + wheat_blend * wheat_prediction[wheat_mask]
        )
    if bundles.wheat_bundle.get("clip_predictions", False):
        hgb_prediction = np.clip(hgb_prediction, -1.0, 1.0)

    extra_prediction = _bundle_prediction(
        built.features, built.meta, bundles.extra_bundle
    )
    extra_blend = float(bundles.extra_bundle["blend_weight"])
    v2_prediction = (
        (1.0 - extra_blend) * hgb_prediction
        + extra_blend * extra_prediction
    )

    reweighted_prediction = _bundle_prediction(
        built.features, built.meta, bundles.reweighted_bundle
    )
    reweighted_blend = float(bundles.reweighted_bundle["blend_weight"])
    v3_prediction = (
        (1.0 - reweighted_blend) * v2_prediction
        + reweighted_blend * reweighted_prediction
    )
    if bundles.reweighted_bundle.get("clip_predictions", True):
        v3_prediction = np.clip(v3_prediction, -1.0, 1.0)

    combined_rows = built.features.index.to_numpy(dtype=int)
    private_rows = combined.loc[combined_rows, "_private_row"].to_numpy(dtype=int)
    if "crop_type" not in data:
        data["crop_type"] = "unknown"
    result = data.loc[
        private_rows, [ID_COL, DATE_COL, "crop_type", "_private_row"]
    ].copy()
    for column in (
        "baseline_mean",
        "baseline_linear",
        "baseline_climatology",
        "baseline",
    ):
        result[column] = built.meta[column].to_numpy(dtype=float)
    result["global_prediction"] = global_prediction
    result["wheat_prediction"] = wheat_prediction
    result["extra_trees_prediction"] = extra_prediction
    result["v2_prediction"] = v2_prediction
    result["reweighted_prediction"] = reweighted_prediction
    result["v3_prediction"] = v3_prediction
    result["year"] = result[DATE_COL].dt.year.astype(float)
    doy = result[DATE_COL].dt.dayofyear.astype(float)
    result["doy_sin"] = np.sin(2 * np.pi * doy / 365.25)
    result["doy_cos"] = np.cos(2 * np.pi * doy / 365.25)
    for column in LOCAL_HISTORY_FEATURES:
        result[column] = built.features[column].to_numpy(dtype=float)
    for column in GLOBAL_CONTEXT_FEATURES:
        result[column] = built.features[column].to_numpy(dtype=float)
    return result.reset_index(drop=True)


def make_disjoint_calibration_masks(
    private: pd.DataFrame,
    *,
    n_masks: int = 4,
    rate: float = 0.15,
    seed: int = 2026,
) -> list[np.ndarray]:
    """Create non-overlapping pseudo-gaps while hiding only ``rate`` per pass."""
    if n_masks < 1 or not 0 < rate < 0.5:
        raise ValueError("Некорректные n_masks/rate")
    data = private.copy().reset_index(drop=True)
    dates = pd.to_datetime(data[DATE_COL])
    candidates = data[TARGET_COL].notna() & ~data[GAP_FLAG_COL].fillna(False).astype(bool)
    masks = [np.zeros(len(data), dtype=bool) for _ in range(n_masks)]
    rng = np.random.default_rng(seed)

    groups = data.loc[candidates].groupby([ID_COL, dates[candidates].dt.year]).groups
    for indices in groups.values():
        shuffled = np.asarray(list(indices), dtype=int)
        rng.shuffle(shuffled)
        per_mask = max(1, int(round(len(shuffled) * rate)))
        per_mask = min(per_mask, max(1, len(shuffled) - 2))
        cursor = 0
        for mask in masks:
            chosen = shuffled[cursor : cursor + per_mask]
            if len(chosen) == 0:
                break
            mask[chosen] = True
            cursor += per_mask
    return masks


def build_private_calibration_table(
    private: pd.DataFrame,
    bundles: V3Bundles,
    *,
    reference: pd.DataFrame | None = None,
    n_masks: int = 4,
    rate: float = 0.15,
    seed: int = 2026,
) -> pd.DataFrame:
    """Predict visible private values as pseudo-gaps and attach their truth."""
    data = private.copy().reset_index(drop=True)
    actual_gap = data[GAP_FLAG_COL].fillna(False).astype(bool).to_numpy()
    parts = []
    for mask_number, pseudo_mask in enumerate(
        make_disjoint_calibration_masks(
            data, n_masks=n_masks, rate=rate, seed=seed
        )
    ):
        if not pseudo_mask.any():
            continue
        predicted = predict_v3_components(
            data,
            actual_gap | pseudo_mask,
            bundles,
            reference=reference,
        )
        pseudo_rows = set(np.flatnonzero(pseudo_mask))
        part = predicted[predicted["_private_row"].isin(pseudo_rows)].copy()
        truth = data.loc[part["_private_row"].to_numpy(dtype=int), TARGET_COL].to_numpy(
            dtype=float
        )
        part["target_true"] = truth
        part["calibration_mask"] = mask_number
        parts.append(part)
    if not parts:
        raise ValueError("Не удалось создать private calibration rows")
    result = pd.concat(parts, ignore_index=True)
    if result.duplicated([ID_COL, "_private_row"]).any():
        raise AssertionError("Calibration masks должны быть непересекающимися")
    return result


def apply_polygon_calibration(
    actual: pd.DataFrame,
    calibration: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Fit a conservative local Ridge correction and apply it to real gaps."""
    result = actual.copy()
    result["local_correction_raw"] = 0.0
    result["local_blend_weight"] = 0.0
    result["calibration_rows"] = 0
    diagnostics = []

    for polygon_id, indices in result.groupby(ID_COL).groups.items():
        rows = np.asarray(list(indices), dtype=int)
        local = calibration[calibration[ID_COL].eq(polygon_id)].copy()
        n_rows = len(local)
        if n_rows < MIN_CALIBRATION_ROWS:
            diagnostics.append(
                {
                    ID_COL: polygon_id,
                    "calibration_rows": n_rows,
                    "local_blend_weight": 0.0,
                    "mean_abs_raw_correction": 0.0,
                    "status": "fallback_v3",
                }
            )
            continue

        model = make_pipeline(
            SimpleImputer(strategy="median", keep_empty_features=True),
            StandardScaler(),
            Ridge(alpha=RIDGE_ALPHA),
        )
        target_residual = (
            local["target_true"].to_numpy(dtype=float)
            - local["v3_prediction"].to_numpy(dtype=float)
        )
        model.fit(local[CALIBRATION_FEATURES], target_residual)
        raw_correction = model.predict(result.loc[rows, CALIBRATION_FEATURES])
        raw_correction = np.clip(
            raw_correction,
            -MAX_ABS_LOCAL_CORRECTION,
            MAX_ABS_LOCAL_CORRECTION,
        )
        blend = min(MAX_LOCAL_BLEND, BLEND_PER_CALIBRATION_ROW * n_rows)
        result.loc[rows, "local_correction_raw"] = raw_correction
        result.loc[rows, "local_blend_weight"] = blend
        result.loc[rows, "calibration_rows"] = n_rows
        diagnostics.append(
            {
                ID_COL: polygon_id,
                "calibration_rows": n_rows,
                "local_blend_weight": blend,
                "mean_abs_raw_correction": float(np.mean(np.abs(raw_correction))),
                "status": "adapted",
            }
        )

    result["v4_prediction"] = np.clip(
        result["v3_prediction"]
        + result["local_blend_weight"] * result["local_correction_raw"],
        -1.0,
        1.0,
    )
    return result, pd.DataFrame(diagnostics)


def predict_global_residual_correction(
    actual: pd.DataFrame,
    calibration: pd.DataFrame,
) -> np.ndarray:
    """Learn one nonlinear-context-aware linear correction over all polygons."""
    if len(calibration) < MIN_CALIBRATION_ROWS:
        return np.zeros(len(actual), dtype=float)

    numeric_pipeline = make_pipeline(
        SimpleImputer(strategy="median", keep_empty_features=True),
        StandardScaler(),
    )
    preprocessor = ColumnTransformer(
        [
            ("numeric", numeric_pipeline, GLOBAL_CALIBRATION_FEATURES),
            (
                "categorical",
                OneHotEncoder(handle_unknown="ignore", sparse_output=False),
                GLOBAL_CATEGORICAL_FEATURES,
            ),
        ],
        sparse_threshold=0.0,
    )
    model = make_pipeline(
        preprocessor,
        Ridge(alpha=GLOBAL_RIDGE_ALPHA, solver="lsqr"),
    )
    target_residual = (
        calibration["target_true"].to_numpy(dtype=float)
        - calibration["v3_prediction"].to_numpy(dtype=float)
    )
    model.fit(calibration, target_residual)
    return np.clip(
        model.predict(actual),
        -MAX_ABS_GLOBAL_CORRECTION,
        MAX_ABS_GLOBAL_CORRECTION,
    )


def apply_global_calibration(
    adapted: pd.DataFrame,
    calibration: pd.DataFrame,
) -> pd.DataFrame:
    """Add a conservative cross-polygon correction on top of v4."""
    result = adapted.copy()
    result["global_correction_raw"] = predict_global_residual_correction(
        result, calibration
    )
    result["global_blend_weight"] = (
        result["crop_type"]
        .map(GLOBAL_BLEND_BY_CROP)
        .fillna(DEFAULT_GLOBAL_BLEND)
        .astype(float)
    )
    result["v5_prediction"] = np.clip(
        result["v4_prediction"]
        + result["global_blend_weight"] * result["global_correction_raw"],
        -1.0,
        1.0,
    )
    return result


def predict_tree_residual_correction(
    actual: pd.DataFrame,
    calibration: pd.DataFrame,
) -> np.ndarray:
    """Fit a nonlinear residual correction on visible private pseudo-gaps."""
    if len(calibration) < MIN_CALIBRATION_ROWS:
        return np.zeros(len(actual), dtype=float)

    preprocessor = ColumnTransformer(
        [
            (
                "numeric",
                SimpleImputer(strategy="median", keep_empty_features=True),
                GLOBAL_CALIBRATION_FEATURES,
            ),
            (
                "categorical",
                OneHotEncoder(handle_unknown="ignore", sparse_output=False),
                GLOBAL_CATEGORICAL_FEATURES,
            ),
        ],
        sparse_threshold=0.0,
    )
    model = make_pipeline(
        preprocessor,
        ExtraTreesRegressor(
            n_estimators=TREE_N_ESTIMATORS,
            min_samples_leaf=TREE_MIN_SAMPLES_LEAF,
            max_features=TREE_MAX_FEATURES,
            n_jobs=-1,
            random_state=TREE_RANDOM_STATE,
        ),
    )
    target_residual = (
        calibration["target_true"].to_numpy(dtype=float)
        - calibration["v3_prediction"].to_numpy(dtype=float)
    )
    model.fit(calibration, target_residual)
    return np.clip(
        model.predict(actual),
        -MAX_ABS_TREE_CORRECTION,
        MAX_ABS_TREE_CORRECTION,
    )


def apply_nonlinear_global_calibration(
    adapted: pd.DataFrame,
    calibration: pd.DataFrame,
) -> pd.DataFrame:
    """Blend Ridge and ExtraTrees residual corrections on top of local v4."""
    result = adapted.copy()
    result["global_correction_raw"] = predict_global_residual_correction(
        result, calibration
    )
    result["tree_correction_raw"] = predict_tree_residual_correction(
        result, calibration
    )
    weights = result["crop_type"].map(NONLINEAR_BLEND_BY_CROP)
    weights = weights.apply(
        lambda value: value
        if isinstance(value, tuple)
        else DEFAULT_NONLINEAR_BLEND
    )
    result["global_blend_weight"] = weights.map(lambda value: value[0])
    result["tree_blend_weight"] = weights.map(lambda value: value[1])
    result["v7_prediction"] = np.clip(
        result["v4_prediction"]
        + result["global_blend_weight"] * result["global_correction_raw"]
        + result["tree_blend_weight"] * result["tree_correction_raw"],
        -1.0,
        1.0,
    )
    return result
