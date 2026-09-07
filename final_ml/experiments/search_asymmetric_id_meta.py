"""Test a target-polygon-aware pseudo expert and an ID-agnostic real-gap expert."""
from __future__ import annotations

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
from search_multidomain_meta import shared_numeric  # noqa: E402


ID = "anon_polygon_id"
KEY = [ID, "date"]
REPORT = ROOT / "reports/asymmetric_id_meta_search.json"
CACHE = ROOT / "reports/cache/asymmetric_id_meta_oof.joblib"


def rmse(y, prediction) -> float:
    return float(np.sqrt(np.mean((np.asarray(y) - np.asarray(prediction)) ** 2)))


def load_frames() -> tuple[pd.DataFrame, pd.DataFrame, list[str]]:
    pseudo, validation = joblib.load(
        ROOT / "reports/cache/multidomain_meta_frames.joblib"
    )
    pseudo = add_formula_features(pseudo, FEATURE_GROUPS)
    validation = add_formula_features(validation, FEATURE_GROUPS)
    pdeta, vdeta, _ = joblib.load(
        ROOT / "reports/cache/collaborative_shock_frames.joblib"
    )
    columns = [column for column in pdeta if column.startswith("collaborative_")]
    pseudo = pseudo.merge(
        pdeta[[*KEY, "calibration_mask", *columns]],
        on=[*KEY, "calibration_mask"],
        validate="one_to_one",
    )
    validation = validation.merge(
        vdeta[[*KEY, *columns]], on=KEY, validate="one_to_one"
    )
    return pseudo, validation, shared_numeric(pseudo, validation)


def model(numeric: list[str], seed: int, *, include_id: bool) -> Pipeline:
    categorical = ["crop_type", ID] if include_id else ["crop_type"]
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
                    n_estimators=360,
                    min_samples_leaf=3,
                    max_features=0.70,
                    n_jobs=-1,
                    random_state=seed,
                ),
            ),
        ]
    )


def residual(frame: pd.DataFrame) -> np.ndarray:
    return (frame["target_true"] - frame["base_prediction"]).to_numpy(float)


def main() -> None:
    pseudo, validation, numeric = load_frames()
    pself = np.full(len(pseudo), np.nan)
    for fold in sorted(pseudo["calibration_mask"].unique()):
        selected = pseudo["calibration_mask"].eq(fold).to_numpy()
        fitted = model(numeric, 61000 + int(fold), include_id=True)
        fitted.fit(pseudo.loc[~selected], residual(pseudo.loc[~selected]))
        pself[selected] = fitted.predict(pseudo.loc[selected])

    vself = np.full(len(validation), np.nan)
    vfold = np.full(len(validation), -1, dtype=int)
    for fold, (train_idx, valid_idx) in enumerate(
        GroupKFold(5).split(validation, groups=validation[ID])
    ):
        vfold[valid_idx] = fold
        fitted = model(numeric, 62000 + fold, include_id=False)
        fitted.fit(validation.iloc[train_idx], residual(validation.iloc[train_idx]))
        vself[valid_idx] = fitted.predict(validation.iloc[valid_idx])

    pmodel = model(numeric, 63001, include_id=True)
    pmodel.fit(pseudo, residual(pseudo))
    pother = pmodel.predict(validation)
    vmodel = model(numeric, 63002, include_id=False)
    vmodel.fit(validation, residual(validation))
    vother = vmodel.predict(pseudo)
    joblib.dump(
        (pself, vself, pother, vother, vfold), CACHE, compress=3
    )

    candidates = []
    # ``pseudo_weight`` has one consistent meaning in both domains and final:
    # how much to trust the model trained on the target polygons.
    for pseudo_weight in np.linspace(0.0, 1.0, 21):
        for blend in np.linspace(0.0, 1.50, 31):
            pcorr = pseudo_weight * pself + (1.0 - pseudo_weight) * vother
            vcorr = pseudo_weight * pother + (1.0 - pseudo_weight) * vself
            ppred = np.clip(pseudo["base_prediction"] + blend * pcorr, -1.0, 1.0)
            vpred = np.clip(
                validation["base_prediction"] + blend * vcorr, -1.0, 1.0
            )
            candidates.append(
                {
                    "pseudo_model_weight": float(pseudo_weight),
                    "blend": float(blend),
                    "pseudo_rmse": rmse(pseudo["target_true"], ppred),
                    "validation_rmse": rmse(validation["target_true"], vpred),
                    "mean_rmse": (
                        rmse(pseudo["target_true"], ppred)
                        + rmse(validation["target_true"], vpred)
                    )
                    / 2.0,
                    "pseudo_prediction": np.asarray(ppred),
                    "validation_prediction": np.asarray(vpred),
                }
            )
    best = min(candidates, key=lambda row: row["mean_rmse"])

    def improvements(frame, prediction, folds):
        result = []
        for fold in sorted(np.unique(folds)):
            selected = folds == fold
            result.append(
                rmse(
                    frame.loc[selected, "target_true"],
                    frame.loc[selected, "base_prediction"],
                )
                - rmse(frame.loc[selected, "target_true"], prediction[selected])
            )
        return result

    p_imp = improvements(
        pseudo,
        best["pseudo_prediction"],
        pseudo["calibration_mask"].to_numpy(dtype=int),
    )
    v_imp = improvements(validation, best["validation_prediction"], vfold)
    report = {
        "model": "target-ID pseudo expert + ID-agnostic validation expert",
        "features": len(numeric),
        "trees": 360,
        "leaf": 3,
        "best": {
            key: value
            for key, value in best.items()
            if key not in {"pseudo_prediction", "validation_prediction"}
        },
        "pseudo_fold_improvements": p_imp,
        "validation_fold_improvements": v_imp,
        "improved_pseudo_folds": sum(value > 0 for value in p_imp),
        "improved_validation_folds": sum(value > 0 for value in v_imp),
    }
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
