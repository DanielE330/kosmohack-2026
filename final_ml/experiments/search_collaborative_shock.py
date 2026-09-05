"""Evaluate ridge collaborative residuals on both available gap domains."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import joblib
import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "src")]

from collaborative_shock import predict_collaborative_shock  # noqa: E402


KEY = ["anon_polygon_id", "date"]
SOURCES = ("landsat", "modis", "s2")
REPORT = ROOT / "reports/collaborative_shock_search.json"
CACHE = ROOT / "reports/cache/collaborative_shock_frames.joblib"


def rmse(y, prediction) -> float:
    return float(np.sqrt(np.mean((np.asarray(y) - np.asarray(prediction)) ** 2)))


def query_columns(frame: pd.DataFrame) -> list[str]:
    return [*KEY, *(f"expert_{source}_probability" for source in SOURCES)]


def build_frames() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    if CACHE.exists():
        print(f"Load cache: {CACHE}", flush=True)
        return joblib.load(CACHE)
    pseudo, validation = joblib.load(
        ROOT / "reports/cache/multidomain_meta_frames.joblib"
    )
    final_data = pd.read_csv(ROOT / "data/final_test_features.csv", parse_dates=["date"])
    pseudo_parts = []
    for fold, query in pseudo.groupby("calibration_mask", sort=True):
        print(f"Collaborative pseudo fold={fold}", flush=True)
        masked = final_data.copy()
        hidden = pd.MultiIndex.from_frame(masked[KEY]).isin(
            pd.MultiIndex.from_frame(query[KEY])
        )
        masked.loc[hidden, ["primary_ndvi", "s2_ndvi", "landsat_ndvi", "modis_ndvi"]] = np.nan
        detail = predict_collaborative_shock(masked, query[query_columns(query)])
        detail["calibration_mask"] = fold
        pseudo_parts.append(detail)
    pseudo_detail = pd.concat(pseudo_parts, ignore_index=True)

    print("Collaborative released validation", flush=True)
    validation_data = pd.read_csv(
        ROOT / "data/validation_features.csv", parse_dates=["date"]
    )
    validation_detail = predict_collaborative_shock(
        validation_data, validation[query_columns(validation)]
    )

    print("Collaborative final gaps", flush=True)
    final_context = joblib.load(ROOT / "reports/cache/final_actual_gap_context.joblib")
    final_expert = pd.read_csv(
        ROOT / "reports/sensor_experts_final.csv", parse_dates=["date"]
    )
    final_query = final_context[KEY].merge(
        final_expert[query_columns(final_expert)], on=KEY, validate="one_to_one"
    )
    final_detail = predict_collaborative_shock(final_data, final_query)
    CACHE.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump((pseudo_detail, validation_detail, final_detail), CACHE, compress=3)
    return pseudo_detail, validation_detail, final_detail


def fold_rows(frame: pd.DataFrame, prediction: np.ndarray, fold_col: str) -> list[dict]:
    rows = []
    for fold in sorted(frame[fold_col].unique()):
        selected = frame[fold_col].eq(fold).to_numpy()
        before = rmse(frame.loc[selected, "target_true"], frame.loc[selected, "v20"])
        after = rmse(frame.loc[selected, "target_true"], prediction[selected])
        rows.append(
            {
                "fold": int(fold),
                "rows": int(selected.sum()),
                "v20_rmse": before,
                "candidate_rmse": after,
                "improvement": before - after,
            }
        )
    return rows


def main() -> None:
    pseudo, validation = joblib.load(
        ROOT / "reports/cache/multidomain_meta_frames.joblib"
    )
    plain_oof = pd.read_csv(ROOT / "reports/multidomain_meta_oof.csv", parse_dates=["date"])
    pplain = plain_oof.iloc[: len(pseudo)]
    vplain = plain_oof.iloc[len(pseudo) :]
    pdetail, vdetail, final_detail = build_frames()

    p = pseudo.merge(
        pplain[KEY + ["prediction"]], on=KEY, validate="one_to_one"
    ).merge(
        pdetail[KEY + ["calibration_mask", "collaborative_shock"]],
        on=[*KEY, "calibration_mask"],
        validate="one_to_one",
    )
    v = validation.merge(
        vplain[KEY + ["prediction"]], on=KEY, validate="one_to_one"
    ).merge(
        vdetail[KEY + ["collaborative_shock"]], on=KEY, validate="one_to_one"
    )
    for frame in (p, v):
        frame["v20"] = np.clip(
            frame["base_prediction"]
            + 1.10 * (frame["prediction"] - frame["base_prediction"]),
            -1.0,
            1.0,
        )

    # Validation polygon folds are reconstructed deterministically for robustness.
    from sklearn.model_selection import GroupKFold

    validation_fold = np.full(len(v), -1, dtype=int)
    for fold, (_, valid_idx) in enumerate(
        GroupKFold(5).split(v, groups=v["anon_polygon_id"])
    ):
        validation_fold[valid_idx] = fold
    v["evaluation_fold"] = validation_fold

    candidates = []
    for weight in np.linspace(-0.10, 0.35, 91):
        ppred = np.clip(p["v20"] + weight * p["collaborative_shock"], -1.0, 1.0)
        vpred = np.clip(v["v20"] + weight * v["collaborative_shock"], -1.0, 1.0)
        candidates.append(
            {
                "weight": float(weight),
                "pseudo_rmse": rmse(p["target_true"], ppred),
                "validation_rmse": rmse(v["target_true"], vpred),
                "mean_rmse": (
                    rmse(p["target_true"], ppred)
                    + rmse(v["target_true"], vpred)
                )
                / 2.0,
                "pseudo_prediction": np.asarray(ppred),
                "validation_prediction": np.asarray(vpred),
            }
        )
    best = min(candidates, key=lambda row: row["mean_rmse"])
    p_folds = fold_rows(p, best["pseudo_prediction"], "calibration_mask")
    v_folds = fold_rows(v, best["validation_prediction"], "evaluation_fold")
    report = {
        "method": "per-polygon/per-source Ridge on date-by-polygon residual panel",
        "alpha": 0.30,
        "best": {
            key: value
            for key, value in best.items()
            if key not in {"pseudo_prediction", "validation_prediction"}
        },
        "pseudo_v20_rmse": rmse(p["target_true"], p["v20"]),
        "validation_v20_rmse": rmse(v["target_true"], v["v20"]),
        "pseudo_folds": p_folds,
        "validation_folds": v_folds,
        "improved_pseudo_folds": sum(row["improvement"] > 0 for row in p_folds),
        "improved_validation_folds": sum(row["improvement"] > 0 for row in v_folds),
        "final_rows_with_signal": int(final_detail["collaborative_source_probability"].gt(0).sum()),
        "final_signal_std": float(final_detail["collaborative_shock"].std()),
    }
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
