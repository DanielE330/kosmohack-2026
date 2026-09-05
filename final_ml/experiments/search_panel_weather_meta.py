"""Ablate collaborative-panel and true weather-window meta features."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import joblib
import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "src"), str(ROOT / "experiments")]

from formula_features import FEATURE_GROUPS, add_formula_features  # noqa: E402
from search_formula_meta import make_model, residual, rmse, self_oof  # noqa: E402
from search_multidomain_meta import shared_numeric  # noqa: E402


KEY = ["anon_polygon_id", "date"]
REPORT = ROOT / "reports/panel_weather_meta_search.json"


def attach_extra(
    pseudo: pd.DataFrame,
    validation: pd.DataFrame,
    *,
    collaborative: bool,
    weather: bool,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    p = add_formula_features(pseudo, FEATURE_GROUPS)
    v = add_formula_features(validation, FEATURE_GROUPS)
    if collaborative:
        pdeta, vdeta, _ = joblib.load(
            ROOT / "reports/cache/collaborative_shock_frames.joblib"
        )
        columns = [
            column
            for column in pdeta
            if column.startswith("collaborative_")
        ]
        p = p.merge(
            pdeta[[*KEY, "calibration_mask", *columns]],
            on=[*KEY, "calibration_mask"],
            validate="one_to_one",
        )
        v = v.merge(
            vdeta[[*KEY, *columns]], on=KEY, validate="one_to_one"
        )
    if weather:
        pweather, vweather, _ = joblib.load(
            ROOT / "reports/cache/weather_window_frames.joblib"
        )
        columns = [column for column in pweather if column.startswith("weather_")]
        p = p.merge(
            pweather[[*KEY, "calibration_mask", *columns]],
            on=[*KEY, "calibration_mask"],
            validate="one_to_one",
        )
        v = v.merge(
            vweather[[*KEY, *columns]], on=KEY, validate="one_to_one"
        )
    return p, v


def evaluate(
    pseudo_raw: pd.DataFrame,
    validation_raw: pd.DataFrame,
    *,
    collaborative: bool,
    weather: bool,
) -> dict:
    pseudo, validation = attach_extra(
        pseudo_raw,
        validation_raw,
        collaborative=collaborative,
        weather=weather,
    )
    numeric = shared_numeric(pseudo, validation)
    pself, vself, vfold = self_oof(pseudo, validation, numeric)
    pmodel = make_model(numeric, 41001)
    pmodel.fit(pseudo, residual(pseudo))
    pother = pmodel.predict(validation)
    vmodel = make_model(numeric, 41002)
    vmodel.fit(validation, residual(validation))
    vother = vmodel.predict(pseudo)

    candidates = []
    for mix in np.linspace(0.0, 0.80, 17):
        for blend in np.linspace(0.0, 1.40, 29):
            pcorr = (1.0 - mix) * pself + mix * vother
            vcorr = (1.0 - mix) * vself + mix * pother
            ppred = np.clip(pseudo["base_prediction"] + blend * pcorr, -1.0, 1.0)
            vpred = np.clip(
                validation["base_prediction"] + blend * vcorr, -1.0, 1.0
            )
            candidates.append(
                {
                    "mix": float(mix),
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
    p_improvements = []
    for fold in sorted(pseudo["calibration_mask"].unique()):
        selected = pseudo["calibration_mask"].eq(fold).to_numpy()
        p_improvements.append(
            rmse(
                pseudo.loc[selected, "target_true"],
                pseudo.loc[selected, "base_prediction"],
            )
            - rmse(
                pseudo.loc[selected, "target_true"],
                best["pseudo_prediction"][selected],
            )
        )
    v_improvements = []
    for fold in sorted(np.unique(vfold)):
        selected = vfold == fold
        v_improvements.append(
            rmse(
                validation.loc[selected, "target_true"],
                validation.loc[selected, "base_prediction"],
            )
            - rmse(
                validation.loc[selected, "target_true"],
                best["validation_prediction"][selected],
            )
        )
    return {
        "collaborative": collaborative,
        "weather_windows": weather,
        "numeric_features": len(numeric),
        "best": {
            key: value
            for key, value in best.items()
            if key not in {"pseudo_prediction", "validation_prediction"}
        },
        "pseudo_fold_improvements": p_improvements,
        "validation_fold_improvements": v_improvements,
        "improved_pseudo_folds": sum(value > 0 for value in p_improvements),
        "improved_validation_folds": sum(value > 0 for value in v_improvements),
    }


def main() -> None:
    pseudo, validation = joblib.load(
        ROOT / "reports/cache/multidomain_meta_frames.joblib"
    )
    results = []
    for collaborative, weather in ((True, False), (False, True), (True, True)):
        print(
            f"Evaluate collaborative={collaborative}, weather={weather}", flush=True
        )
        row = evaluate(
            pseudo,
            validation,
            collaborative=collaborative,
            weather=weather,
        )
        results.append(row)
        REPORT.write_text(
            json.dumps({"results": results}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        print(json.dumps(row, ensure_ascii=False, indent=2), flush=True)
    report = {
        "protocol": "formula meta plus panel/weather ablation, 180 ExtraTrees",
        "formula_only_reference_mean_rmse": 0.06614416267405945,
        "results": results,
    }
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"report: {REPORT}")


if __name__ == "__main__":
    main()
