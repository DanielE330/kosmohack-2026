"""Experimental v9: refined extrapolation of the v5 -> v7 direction."""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
KEY = ["anon_polygon_id", "date"]
OUTPUT_COL = "primary_ndvi_true"
NONLINEAR_SCALE = 2.35
V5_PATH = ROOT / "submission_ensemble_v5.csv"
V7_PATH = ROOT / "submission_ensemble_v7.csv"
OUTPUT_PATH = ROOT / "submission_ensemble_v9.csv"


def load_version(path: Path, prediction_column: str) -> pd.DataFrame:
    frame = pd.read_csv(path, parse_dates=["date"])
    if frame.columns.tolist() != [*KEY, OUTPUT_COL]:
        raise ValueError(f"Некорректный формат {path.name}")
    if frame.duplicated(KEY).any() or frame[OUTPUT_COL].isna().any():
        raise ValueError(f"{path.name}: найдены дубликаты или NaN")
    return frame.rename(columns={OUTPUT_COL: prediction_column})


def main() -> None:
    v5 = load_version(V5_PATH, "v5_prediction")
    v7 = load_version(V7_PATH, "v7_prediction")
    merged = v5.merge(v7, on=KEY, validate="one_to_one")
    if not (len(merged) == len(v5) == len(v7)):
        raise AssertionError("Ключи v5 и v7 не совпадают")

    direction = merged["v7_prediction"] - merged["v5_prediction"]
    prediction = np.clip(
        merged["v5_prediction"] + NONLINEAR_SCALE * direction,
        -1.0,
        1.0,
    )
    submission = merged[KEY].copy()
    submission[OUTPUT_COL] = prediction
    submission["date"] = submission["date"].dt.strftime("%Y-%m-%d")
    submission.to_csv(OUTPUT_PATH, index=False, encoding="utf-8")

    print(f"submission: {OUTPUT_PATH} ({len(submission):,} строк)")
    print(submission[OUTPUT_COL].describe().to_string())
    print(f"Nonlinear direction scale: {NONLINEAR_SCALE:.2f}")
    print(
        "Mean abs v9-v8-equivalent: "
        f"{float(np.mean(np.abs((NONLINEAR_SCALE - 1.75) * direction))):.6f}"
    )


if __name__ == "__main__":
    main()
