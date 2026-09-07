"""Evaluate non-tree temporal curve models on released organizer gaps."""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.interpolate import Akima1DInterpolator, PchipInterpolator, UnivariateSpline
from sklearn.metrics import mean_squared_error
from sklearn.model_selection import GroupKFold


ROOT = Path(__file__).resolve().parents[1]
ID = "anon_polygon_id"
DATE = "date"
TARGET = "primary_ndvi"
TRUTH = "primary_ndvi_true"
KEY = [ID, DATE]
REPORT = ROOT / "reports/curve_model_search.json"
VALIDATION_OUTPUT = ROOT / "reports/curve_validation_predictions.csv"
FINAL_OUTPUT = ROOT / "reports/curve_final_predictions.csv"


def rmse(y, prediction) -> float:
    return float(np.sqrt(mean_squared_error(y, prediction)))


def safe_interp(x: np.ndarray, y: np.ndarray, q: np.ndarray) -> np.ndarray:
    if len(x) == 0:
        return np.full(len(q), np.nan)
    return np.interp(q, x, y, left=y[0], right=y[-1])


def local_polynomial(
    x: np.ndarray,
    y: np.ndarray,
    q: np.ndarray,
    *,
    neighbors: int,
    degree: int,
) -> np.ndarray:
    result = np.full(len(q), np.nan)
    if len(x) == 0:
        return result
    for i, query in enumerate(q):
        order = np.argsort(np.abs(x - query))[: min(neighbors, len(x))]
        dx = x[order] - query
        values = y[order]
        bandwidth = max(float(np.max(np.abs(dx))), 4.0)
        scaled = np.abs(dx) / bandwidth
        weight = np.clip(1.0 - scaled**3, 0.0, None) ** 3
        design = np.column_stack([dx**power for power in range(degree + 1)])
        penalty = np.diag([1e-8] + [1e-4] * degree)
        try:
            beta = np.linalg.solve(
                design.T @ (weight[:, None] * design) + penalty,
                design.T @ (weight * values),
            )
            result[i] = beta[0]
        except np.linalg.LinAlgError:
            result[i] = values[np.argmin(np.abs(dx))]
    return result


def rbf_smoother(
    x: np.ndarray,
    y: np.ndarray,
    q: np.ndarray,
    *,
    length_scale: float,
    noise: float,
) -> np.ndarray:
    if len(x) == 0:
        return np.full(len(q), np.nan)
    center = float(np.mean(y))
    distance = x[:, None] - x[None, :]
    kernel = np.exp(-0.5 * (distance / length_scale) ** 2)
    kernel.flat[:: len(x) + 1] += noise**2
    cross = np.exp(-0.5 * ((q[:, None] - x[None, :]) / length_scale) ** 2)
    try:
        alpha = np.linalg.solve(kernel, y - center)
        return center + cross @ alpha
    except np.linalg.LinAlgError:
        return safe_interp(x, y, q)


def predict_curves(data: pd.DataFrame) -> pd.DataFrame:
    data = data.copy().reset_index(drop=True)
    data[DATE] = pd.to_datetime(data[DATE])
    queries = data[data["is_synthetic_gap"].fillna(False)].copy()
    result = queries[KEY].copy()
    methods = [
        "curve_linear",
        "curve_pchip",
        "curve_akima",
        "curve_spline_003",
        "curve_spline_005",
        "curve_spline_008",
        "curve_local1_k6",
        "curve_local1_k10",
        "curve_local2_k8",
        "curve_local2_k12",
        "curve_rbf_l10_n005",
        "curve_rbf_l18_n005",
        "curve_rbf_l30_n005",
        "curve_rbf_l18_n008",
    ]
    for method in methods:
        result[method] = np.nan

    lookup = result.reset_index().set_index(KEY)["index"]
    work = data.assign(_year=data[DATE].dt.year)
    for (_, _), group in work.groupby([ID, "_year"], sort=False):
        target_numeric = pd.to_numeric(group[TARGET], errors="coerce")
        known = group[np.isfinite(target_numeric.to_numpy(dtype=float))].sort_values(
            DATE
        )
        query = group[group["is_synthetic_gap"].fillna(False)].sort_values(DATE)
        if query.empty or known.empty:
            continue
        origin = pd.Timestamp(year=int(group["_year"].iloc[0]), month=1, day=1)
        x = (known[DATE] - origin).dt.days.to_numpy(dtype=float)
        y = known[TARGET].to_numpy(dtype=float)
        q = (query[DATE] - origin).dt.days.to_numpy(dtype=float)
        row_ids = [lookup.loc[(polygon, date)] for polygon, date in query[KEY].itertuples(index=False, name=None)]
        fallback = safe_interp(x, y, q)
        values: dict[str, np.ndarray] = {"curve_linear": fallback}

        if len(x) >= 3:
            values["curve_pchip"] = np.asarray(PchipInterpolator(x, y)(q), dtype=float)
            akima = np.asarray(Akima1DInterpolator(x, y, extrapolate=True)(q), dtype=float)
            values["curve_akima"] = akima
        else:
            values["curve_pchip"] = fallback
            values["curve_akima"] = fallback

        for sigma in (0.03, 0.05, 0.08):
            name = f"curve_spline_{int(sigma * 100):03d}"
            if len(x) >= 5:
                try:
                    spline = UnivariateSpline(
                        x, y, k=min(3, len(x) - 1), s=len(x) * sigma**2
                    )
                    values[name] = np.asarray(spline(q), dtype=float)
                except Exception:
                    values[name] = fallback
            else:
                values[name] = fallback

        values["curve_local1_k6"] = local_polynomial(x, y, q, neighbors=6, degree=1)
        values["curve_local1_k10"] = local_polynomial(x, y, q, neighbors=10, degree=1)
        values["curve_local2_k8"] = local_polynomial(x, y, q, neighbors=8, degree=2)
        values["curve_local2_k12"] = local_polynomial(x, y, q, neighbors=12, degree=2)
        values["curve_rbf_l10_n005"] = rbf_smoother(x, y, q, length_scale=10, noise=0.05)
        values["curve_rbf_l18_n005"] = rbf_smoother(x, y, q, length_scale=18, noise=0.05)
        values["curve_rbf_l30_n005"] = rbf_smoother(x, y, q, length_scale=30, noise=0.05)
        values["curve_rbf_l18_n008"] = rbf_smoother(x, y, q, length_scale=18, noise=0.08)

        for name, prediction in values.items():
            prediction = np.where(np.isfinite(prediction), prediction, fallback)
            result.loc[row_ids, name] = np.clip(prediction, -1.0, 1.0)

    return result


def evaluate(validation: pd.DataFrame) -> dict:
    starts = pd.read_csv(
        ROOT / "data/validation_features.csv", parse_dates=[DATE], usecols=KEY
    ).groupby(ID)[DATE].min()
    historical_ids = starts[starts.dt.year.lt(2025)].index
    scored = validation[
        validation[ID].isin(historical_ids) & validation[DATE].dt.year.lt(2025)
    ].reset_index(drop=True)
    y = scored[TRUTH].to_numpy(dtype=float)
    base = scored["v10_prediction"].to_numpy(dtype=float)
    splitter = GroupKFold(n_splits=5)
    folds = list(splitter.split(scored, groups=scored[ID]))
    rows = []
    for column in [c for c in scored if c.startswith("curve_")]:
        alternative = scored[column].to_numpy(dtype=float)
        if not np.isfinite(alternative).all():
            continue
        best = None
        for weight in np.linspace(0.0, 0.8, 33):
            prediction = np.clip((1.0 - weight) * base + weight * alternative, -1, 1)
            score = rmse(y, prediction)
            if best is None or score < best["rmse"]:
                best = {"weight": float(weight), "rmse": score, "prediction": prediction}
        assert best is not None
        fold_metrics = []
        improved = 0
        for fold, (_, idx) in enumerate(folds):
            before = rmse(y[idx], base[idx])
            after = rmse(y[idx], best["prediction"][idx])
            improved += int(after < before)
            fold_metrics.append({"fold": fold, "v10_rmse": before, "blend_rmse": after})
        rows.append(
            {
                "method": column,
                "standalone_rmse": rmse(y, alternative),
                "blend_weight": best["weight"],
                "blend_rmse": best["rmse"],
                "improvement": rmse(y, base) - best["rmse"],
                "improved_folds": improved,
                "folds": fold_metrics,
            }
        )
    rows.sort(key=lambda item: item["blend_rmse"])
    return {
        "validation_rows": len(scored),
        "validation_polygons": int(scored[ID].nunique()),
        "v10_rmse": rmse(y, base),
        "methods": rows,
    }


def main() -> None:
    validation_features = pd.read_csv(
        ROOT / "data/validation_features.csv", parse_dates=[DATE]
    )
    validation = predict_curves(validation_features)
    truth = pd.read_csv(ROOT / "data/validation_ground_truth.csv", parse_dates=[DATE])
    v5 = pd.read_csv(ROOT / "data/validation_predictions_v5.csv", parse_dates=[DATE]).rename(columns={TRUTH: "v5_prediction"})
    v7 = pd.read_csv(ROOT / "data/validation_predictions_v7.csv", parse_dates=[DATE]).rename(columns={TRUTH: "v7_prediction"})
    validation = validation.merge(truth, on=KEY).merge(v5, on=KEY).merge(v7, on=KEY)
    validation["v10_prediction"] = np.clip(
        validation["v5_prediction"] + 2.8 * (validation["v7_prediction"] - validation["v5_prediction"]),
        -1,
        1,
    )
    report = evaluate(validation)
    validation.to_csv(VALIDATION_OUTPUT, index=False)

    final_features = pd.read_csv(ROOT / "data/final_test_features.csv", parse_dates=[DATE])
    final = predict_curves(final_features)
    final.to_csv(FINAL_OUTPUT, index=False)
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({**report, "methods": report["methods"][:8]}, ensure_ascii=False, indent=2))
    print(f"validation predictions: {VALIDATION_OUTPUT}")
    print(f"final predictions: {FINAL_OUTPUT}")


if __name__ == "__main__":
    main()
