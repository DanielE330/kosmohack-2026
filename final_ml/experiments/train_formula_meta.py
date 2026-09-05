"""Train the formula-augmented, target-noise-filtered multidomain meta model."""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import ExtraTreesRegressor
from sklearn.impute import SimpleImputer
from sklearn.model_selection import GroupKFold
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder


ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "src"), str(ROOT / "experiments")]

from formula_features import FEATURE_GROUPS, add_formula_features  # noqa: E402
from search_multidomain_meta import load_frames, shared_numeric  # noqa: E402
from train_multidomain_meta import build_final_frame  # noqa: E402


KEY = ["anon_polygon_id", "date"]
OUTPUT_COL = "primary_ndvi_true"
MODEL_PATH = ROOT / "models/formula_multidomain_meta.joblib"
REPORT_PATH = ROOT / "reports/formula_multidomain_meta_metrics.json"
OOF_PATH = ROOT / "reports/formula_multidomain_meta_oof.csv"
OUTPUT_PATH = ROOT / "submission_ensemble_v21_formula_aggressive.csv"
PHYSICAL_TARGET_MIN = -0.15
PHYSICAL_TARGET_MAX = 0.98
TRAIN_FRAME_AUGMENTER = None
FINAL_FRAME_AUGMENTER = None
EXPERIMENT_LABEL = "formula_only"


def rmse(y, prediction) -> float:
    return float(np.sqrt(np.mean((np.asarray(y) - np.asarray(prediction)) ** 2)))


def make_model(numeric: list[str], seed: int) -> Pipeline:
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
                    n_estimators=520,
                    min_samples_leaf=5,
                    max_features=0.70,
                    n_jobs=-1,
                    random_state=seed,
                ),
            ),
        ]
    )


def residual(frame: pd.DataFrame) -> np.ndarray:
    return (
        frame["target_true"].to_numpy(dtype=float)
        - frame["base_prediction"].to_numpy(dtype=float)
    )


def pseudo_oof(frame: pd.DataFrame, numeric: list[str]) -> np.ndarray:
    result = np.full(len(frame), np.nan)
    for fold in sorted(frame["calibration_mask"].unique()):
        valid = frame["calibration_mask"].eq(fold).to_numpy()
        model = make_model(numeric, 31000 + int(fold))
        model.fit(frame.loc[~valid], residual(frame.loc[~valid]))
        result[valid] = model.predict(frame.loc[valid])
    return result


def validation_oof(
    frame: pd.DataFrame, numeric: list[str]
) -> tuple[np.ndarray, np.ndarray]:
    result = np.full(len(frame), np.nan)
    fold_ids = np.full(len(frame), -1, dtype=int)
    splitter = GroupKFold(n_splits=5)
    for fold, (train_idx, valid_idx) in enumerate(
        splitter.split(frame, groups=frame["anon_polygon_id"])
    ):
        fold_ids[valid_idx] = fold
        model = make_model(numeric, 32000 + fold)
        model.fit(frame.iloc[train_idx], residual(frame.iloc[train_idx]))
        result[valid_idx] = model.predict(frame.iloc[valid_idx])
    return result, fold_ids


def fold_improvements(
    frame: pd.DataFrame,
    prediction: np.ndarray,
    fold_ids: np.ndarray,
) -> list[dict]:
    rows = []
    for fold in sorted(np.unique(fold_ids)):
        selected = fold_ids == fold
        before = rmse(
            frame.loc[selected, "target_true"],
            frame.loc[selected, "base_prediction"],
        )
        after = rmse(frame.loc[selected, "target_true"], prediction[selected])
        rows.append(
            {
                "fold": int(fold),
                "rows": int(selected.sum()),
                "base_rmse": before,
                "candidate_rmse": after,
                "improvement": before - after,
            }
        )
    return rows


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    pseudo_raw, validation_raw = load_frames()
    valid_target = pseudo_raw["target_true"].between(
        PHYSICAL_TARGET_MIN, PHYSICAL_TARGET_MAX
    )
    pseudo = add_formula_features(
        pseudo_raw.loc[valid_target].reset_index(drop=True), FEATURE_GROUPS
    )
    validation = add_formula_features(validation_raw.reset_index(drop=True), FEATURE_GROUPS)
    if TRAIN_FRAME_AUGMENTER is not None:
        pseudo, validation = TRAIN_FRAME_AUGMENTER(pseudo, validation)
    numeric = shared_numeric(pseudo, validation)
    print(
        f"Frames: pseudo={len(pseudo)} (removed={int((~valid_target).sum())}), "
        f"validation={len(validation)}, features={len(numeric)}",
        flush=True,
    )

    print("Formula pseudo OOF", flush=True)
    pseudo_self = pseudo_oof(pseudo, numeric)
    print("Formula validation OOF", flush=True)
    validation_self, validation_folds = validation_oof(validation, numeric)

    print("Fit full formula domain experts", flush=True)
    pseudo_model = make_model(numeric, 33001)
    pseudo_model.fit(pseudo, residual(pseudo))
    validation_model = make_model(numeric, 33002)
    validation_model.fit(validation, residual(validation))
    pseudo_other = validation_model.predict(pseudo)
    validation_other = pseudo_model.predict(validation)

    candidates = []
    for mix in np.linspace(0.0, 0.85, 18):
        for blend in np.linspace(0.0, 1.50, 31):
            pcorr = (1.0 - mix) * pseudo_self + mix * pseudo_other
            vcorr = (1.0 - mix) * validation_self + mix * validation_other
            ppred = np.clip(
                pseudo["base_prediction"].to_numpy(dtype=float) + blend * pcorr,
                -1.0,
                1.0,
            )
            vpred = np.clip(
                validation["base_prediction"].to_numpy(dtype=float) + blend * vcorr,
                -1.0,
                1.0,
            )
            candidates.append(
                {
                    "mix_cross_domain": float(mix),
                    "blend": float(blend),
                    "pseudo_rmse": rmse(pseudo["target_true"], ppred),
                    "validation_rmse": rmse(validation["target_true"], vpred),
                    "mean_rmse": (
                        rmse(pseudo["target_true"], ppred)
                        + rmse(validation["target_true"], vpred)
                    )
                    / 2.0,
                    "pseudo_prediction": ppred,
                    "validation_prediction": vpred,
                }
            )
    best = min(candidates, key=lambda row: row["mean_rmse"])
    pseudo_folds = pseudo["calibration_mask"].to_numpy(dtype=int)
    pseudo_fold_rows = fold_improvements(
        pseudo, best["pseudo_prediction"], pseudo_folds
    )
    validation_fold_rows = fold_improvements(
        validation, best["validation_prediction"], validation_folds
    )

    base_numeric = shared_numeric(pseudo_raw, validation_raw)
    final = add_formula_features(build_final_frame(base_numeric), FEATURE_GROUPS)
    if FINAL_FRAME_AUGMENTER is not None:
        final = FINAL_FRAME_AUGMENTER(final)
    for column in numeric:
        if column not in final:
            final[column] = np.nan
    correction = (
        (1.0 - best["mix_cross_domain"]) * pseudo_model.predict(final)
        + best["mix_cross_domain"] * validation_model.predict(final)
    )
    prediction = np.clip(
        final["base_prediction"].to_numpy(dtype=float) + best["blend"] * correction,
        -1.0,
        1.0,
    )
    submission = final[KEY].copy()
    submission[OUTPUT_COL] = prediction
    submission["date"] = submission["date"].dt.strftime("%Y-%m-%d")
    if len(submission) != 2323 or submission.duplicated(KEY).any():
        raise AssertionError("Invalid formula submission keys")
    if not np.isfinite(prediction).all():
        raise AssertionError("Formula predictions are not finite")
    submission.to_csv(OUTPUT_PATH, index=False)

    joblib.dump(
        {
            "pseudo_model": pseudo_model,
            "validation_model": validation_model,
            "numeric_features": numeric,
            "formula_groups": FEATURE_GROUPS,
            "mix_cross_domain": best["mix_cross_domain"],
            "blend": best["blend"],
            "physical_target_range": [PHYSICAL_TARGET_MIN, PHYSICAL_TARGET_MAX],
        },
        MODEL_PATH,
        compress=3,
    )
    oof = pd.concat(
        [
            pseudo[KEY + ["domain", "target_true", "base_prediction"]].assign(
                prediction=best["pseudo_prediction"]
            ),
            validation[KEY + ["domain", "target_true", "base_prediction"]].assign(
                prediction=best["validation_prediction"]
            ),
        ],
        ignore_index=True,
    )
    oof.to_csv(OOF_PATH, index=False)

    serializable_best = {
        key: value
        for key, value in best.items()
        if key not in {"pseudo_prediction", "validation_prediction"}
    }
    report = {
        "model": "formula-augmented two-domain ExtraTrees residual experts",
        "experiment_label": EXPERIMENT_LABEL,
        "trees_per_expert": 520,
        "formula_groups": list(FEATURE_GROUPS),
        "numeric_features": len(numeric),
        "formula_features": sum(c.startswith("formula_") for c in numeric),
        "pseudo_rows_before_filter": len(pseudo_raw),
        "pseudo_rows_after_filter": len(pseudo),
        "removed_physical_target_outliers": int((~valid_target).sum()),
        "pseudo_base_rmse_clean": rmse(
            pseudo["target_true"], pseudo["base_prediction"]
        ),
        "validation_base_rmse": rmse(
            validation["target_true"], validation["base_prediction"]
        ),
        "best": serializable_best,
        "pseudo_folds": pseudo_fold_rows,
        "validation_folds": validation_fold_rows,
        "improved_pseudo_folds": sum(row["improvement"] > 0 for row in pseudo_fold_rows),
        "improved_validation_folds": sum(
            row["improvement"] > 0 for row in validation_fold_rows
        ),
        "submission_rows": len(submission),
        "mean_abs_formula_minus_v18": float(
            np.mean(np.abs(prediction - final["base_prediction"]))
        ),
        "max_abs_formula_minus_v18": float(
            np.max(np.abs(prediction - final["base_prediction"]))
        ),
        "sha256": sha256(OUTPUT_PATH),
    }
    REPORT_PATH.write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    print(f"submission: {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
