"""High-capacity formula+panel expert selected by cross-domain transfer."""
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

import train_formula_collaborative_meta as configured  # noqa: E402,F401
import train_formula_meta as experiment  # noqa: E402


def leaf2_model(numeric: list[str], seed: int) -> Pipeline:
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
    return Pipeline(
        [
            ("prep", prep),
            (
                "model",
                ExtraTreesRegressor(
                    n_estimators=600,
                    min_samples_leaf=2,
                    max_features=0.70,
                    n_jobs=-1,
                    random_state=seed,
                ),
            ),
        ]
    )


experiment.make_model = leaf2_model
experiment.EXPERIMENT_LABEL = "formula_plus_collaborative_panel_leaf2"
experiment.MODEL_PATH = ROOT / "models/formula_collaborative_leaf2.joblib"
experiment.REPORT_PATH = ROOT / "reports/formula_collaborative_leaf2_metrics.json"
experiment.OOF_PATH = ROOT / "reports/formula_collaborative_leaf2_oof.csv"
experiment.OUTPUT_PATH = ROOT / "submission_ensemble_v21_formula_collaborative_leaf2_aggressive.csv"


if __name__ == "__main__":
    experiment.main()
