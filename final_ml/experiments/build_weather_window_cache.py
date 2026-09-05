"""Build weather-window features for pseudo, validation and final gaps."""
from __future__ import annotations

import sys
from pathlib import Path

import joblib
import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from weather_window_features import build_weather_window_features  # noqa: E402


KEY = ["anon_polygon_id", "date"]
CACHE = ROOT / "reports/cache/weather_window_frames.joblib"


def main() -> None:
    pseudo, validation = joblib.load(
        ROOT / "reports/cache/multidomain_meta_frames.joblib"
    )
    final_data = pd.read_csv(ROOT / "data/final_test_features.csv", parse_dates=["date"])
    pseudo_parts = []
    for fold, query in pseudo.groupby("calibration_mask", sort=True):
        print(f"Weather windows pseudo fold={fold}", flush=True)
        masked = final_data.copy()
        hidden = pd.MultiIndex.from_frame(masked[KEY]).isin(
            pd.MultiIndex.from_frame(query[KEY])
        )
        masked.loc[hidden, ["era5_temp_c", "era5_precip_mm"]] = np.nan
        detail = build_weather_window_features(masked, query[KEY])
        detail["calibration_mask"] = fold
        pseudo_parts.append(detail)
    pseudo_detail = pd.concat(pseudo_parts, ignore_index=True)

    print("Weather windows released validation", flush=True)
    validation_data = pd.read_csv(
        ROOT / "data/validation_features.csv", parse_dates=["date"]
    )
    validation_detail = build_weather_window_features(validation_data, validation[KEY])

    print("Weather windows final", flush=True)
    final_context = joblib.load(ROOT / "reports/cache/final_actual_gap_context.joblib")
    final_detail = build_weather_window_features(final_data, final_context[KEY])
    CACHE.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump((pseudo_detail, validation_detail, final_detail), CACHE, compress=3)
    print(f"cache: {CACHE}")


if __name__ == "__main__":
    main()
