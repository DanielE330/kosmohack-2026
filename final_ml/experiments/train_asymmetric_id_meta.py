"""Train final asymmetric target-ID / real-gap experts and create V21."""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import joblib
import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "src"), str(ROOT / "experiments")]

from formula_features import FEATURE_GROUPS, add_formula_features  # noqa: E402
from search_asymmetric_id_meta import load_frames, model, residual, rmse  # noqa: E402
from search_multidomain_meta import shared_numeric  # noqa: E402
from train_multidomain_meta import build_final_frame  # noqa: E402


KEY = ["anon_polygon_id", "date"]
OUTPUT_COL = "primary_ndvi_true"
PSEUDO_WEIGHT = 0.80
RESIDUAL_BLEND = 1.05
MODEL_PATH = ROOT / "models/asymmetric_id_meta.joblib"
OUTPUT_PATH = ROOT / "submission_ensemble_v21.csv"
REPORT_PATH = ROOT / "reports/ensemble_v21.json"
OOF_PATH = ROOT / "reports/asymmetric_id_meta_oof.csv"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    pseudo, validation, numeric = load_frames()
    print(
        f"Train target-ID expert: rows={len(pseudo)}, features={len(numeric)}",
        flush=True,
    )
    pseudo_model = model(numeric, 71001, include_id=True)
    pseudo_model.set_params(model__n_estimators=650)
    pseudo_model.fit(pseudo, residual(pseudo))
    print(f"Train real-gap expert: rows={len(validation)}", flush=True)
    validation_model = model(numeric, 71002, include_id=False)
    validation_model.set_params(model__n_estimators=650)
    validation_model.fit(validation, residual(validation))

    pseudo_raw, validation_raw = joblib.load(
        ROOT / "reports/cache/multidomain_meta_frames.joblib"
    )
    base_numeric = shared_numeric(pseudo_raw, validation_raw)
    final = add_formula_features(build_final_frame(base_numeric), FEATURE_GROUPS)
    _, _, collaborative = joblib.load(
        ROOT / "reports/cache/collaborative_shock_frames.joblib"
    )
    collaborative_columns = [
        column for column in collaborative if column.startswith("collaborative_")
    ]
    final = final.merge(
        collaborative[[*KEY, *collaborative_columns]],
        on=KEY,
        validate="one_to_one",
    )
    for column in numeric:
        if column not in final:
            final[column] = np.nan

    pseudo_correction = pseudo_model.predict(final)
    validation_correction = validation_model.predict(final)
    correction = (
        PSEUDO_WEIGHT * pseudo_correction
        + (1.0 - PSEUDO_WEIGHT) * validation_correction
    )
    prediction = np.clip(
        final["base_prediction"].to_numpy(dtype=float)
        + RESIDUAL_BLEND * correction,
        -1.0,
        1.0,
    )
    submission = final[KEY].copy()
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
        raise AssertionError("Wrong V21 row count")
    if set(map(tuple, submission[KEY].to_numpy())) != set(
        map(tuple, expected[KEY].to_numpy())
    ):
        raise AssertionError("V21 keys differ from final gaps")
    if submission.duplicated(KEY).any() or not np.isfinite(prediction).all():
        raise AssertionError("Invalid V21 predictions")
    submission.to_csv(OUTPUT_PATH, index=False)

    pself, vself, pother, vother, validation_folds = joblib.load(
        ROOT / "reports/cache/asymmetric_id_meta_oof.joblib"
    )
    pseudo_oof = np.clip(
        pseudo["base_prediction"].to_numpy(dtype=float)
        + RESIDUAL_BLEND
        * (PSEUDO_WEIGHT * pself + (1.0 - PSEUDO_WEIGHT) * vother),
        -1.0,
        1.0,
    )
    validation_oof = np.clip(
        validation["base_prediction"].to_numpy(dtype=float)
        + RESIDUAL_BLEND
        * (PSEUDO_WEIGHT * pother + (1.0 - PSEUDO_WEIGHT) * vself),
        -1.0,
        1.0,
    )
    oof = pd.concat(
        [
            pseudo[KEY + ["domain", "target_true", "base_prediction"]].assign(
                prediction=pseudo_oof
            ),
            validation[KEY + ["domain", "target_true", "base_prediction"]].assign(
                prediction=validation_oof
            ),
        ],
        ignore_index=True,
    )
    oof.to_csv(OOF_PATH, index=False)

    joblib.dump(
        {
            "pseudo_model": pseudo_model,
            "validation_model": validation_model,
            "numeric_features": numeric,
            "formula_groups": FEATURE_GROUPS,
            "collaborative_columns": collaborative_columns,
            "pseudo_model_weight": PSEUDO_WEIGHT,
            "residual_blend": RESIDUAL_BLEND,
        },
        MODEL_PATH,
        compress=3,
    )
    v18 = final["base_prediction"].to_numpy(dtype=float)
    report = {
        "model": "asymmetric target-ID ExtraTrees + ID-agnostic real-gap ExtraTrees",
        "trees_per_expert": 650,
        "min_samples_leaf": 3,
        "max_features": 0.70,
        "pseudo_model_weight": PSEUDO_WEIGHT,
        "validation_model_weight": 1.0 - PSEUDO_WEIGHT,
        "residual_blend": RESIDUAL_BLEND,
        "numeric_features": len(numeric),
        "pseudo_oof_rmse": rmse(pseudo["target_true"], pseudo_oof),
        "validation_oof_rmse": rmse(validation["target_true"], validation_oof),
        "pseudo_v18_rmse": rmse(
            pseudo["target_true"], pseudo["base_prediction"]
        ),
        "validation_v18_rmse": rmse(
            validation["target_true"], validation["base_prediction"]
        ),
        "submission_rows": len(submission),
        "prediction_min": float(np.min(prediction)),
        "prediction_max": float(np.max(prediction)),
        "prediction_mean": float(np.mean(prediction)),
        "mean_abs_v21_minus_v18": float(np.mean(np.abs(prediction - v18))),
        "max_abs_v21_minus_v18": float(np.max(np.abs(prediction - v18))),
        "mean_abs_pseudo_correction": float(np.mean(np.abs(pseudo_correction))),
        "mean_abs_validation_correction": float(
            np.mean(np.abs(validation_correction))
        ),
        "sha256": sha256(OUTPUT_PATH),
    }
    REPORT_PATH.write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    print(f"submission: {OUTPUT_PATH}")
    print(f"model: {MODEL_PATH}")


if __name__ == "__main__":
    main()
