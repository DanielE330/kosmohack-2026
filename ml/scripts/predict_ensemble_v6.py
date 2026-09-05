"""Experimental v6 calibrated from the v3/v4/v5 leaderboard trajectory.

This script does not retrain the models.  It moves conservatively farther in
the two already validated correction directions:

    v6 = v3 + 1.30 * (v4 - v3) + 1.15 * (v5 - v4)
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
KEY = ["anon_polygon_id", "date"]
OUTPUT_COL = "primary_ndvi_true"
LOCAL_SCALE = 1.30
GLOBAL_SCALE = 1.15
V3_PATH = ROOT / "submission_ensemble_v3.csv"
V4_PATH = ROOT / "submission_ensemble_v4.csv"
V5_PATH = ROOT / "submission_ensemble_v5.csv"
OUTPUT_PATH = ROOT / "submission_ensemble_v6.csv"


def load_version(path: Path, name: str) -> pd.DataFrame:
    frame = pd.read_csv(path, parse_dates=["date"])
    expected_columns = [*KEY, OUTPUT_COL]
    if frame.columns.tolist() != expected_columns:
        raise ValueError(f"{path.name}: ожидались колонки {expected_columns}")
    if frame.duplicated(KEY).any() or frame[OUTPUT_COL].isna().any():
        raise ValueError(f"{path.name}: найдены дубликаты или NaN")
    return frame.rename(columns={OUTPUT_COL: name})


def main() -> None:
    v3 = load_version(V3_PATH, "v3_prediction")
    v4 = load_version(V4_PATH, "v4_prediction")
    v5 = load_version(V5_PATH, "v5_prediction")
    merged = v3.merge(v4, on=KEY, validate="one_to_one").merge(
        v5, on=KEY, validate="one_to_one"
    )
    if not (len(merged) == len(v3) == len(v4) == len(v5)):
        raise AssertionError("Ключи v3/v4/v5 не совпадают")

    local_delta = merged["v4_prediction"] - merged["v3_prediction"]
    global_delta = merged["v5_prediction"] - merged["v4_prediction"]
    prediction = np.clip(
        merged["v3_prediction"]
        + LOCAL_SCALE * local_delta
        + GLOBAL_SCALE * global_delta,
        -1.0,
        1.0,
    )
    submission = merged[KEY].copy()
    submission[OUTPUT_COL] = prediction
    submission["date"] = submission["date"].dt.strftime("%Y-%m-%d")
    submission.to_csv(OUTPUT_PATH, index=False, encoding="utf-8")

    print(f"submission: {OUTPUT_PATH} ({len(submission):,} строк)")
    print(submission[OUTPUT_COL].describe().to_string())
    print(f"Local correction scale:  {LOCAL_SCALE:.2f}")
    print(f"Global correction scale: {GLOBAL_SCALE:.2f}")
    print(
        "Mean abs v6-v5:       "
        f"{float(np.mean(np.abs(prediction - merged['v5_prediction']))):.6f}"
    )


if __name__ == "__main__":
    main()
