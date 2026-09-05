# Submission v5: global private calibration

`v5` keeps the leaderboard-proven `v4` prediction and adds one conservative
correction learned from visible target values in `private_features.csv`.

## Idea

1. Build the unchanged v3 ensemble prediction.
2. Hide four disjoint 15% subsets of visible private `primary_ndvi` values.
3. Predict those pseudo-gaps and use their known residuals as calibration data.
4. Keep the v4 per-polygon Ridge correction.
5. Fit a second Ridge model over all private polygons. It uses model-component
   predictions, interpolation/climatology/history features, gap geometry,
   polygon ID, and crop type.
6. Add its clipped residual correction to v4 with conservative crop weights.

The real rows marked `is_synthetic_gap=True` are never used as labels.

## Validation

Run:

```bash
python experiments/validate_private_adaptation.py
python experiments/validate_global_private_adaptation.py
```

The second script uses two safeguards:

- every evaluated synthetic-mask seed is predicted using the other seeds and
  never the same original `row_id`;
- crop blend weights are selected on four polygon-disjoint GroupKFold folds and
  scored on the fifth.

Observed nested OOF result at creation time:

- v4: `0.061877`
- v5: `0.061659`
- improvement: about `0.000218`
- all 5 outer folds and all 3 synthetic-mask seeds improved.

## Build submission

```bash
python scripts/predict_ensemble_v5.py
```

Output: `submission_ensemble_v5.csv` with columns:

```text
anon_polygon_id,date,primary_ndvi_true
```

`submission_ensemble_v4.csv` remains the safe fallback because it already
scored `0.0688` on the private leaderboard.
