# Submission v7: nonlinear private adaptation

`v7` is an independent model-backed candidate. It does not use leaderboard
scores when producing predictions.

The pipeline keeps the v4 local per-polygon Ridge correction and trains two
cross-polygon residual correctors on 10,576 visible private pseudo-gaps:

- Ridge captures stable linear bias;
- ExtraTrees captures nonlinear interactions between crop, season, gap length,
  model disagreement, polygon identity, and historical context.

Both models predict residuals relative to v3. Their contributions are clipped
and conservatively blended by crop.

## Leakage-safe validation

```bash
python experiments/validate_tree_private_adaptation.py
```

Protocol:

- the evaluated synthetic-mask seed is excluded from calibration;
- the same original `row_id` is forbidden in calibration;
- Ridge/ExtraTrees blend weights for an outer fold are selected only on the
  other polygon-disjoint folds.

Results:

- v5 OOF RMSE: `0.061643`;
- nested v7 OOF RMSE: `0.061473`;
- fixed production v7 OOF RMSE: `0.061405`;
- all 5 outer folds, all 3 mask seeds, and all 4 crop groups improved.

## Build

```bash
python scripts/predict_ensemble_v7.py
```

Output: `submission_ensemble_v7.csv`.
