"""Confirm leaf=2 inside the asymmetric target-ID protocol."""
from __future__ import annotations

import sys
from pathlib import Path

from sklearn.compose import ColumnTransformer
from sklearn.ensemble import ExtraTreesRegressor
from sklearn.impute import SimpleImputer
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "experiments"))

import search_asymmetric_id_meta as experiment  # noqa: E402


def leaf2_model(numeric: list[str], seed: int, *, include_id: bool) -> Pipeline:
    categorical = ["crop_type", experiment.ID] if include_id else ["crop_type"]
    prep = ColumnTransformer(
        [
            (
                "numeric",
                SimpleImputer(strategy="median", keep_empty_features=True),
                numeric,
            ),
            (
                "categorical",
                OneHotEncoder(handle_unknown="ignore", sparse_output=False),
                categorical,
            ),
        ],
        sparse_threshold=0.0,
    )
    return Pipeline(
        [
            ("prep", prep),
            (
                "model",
                ExtraTreesRegressor(
                    n_estimators=520,
                    min_samples_leaf=2,
                    max_features=0.70,
                    n_jobs=-1,
                    random_state=seed,
                ),
            ),
        ]
    )


experiment.model = leaf2_model
experiment.REPORT = ROOT / "reports/asymmetric_id_leaf2_search.json"
experiment.CACHE = ROOT / "reports/cache/asymmetric_id_leaf2_oof.joblib"


if __name__ == "__main__":
    experiment.main()
