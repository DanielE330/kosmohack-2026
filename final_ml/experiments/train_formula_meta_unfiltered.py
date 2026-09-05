"""Train the same formula meta model while retaining all finite target labels.

This is an intentional A/B against ``train_formula_meta.py``.  The four
physical outliers are kept so that we can distinguish robust transfer from an
artificially easier, cleaned pseudo score.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "experiments"))

import train_formula_meta as experiment  # noqa: E402


experiment.PHYSICAL_TARGET_MIN = -np.inf
experiment.PHYSICAL_TARGET_MAX = np.inf
experiment.MODEL_PATH = ROOT / "models/formula_multidomain_meta_unfiltered.joblib"
experiment.REPORT_PATH = ROOT / "reports/formula_multidomain_meta_unfiltered_metrics.json"
experiment.OOF_PATH = ROOT / "reports/formula_multidomain_meta_unfiltered_oof.csv"
experiment.OUTPUT_PATH = ROOT / "submission_ensemble_v21_formula_unfiltered.csv"


if __name__ == "__main__":
    experiment.main()
