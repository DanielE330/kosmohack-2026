"""Train formula meta experts with leakage-safe collaborative panel features."""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import joblib


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "experiments"))

import train_formula_meta as experiment  # noqa: E402


KEY = ["anon_polygon_id", "date"]


def collaborative_columns(frame: pd.DataFrame) -> list[str]:
    return [column for column in frame if column.startswith("collaborative_")]


def augment_train(
    pseudo: pd.DataFrame, validation: pd.DataFrame
) -> tuple[pd.DataFrame, pd.DataFrame]:
    pdetail, vdetail, _ = joblib.load(
        ROOT / "reports/cache/collaborative_shock_frames.joblib"
    )
    columns = collaborative_columns(pdetail)
    pseudo = pseudo.merge(
        pdetail[[*KEY, "calibration_mask", *columns]],
        on=[*KEY, "calibration_mask"],
        validate="one_to_one",
    )
    validation = validation.merge(
        vdetail[[*KEY, *columns]], on=KEY, validate="one_to_one"
    )
    return pseudo, validation


def augment_final(final: pd.DataFrame) -> pd.DataFrame:
    _, _, detail = joblib.load(
        ROOT / "reports/cache/collaborative_shock_frames.joblib"
    )
    columns = collaborative_columns(detail)
    return final.merge(detail[[*KEY, *columns]], on=KEY, validate="one_to_one")


experiment.PHYSICAL_TARGET_MIN = -np.inf
experiment.PHYSICAL_TARGET_MAX = np.inf
experiment.TRAIN_FRAME_AUGMENTER = augment_train
experiment.FINAL_FRAME_AUGMENTER = augment_final
experiment.EXPERIMENT_LABEL = "formula_plus_collaborative_panel"
experiment.MODEL_PATH = ROOT / "models/formula_collaborative_meta.joblib"
experiment.REPORT_PATH = ROOT / "reports/formula_collaborative_meta_metrics.json"
experiment.OOF_PATH = ROOT / "reports/formula_collaborative_meta_oof.csv"
experiment.OUTPUT_PATH = ROOT / "submission_ensemble_v21_formula_collaborative_aggressive.csv"


if __name__ == "__main__":
    experiment.main()
