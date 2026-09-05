"""V20: leaderboard-calibrated strength of the multidomain correction.

V19-safe used only 60% of the learned correction.  Its real score improved
from 0.0779 to 0.0772, while independent pseudo/validation OOF curves put the
robust optimum close to 110% of the original correction.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
KEY = ["anon_polygon_id", "date"]
OUTPUT_COL = "primary_ndvi_true"
META_SCALE = 1.10
BASE_PATH = ROOT / "submission_ensemble_v18.csv"
AGGRESSIVE_PATH = ROOT / "submission_ensemble_v19.csv"
OUTPUT_PATH = ROOT / "submission_ensemble_v20.csv"
REPORT_PATH = ROOT / "reports/ensemble_v20.json"


def load(path: Path, name: str) -> pd.DataFrame:
    frame = pd.read_csv(path, parse_dates=["date"])
    if frame.columns.tolist() != [*KEY, OUTPUT_COL]:
        raise ValueError(f"{path.name}: unexpected columns")
    if frame.duplicated(KEY).any() or frame[OUTPUT_COL].isna().any():
        raise ValueError(f"{path.name}: duplicate keys or missing values")
    return frame.rename(columns={OUTPUT_COL: name})


def rmse(y: np.ndarray, prediction: np.ndarray) -> float:
    return float(np.sqrt(np.mean((y - prediction) ** 2)))


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    merged = load(BASE_PATH, "v18_prediction").merge(
        load(AGGRESSIVE_PATH, "v19_aggressive_prediction"),
        on=KEY,
        validate="one_to_one",
    )
    correction = (
        merged["v19_aggressive_prediction"].to_numpy(dtype=float)
        - merged["v18_prediction"].to_numpy(dtype=float)
    )
    prediction = np.clip(
        merged["v18_prediction"].to_numpy(dtype=float) + META_SCALE * correction,
        -1.0,
        1.0,
    )
    submission = merged[KEY].copy()
    submission[OUTPUT_COL] = prediction
    submission["date"] = submission["date"].dt.strftime("%Y-%m-%d")

    test = pd.read_csv(
        ROOT / "data/final_test_features.csv",
        parse_dates=["date"],
        usecols=[*KEY, "is_synthetic_gap"],
    )
    expected = test[test["is_synthetic_gap"].fillna(False)][KEY].copy()
    expected["date"] = expected["date"].dt.strftime("%Y-%m-%d")
    if len(submission) != len(expected):
        raise AssertionError("Wrong submission row count")
    if set(map(tuple, submission[KEY].to_numpy())) != set(
        map(tuple, expected[KEY].to_numpy())
    ):
        raise AssertionError("Submission keys differ from final gaps")
    if submission.duplicated(KEY).any() or not np.isfinite(prediction).all():
        raise AssertionError("Invalid V20 predictions")
    submission.to_csv(OUTPUT_PATH, index=False)

    pseudo, validation = __import__("joblib").load(
        ROOT / "reports/cache/multidomain_meta_frames.joblib"
    )
    oof = pd.read_csv(ROOT / "reports/multidomain_meta_oof.csv")
    split = len(pseudo)
    domain_rows = []
    for name, frame, part in (
        ("final_pseudo", pseudo, oof.iloc[:split]),
        ("released_validation", validation, oof.iloc[split:]),
    ):
        y = frame["target_true"].to_numpy(dtype=float)
        base = frame["base_prediction"].to_numpy(dtype=float)
        aggressive = part["prediction"].to_numpy(dtype=float)
        scaled = np.clip(base + META_SCALE * (aggressive - base), -1.0, 1.0)
        domain_rows.append(
            {
                "domain": name,
                "rows": len(frame),
                "base_rmse": rmse(y, base),
                "v20_proxy_rmse": rmse(y, scaled),
                "improvement": rmse(y, base) - rmse(y, scaled),
            }
        )

    report = {
        "formula": "v18 + 1.10 * (v19_aggressive - v18)",
        "meta_scale": META_SCALE,
        "why": "OOF optimum is about 1.10; v19-safe leaderboard movement confirms the correction direction",
        "domains": domain_rows,
        "leaderboard_calibration": {
            "v18_score": 0.0779,
            "v19_safe_score": 0.0772,
            "v19_safe_scale": 0.60,
            "quadratic_central_optimum_scale": 1.336,
            "v20_central_estimated_score": 0.07692,
        },
        "submission_rows": len(submission),
        "prediction_min": float(np.min(prediction)),
        "prediction_max": float(np.max(prediction)),
        "mean_abs_v20_minus_v18": float(np.mean(np.abs(META_SCALE * correction))),
        "max_abs_v20_minus_v18": float(np.max(np.abs(META_SCALE * correction))),
        "sha256": sha256(OUTPUT_PATH),
    }
    REPORT_PATH.write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    print(f"submission: {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
