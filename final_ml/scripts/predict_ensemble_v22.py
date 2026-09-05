"""V22: robust ensemble of asymmetric-ID and leaf-2 panel meta models.

The new correction is disabled for 20--40 day spans, the only pre-defined gap
regime where it did not transfer to target-polygon pseudo gaps.  Those rows
fall back to the leaderboard-confirmed V20.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import joblib
import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
KEY = ["anon_polygon_id", "date"]
OUTPUT_COL = "primary_ndvi_true"
V20_PATH = ROOT / "submission_ensemble_v20.csv"
ASYMMETRIC_PATH = ROOT / "submission_ensemble_v21.csv"
LEAF2_PATH = ROOT / "submission_ensemble_v21_formula_collaborative_leaf2_aggressive.csv"
OUTPUT_PATH = ROOT / "submission_ensemble_v22.csv"
REPORT_PATH = ROOT / "reports/ensemble_v22.json"


def load(path: Path, name: str) -> pd.DataFrame:
    frame = pd.read_csv(path, parse_dates=["date"])
    if frame.columns.tolist() != [*KEY, OUTPUT_COL]:
        raise ValueError(f"{path.name}: unexpected columns")
    if frame.duplicated(KEY).any() or frame[OUTPUT_COL].isna().any():
        raise ValueError(f"{path.name}: duplicates or missing predictions")
    return frame.rename(columns={OUTPUT_COL: name})


def rmse(y, prediction) -> float:
    return float(np.sqrt(np.mean((np.asarray(y) - np.asarray(prediction)) ** 2)))


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    context = joblib.load(ROOT / "reports/cache/final_actual_gap_context.joblib")
    merged = (
        load(V20_PATH, "v20")
        .merge(load(ASYMMETRIC_PATH, "asymmetric"), on=KEY, validate="one_to_one")
        .merge(load(LEAF2_PATH, "leaf2"), on=KEY, validate="one_to_one")
        .merge(context[KEY + ["target_span_days"]], on=KEY, validate="one_to_one")
    )
    new_model = 0.50 * merged["asymmetric"] + 0.50 * merged["leaf2"]
    use_v20 = merged["target_span_days"].gt(20.0) & merged[
        "target_span_days"
    ].le(40.0)
    prediction = np.where(use_v20, merged["v20"], new_model)
    prediction = np.clip(prediction, -1.0, 1.0)

    submission = merged[KEY].copy()
    submission[OUTPUT_COL] = prediction
    submission["date"] = submission["date"].dt.strftime("%Y-%m-%d")
    expected = pd.read_csv(
        ROOT / "data/final_test_features.csv",
        parse_dates=["date"],
        usecols=[*KEY, "is_synthetic_gap"],
    )
    expected = expected[expected["is_synthetic_gap"].fillna(False)][KEY].copy()
    expected["date"] = expected["date"].dt.strftime("%Y-%m-%d")
    if len(submission) != len(expected):
        raise AssertionError("Wrong V22 row count")
    if set(map(tuple, submission[KEY].to_numpy())) != set(
        map(tuple, expected[KEY].to_numpy())
    ):
        raise AssertionError("V22 keys differ from final gaps")
    if submission.duplicated(KEY).any() or not np.isfinite(prediction).all():
        raise AssertionError("Invalid V22 predictions")
    submission.to_csv(OUTPUT_PATH, index=False)

    pseudo, validation = joblib.load(
        ROOT / "reports/cache/multidomain_meta_frames.joblib"
    )
    asym_oof = pd.read_csv(ROOT / "reports/asymmetric_id_meta_oof.csv", parse_dates=["date"])
    leaf_oof = pd.read_csv(
        ROOT / "reports/formula_collaborative_leaf2_oof.csv", parse_dates=["date"]
    ).rename(columns={"prediction": "leaf2_prediction"})
    plain_oof = pd.read_csv(
        ROOT / "reports/multidomain_meta_oof.csv", parse_dates=["date"]
    ).rename(columns={"prediction": "plain_prediction"})
    oof = (
        pd.concat([pseudo, validation], ignore_index=True)
        .merge(
            asym_oof[KEY + ["domain", "prediction"]],
            on=[*KEY, "domain"],
            validate="one_to_one",
        )
        .merge(
            leaf_oof[KEY + ["domain", "leaf2_prediction"]],
            on=[*KEY, "domain"],
            validate="one_to_one",
        )
        .merge(
            plain_oof[KEY + ["domain", "plain_prediction"]],
            on=[*KEY, "domain"],
            validate="one_to_one",
        )
    )
    oof["v20"] = np.clip(
        oof["base_prediction"]
        + 1.10 * (oof["plain_prediction"] - oof["base_prediction"]),
        -1.0,
        1.0,
    )
    oof_new = 0.50 * oof["prediction"] + 0.50 * oof["leaf2_prediction"]
    oof_use_v20 = oof["target_span_days"].gt(20.0) & oof[
        "target_span_days"
    ].le(40.0)
    oof["v22"] = np.where(oof_use_v20, oof["v20"], oof_new)
    domains = []
    for domain, part in oof.groupby("domain", sort=False):
        domains.append(
            {
                "domain": domain,
                "rows": len(part),
                "v18_rmse": rmse(part["target_true"], part["base_prediction"]),
                "v20_rmse": rmse(part["target_true"], part["v20"]),
                "v22_rmse": rmse(part["target_true"], part["v22"]),
                "improvement_vs_v20": rmse(part["target_true"], part["v20"])
                - rmse(part["target_true"], part["v22"]),
            }
        )

    report = {
        "formula": "mean(asymmetric-ID, leaf2-panel), fallback V20 for target span (20, 40] days",
        "domains": domains,
        "fallback_regime": "20 < target_span_days <= 40",
        "fallback_rows_final": int(use_v20.sum()),
        "new_model_rows_final": int((~use_v20).sum()),
        "submission_rows": len(submission),
        "prediction_min": float(np.min(prediction)),
        "prediction_max": float(np.max(prediction)),
        "prediction_mean": float(np.mean(prediction)),
        "mean_abs_v22_minus_v20": float(np.mean(np.abs(prediction - merged["v20"]))),
        "max_abs_v22_minus_v20": float(np.max(np.abs(prediction - merged["v20"]))),
        "sha256": sha256(OUTPUT_PATH),
    }
    REPORT_PATH.write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    print(f"submission: {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
