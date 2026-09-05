"""A/B formula feature groups under the same multidomain OOF protocol."""
from __future__ import annotations

import json
import sys
from pathlib import Path

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


REPORT = ROOT / "reports/formula_meta_search.json"


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
                    n_estimators=180,
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


def self_oof(
    pseudo: pd.DataFrame,
    validation: pd.DataFrame,
    numeric: list[str],
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    pseudo_prediction = np.full(len(pseudo), np.nan)
    for fold in sorted(pseudo["calibration_mask"].unique()):
        valid = pseudo["calibration_mask"].eq(fold).to_numpy()
        model = make_model(numeric, 21000 + int(fold))
        model.fit(pseudo.loc[~valid], residual(pseudo.loc[~valid]))
        pseudo_prediction[valid] = model.predict(pseudo.loc[valid])

    validation_prediction = np.full(len(validation), np.nan)
    validation_fold = np.full(len(validation), -1, dtype=int)
    split = GroupKFold(n_splits=5)
    for fold, (train_idx, valid_idx) in enumerate(
        split.split(validation, groups=validation["anon_polygon_id"])
    ):
        validation_fold[valid_idx] = fold
        model = make_model(numeric, 22000 + fold)
        model.fit(validation.iloc[train_idx], residual(validation.iloc[train_idx]))
        validation_prediction[valid_idx] = model.predict(validation.iloc[valid_idx])
    return pseudo_prediction, validation_prediction, validation_fold


def evaluate(groups: tuple[str, ...]) -> dict:
    pseudo_raw, validation_raw = load_frames()
    pseudo = add_formula_features(pseudo_raw, groups)
    validation = add_formula_features(validation_raw, groups)
    numeric = shared_numeric(pseudo, validation)
    pself, vself, vfold = self_oof(pseudo, validation, numeric)

    pmodel = make_model(numeric, 23001)
    pmodel.fit(pseudo, residual(pseudo))
    pother = pmodel.predict(validation)
    vmodel = make_model(numeric, 23002)
    vmodel.fit(validation, residual(validation))
    vother = vmodel.predict(pseudo)

    candidates = []
    for mix in np.linspace(0.0, 0.75, 16):
        for blend in np.linspace(0.0, 1.25, 26):
            pcorr = (1.0 - mix) * pself + mix * vother
            vcorr = (1.0 - mix) * vself + mix * pother
            ppred = np.clip(pseudo["base_prediction"] + blend * pcorr, -1.0, 1.0)
            vpred = np.clip(
                validation["base_prediction"] + blend * vcorr, -1.0, 1.0
            )
            prmse = rmse(pseudo["target_true"], ppred)
            vrmse = rmse(validation["target_true"], vpred)
            candidates.append(
                {
                    "mix": float(mix),
                    "blend": float(blend),
                    "pseudo_rmse": prmse,
                    "validation_rmse": vrmse,
                    "mean_rmse": (prmse + vrmse) / 2.0,
                    "pseudo_prediction": np.asarray(ppred),
                    "validation_prediction": np.asarray(vpred),
                }
            )
    best = min(candidates, key=lambda row: row["mean_rmse"])
    pfolds = []
    for fold in sorted(pseudo["calibration_mask"].unique()):
        selected = pseudo["calibration_mask"].eq(fold).to_numpy()
        before = rmse(
            pseudo.loc[selected, "target_true"],
            pseudo.loc[selected, "base_prediction"],
        )
        after = rmse(
            pseudo.loc[selected, "target_true"],
            best["pseudo_prediction"][selected],
        )
        pfolds.append(before - after)
    vfolds = []
    for fold in sorted(np.unique(vfold)):
        selected = vfold == fold
        before = rmse(
            validation.loc[selected, "target_true"],
            validation.loc[selected, "base_prediction"],
        )
        after = rmse(
            validation.loc[selected, "target_true"],
            best["validation_prediction"][selected],
        )
        vfolds.append(before - after)
    return {
        "groups": list(groups) if groups else ["none"],
        "features": len(numeric),
        "formula_features": sum(c.startswith("formula_") for c in numeric),
        "base_pseudo_rmse": rmse(pseudo["target_true"], pseudo["base_prediction"]),
        "base_validation_rmse": rmse(
            validation["target_true"], validation["base_prediction"]
        ),
        "best": {
            key: value
            for key, value in best.items()
            if key not in {"pseudo_prediction", "validation_prediction"}
        },
        "pseudo_fold_improvements": pfolds,
        "validation_fold_improvements": vfolds,
        "improved_pseudo_folds": sum(value > 0 for value in pfolds),
        "improved_validation_folds": sum(value > 0 for value in vfolds),
    }


def main() -> None:
    variants = [
        (),
        *(tuple([group]) for group in FEATURE_GROUPS),
        *(tuple(item for item in FEATURE_GROUPS if item != dropped) for dropped in FEATURE_GROUPS),
        FEATURE_GROUPS,
    ]
    previous: dict[tuple[str, ...], dict] = {}
    if REPORT.exists():
        loaded = json.loads(REPORT.read_text(encoding="utf-8"))
        for row in loaded.get("results", []):
            key = tuple(() if row.get("groups") == ["none"] else row.get("groups", []))
            previous[key] = row
    results = []
    for groups in variants:
        key = tuple(groups)
        if key in previous:
            print(f"Reuse formula groups: {groups or ('none',)}", flush=True)
            row = previous[key]
        else:
            print(f"Evaluate formula groups: {groups or ('none',)}", flush=True)
            row = evaluate(key)
        results.append(row)
        print(json.dumps(row, ensure_ascii=False, indent=2), flush=True)
        REPORT.write_text(
            json.dumps({"results": results}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    plain = next(row for row in results if row["groups"] == ["none"])
    all_formula = next(row for row in results if row["groups"] == list(FEATURE_GROUPS))
    report = {
        "protocol": "same ExtraTrees and folds; formula group ablation",
        "trees_per_fit": 180,
        "results": results,
        "formula_minus_plain_mean_rmse": (
            all_formula["best"]["mean_rmse"] - plain["best"]["mean_rmse"]
        ),
    }
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"report: {REPORT}")


if __name__ == "__main__":
    main()
