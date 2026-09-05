"""Cross-polygon residual prediction using a date-by-polygon panel.

Unlike a plain date mean, each polygon gets a ridge model of how its temporal
interpolation residual co-moves with the other polygons observed on the same
date.  Only visible measurements are used; query targets never enter fitting.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.linear_model import Ridge


ID_COL = "anon_polygon_id"
DATE_COL = "date"
TARGET_COL = "primary_ndvi"
SOURCES = ("landsat", "modis", "s2")


def _visible_residuals(
    data: pd.DataFrame,
    *,
    target_min: float = -0.15,
    target_max: float = 0.98,
) -> pd.DataFrame:
    frame = data.copy()
    frame[DATE_COL] = pd.to_datetime(frame[DATE_COL])
    target = pd.to_numeric(frame[TARGET_COL], errors="coerce")
    visible = np.isfinite(target.to_numpy(dtype=float))
    if "is_synthetic_gap" in frame:
        visible &= ~frame["is_synthetic_gap"].fillna(False).astype(bool).to_numpy()
    columns = [
        ID_COL,
        DATE_COL,
        TARGET_COL,
        "s2_ndvi",
        "landsat_ndvi",
        "modis_ndvi",
    ]
    observed = frame.loc[visible, columns].sort_values([ID_COL, DATE_COL]).copy()
    grouped = observed.groupby(ID_COL, sort=False)
    previous = grouped[TARGET_COL].shift(1)
    following = grouped[TARGET_COL].shift(-1)
    previous_date = grouped[DATE_COL].shift(1)
    following_date = grouped[DATE_COL].shift(-1)
    days_previous = (observed[DATE_COL] - previous_date).dt.days.astype(float)
    days_following = (following_date - observed[DATE_COL]).dt.days.astype(float)
    interpolation = (
        previous * days_following + following * days_previous
    ) / (days_previous + days_following)
    observed["residual"] = observed[TARGET_COL] - interpolation
    observed["source"] = np.select(
        [
            observed["s2_ndvi"].notna(),
            observed["landsat_ndvi"].notna(),
            observed["modis_ndvi"].notna(),
        ],
        ["s2", "landsat", "modis"],
        default="unknown",
    )
    finite = np.isfinite(observed["residual"].to_numpy(dtype=float))
    physical = observed[TARGET_COL].between(target_min, target_max).to_numpy()
    observed = observed.loc[finite & physical & observed["source"].ne("unknown")].copy()
    # A single corrupted donor must not dominate an entire acquisition date.
    observed["residual"] = observed["residual"].clip(-0.30, 0.30)
    return observed


def predict_collaborative_shock(
    data: pd.DataFrame,
    query: pd.DataFrame,
    *,
    alpha: float = 0.30,
    minimum_training_rows: int = 15,
) -> pd.DataFrame:
    """Predict a synchronous residual for every query row.

    ``query`` must contain keys and ``expert_<source>_probability`` columns.
    Ridge is fitted independently for each target polygon and possible source.
    """
    observed = _visible_residuals(data)
    result = query.reset_index(drop=True).copy()
    result[DATE_COL] = pd.to_datetime(result[DATE_COL])
    source_prediction = np.zeros((len(result), len(SOURCES)), dtype=float)
    source_available = np.zeros((len(result), len(SOURCES)), dtype=bool)
    training_rows = np.zeros((len(result), len(SOURCES)), dtype=float)

    for source_index, source in enumerate(SOURCES):
        part = observed[observed["source"].eq(source)]
        panel = part.pivot(index=DATE_COL, columns=ID_COL, values="residual")
        if panel.empty:
            continue
        centered = panel - panel.mean(axis=0)

        for polygon_id, row_index in result.groupby(ID_COL, sort=False).groups.items():
            rows = np.asarray(list(row_index), dtype=int)
            if polygon_id not in centered.columns:
                continue
            target = centered[polygon_id].dropna()
            if len(target) < minimum_training_rows:
                continue
            donors = [column for column in centered.columns if column != polygon_id]
            if not donors:
                continue

            train_panel = centered.reindex(target.index)[donors]
            donor_mean = train_panel.mean(axis=1).fillna(0.0).to_numpy(dtype=float)
            donor_fraction = train_panel.notna().mean(axis=1).to_numpy(dtype=float)
            matrix = np.column_stack(
                [
                    train_panel.fillna(0.0).to_numpy(dtype=float),
                    donor_mean,
                    donor_fraction,
                ]
            )
            model = Ridge(alpha=alpha, fit_intercept=True)
            model.fit(matrix, target.to_numpy(dtype=float))

            dates = result.loc[rows, DATE_COL]
            query_panel = centered.reindex(dates)[donors]
            available = query_panel.notna().any(axis=1).to_numpy()
            query_mean = query_panel.mean(axis=1).fillna(0.0).to_numpy(dtype=float)
            query_fraction = query_panel.notna().mean(axis=1).to_numpy(dtype=float)
            query_matrix = np.column_stack(
                [
                    query_panel.fillna(0.0).to_numpy(dtype=float),
                    query_mean,
                    query_fraction,
                ]
            )
            source_prediction[rows, source_index] = model.predict(query_matrix)
            source_available[rows, source_index] = available
            training_rows[rows, source_index] = len(target)

    probabilities = np.column_stack(
        [
            result[f"expert_{source}_probability"].fillna(0.0).to_numpy(dtype=float)
            for source in SOURCES
        ]
    )
    weights = probabilities * source_available
    denominator = weights.sum(axis=1)
    result["collaborative_shock"] = np.divide(
        np.sum(weights * source_prediction, axis=1),
        denominator,
        out=np.zeros(len(result), dtype=float),
        where=denominator > 0,
    )
    result["collaborative_source_probability"] = denominator
    result["collaborative_available_sources"] = source_available.sum(axis=1)
    result["collaborative_training_rows"] = np.divide(
        np.sum(weights * training_rows, axis=1),
        denominator,
        out=np.zeros(len(result), dtype=float),
        where=denominator > 0,
    )
    for index, source in enumerate(SOURCES):
        result[f"collaborative_{source}_shock"] = source_prediction[:, index]
        result[f"collaborative_{source}_available"] = source_available[:, index].astype(
            float
        )
    return result

