"""Fast bidirectional transfer search for formula+panel tree regularization."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import ExtraTreesRegressor, RandomForestRegressor
from sklearn.impute import SimpleImputer
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder


ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "src"), str(ROOT / "experiments")]

from formula_features import FEATURE_GROUPS, add_formula_features  # noqa: E402
from search_multidomain_meta import shared_numeric  # noqa: E402


KEY = ["anon_polygon_id", "date"]
REPORT = ROOT / "reports/formula_collab_hyperparams.json"


def rmse(y, prediction) -> float:
    return float(np.sqrt(np.mean((np.asarray(y) - np.asarray(prediction)) ** 2)))


def frames() -> tuple[pd.DataFrame, pd.DataFrame, list[str]]:
    pseudo, validation = joblib.load(
        ROOT / "reports/cache/multidomain_meta_frames.joblib"
    )
    pseudo = add_formula_features(pseudo, FEATURE_GROUPS)
    validation = add_formula_features(validation, FEATURE_GROUPS)
    pdeta, vdeta, _ = joblib.load(
        ROOT / "reports/cache/collaborative_shock_frames.joblib"
    )
    columns = [column for column in pdeta if column.startswith("collaborative_")]
    pseudo = pseudo.merge(
        pdeta[[*KEY, "calibration_mask", *columns]],
        on=[*KEY, "calibration_mask"],
        validate="one_to_one",
    )
    validation = validation.merge(
        vdeta[[*KEY, *columns]], on=KEY, validate="one_to_one"
    )
    return pseudo, validation, shared_numeric(pseudo, validation)


def make_model(
    numeric: list[str],
    *,
    family: str,
    leaf: int,
    max_features: float,
    seed: int,
) -> Pipeline:
    prep = ColumnTransformer(
        [
            (
                "numeric",
                SimpleImputer(strategy="median", keep_empty_features=True),
                numeric,
            ),
            (
                "crop",
                OneHotEncoder(handle_unknown="ignore", sparse_output=False),
                ["crop_type"],
            ),
        ],
        sparse_threshold=0.0,
    )
    common = dict(
        n_estimators=220,
        min_samples_leaf=leaf,
        max_features=max_features,
        n_jobs=-1,
        random_state=seed,
    )
    if family == "extra":
        model = ExtraTreesRegressor(**common)
    elif family == "forest":
        model = RandomForestRegressor(**common, bootstrap=True, max_samples=0.85)
    else:
        raise ValueError(family)
    return Pipeline([("prep", prep), ("model", model)])


def target(frame: pd.DataFrame) -> np.ndarray:
    return (
        frame["target_true"].to_numpy(dtype=float)
        - frame["base_prediction"].to_numpy(dtype=float)
    )


def best_blend(frame: pd.DataFrame, correction: np.ndarray) -> dict:
    y = frame["target_true"].to_numpy(dtype=float)
    base = frame["base_prediction"].to_numpy(dtype=float)
    rows = []
    for weight in np.linspace(0.0, 1.50, 61):
        pred = np.clip(base + weight * correction, -1.0, 1.0)
        rows.append((rmse(y, pred), float(weight)))
    score, weight = min(rows)
    return {
        "base_rmse": rmse(y, base),
        "rmse": score,
        "improvement": rmse(y, base) - score,
        "weight": weight,
    }


def main() -> None:
    pseudo, validation, numeric = frames()
    settings = []
    for leaf in (2, 3, 5, 8, 12, 20):
        for max_features in (0.40, 0.60, 0.80, 1.00):
            settings.append(("extra", leaf, max_features))
    for leaf in (3, 5, 10, 20):
        for max_features in (0.50, 0.80):
            settings.append(("forest", leaf, max_features))

    results = []
    for number, (family, leaf, max_features) in enumerate(settings):
        name = f"{family}_leaf{leaf}_mf{max_features:.2f}"
        print(name, flush=True)
        pmodel = make_model(
            numeric,
            family=family,
            leaf=leaf,
            max_features=max_features,
            seed=51000 + number,
        )
        pmodel.fit(pseudo, target(pseudo))
        on_validation = best_blend(validation, pmodel.predict(validation))
        vmodel = make_model(
            numeric,
            family=family,
            leaf=leaf,
            max_features=max_features,
            seed=52000 + number,
        )
        vmodel.fit(validation, target(validation))
        on_pseudo = best_blend(pseudo, vmodel.predict(pseudo))
        row = {
            "name": name,
            "family": family,
            "leaf": leaf,
            "max_features": max_features,
            "train_pseudo_test_validation": on_validation,
            "train_validation_test_pseudo": on_pseudo,
            "mean_improvement": (
                on_validation["improvement"] + on_pseudo["improvement"]
            )
            / 2.0,
        }
        results.append(row)
        REPORT.write_text(
            json.dumps({"results": results}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        print(json.dumps(row, ensure_ascii=False), flush=True)
    results.sort(key=lambda row: row["mean_improvement"], reverse=True)
    report = {
        "protocol": "fit one full domain and evaluate only on the other domain",
        "features": len(numeric),
        "trees": 220,
        "results": results,
        "best": results[0],
    }
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"best": results[:8]}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
