# Fine-Tuning Quick Reference

## Three-Tier Healing Strategy

```
Drift Detected?
    │
    ├─ NO (KS < 0.05)
    │   └─ TIER 1: MONITOR
    │       └─ Action: Continue monitoring, no model update
    │       └─ Improvement: 0%
    │
    ├─ MILD (KS 0.05-0.15)
    │   └─ TIER 2: FINE-TUNE
    │       ├─ Add 10-50 trees (proportional to drift)
    │       ├─ Fit on current + validation data
    │       ├─ Validate on holdout
    │       └─ Deploy if improvement ≥ 5%
    │
    └─ SEVERE (KS > 0.2)
        └─ TIER 3: RETRAIN
            ├─ Full retrain with optimized hyperparameters
            ├─ Fit on training + validation data
            ├─ Validate on holdout
            └─ Deploy if improvement ≥ 5%
```

## Decision Matrix

| Drift Severity | KS Range | Action | Trees Added | Typical Improvement |
|---|---|---|---|---|
| None | < 0.05 | Monitor | 0 | 0% |
| Mild | 0.05-0.15 | Fine-tune | 10-50 | 3-8% |
| Severe | > 0.2 | Retrain | N/A | 8-15% |

## Implementation Details

### Tier 1: Monitor
```python
# No action taken
action = {
    "action": "monitor",
    "model_updated": False,
    "improvement": 0.0
}
```

### Tier 2: Fine-Tune
```python
# Calculate drift magnitude (0-1)
drift_magnitude = min(ks_max / 0.2, 1.0)

# Determine trees to add
trees_to_add = int(10 + drift_magnitude * 40)

# Example: KS=0.10 → drift_magnitude=0.5 → trees_to_add=30
```

### Tier 3: Retrain
```python
# Use optimized hyperparameters
RandomForestRegressor(
    n_estimators=500,
    max_depth=30,
    min_samples_leaf=2,
    max_features=0.7
)
```

## Validation & Rollback

All actions validated on holdout set:

```python
improvement = (old_mae - new_mae) / old_mae

if improvement >= 0.05:  # 5% threshold
    deploy_model()
else:
    rollback_to_previous()
```

## API Usage

### Get Healing Statistics
```bash
curl http://localhost:8000/api/healing-actions
```

Response:
```json
{
  "total_actions": 12,
  "monitor_only": 3,
  "fine_tuned": 7,
  "retrained": 1,
  "rollbacks": 1,
  "avg_improvement": 0.0456
}
```

## Monitoring Dashboard

The React dashboard shows:
- **Healing Actions Tab**: Total actions, breakdown by type
- **Improvement Chart**: Average improvement over time
- **Action History**: Detailed log of each healing action
- **Model Status**: Current model version and update timestamp

## Example Scenarios

### Scenario 1: Stable Model
```
Month: 2012-05
Drift: NONE (KS=0.03)
Action: MONITOR
Result: No model update
```

### Scenario 2: Mild Drift
```
Month: 2012-04
Drift: MILD (KS=0.12)
Action: FINE-TUNE
Trees Added: 32
Old MAE: $58,200
New MAE: $55,100
Improvement: 5.32%
Result: Model deployed ✓
```

### Scenario 3: Severe Drift
```
Month: 2012-03
Drift: SEVERE (KS=0.28)
Action: RETRAIN
Old MAE: $67,394
New MAE: $58,200
Improvement: 13.78%
Result: Model deployed ✓
```

### Scenario 4: Healing Failed
```
Month: 2012-06
Drift: MILD (KS=0.11)
Action: FINE-TUNE
Old MAE: $55,100
New MAE: $54,800
Improvement: 0.54%
Result: ROLLBACK (< 5% threshold)
```

## Performance Metrics

Typical performance after healing:

| Metric | Before | After | Improvement |
|---|---|---|---|
| MAE | $67,394 | $58,200 | 13.6% |
| RMSE | $89,500 | $76,200 | 14.9% |
| MAPE | 8.2% | 7.1% | 13.4% |

## Troubleshooting

### Fine-tune not improving
- Check if drift is real (not noise)
- Verify validation set quality
- Consider full retrain instead

### Retrain failing
- Ensure sufficient training data (min 100 rows)
- Check for NaN/Inf values in features
- Verify model type is supported

### Rollback occurring
- Improvement threshold may be too high
- Consider adjusting to 3% for sensitive applications
- Check if drift is temporary

## Configuration

Edit `fine_tuner.py` to adjust:

```python
# Improvement threshold (default: 5%)
threshold = 0.05

# Trees to add formula (default: 10-50)
trees_to_add = int(10 + drift_magnitude * 40)

# Retrain hyperparameters
n_estimators = 500
max_depth = 30
learning_rate = 0.03
```

## Files

- `fine_tuner.py`: Core fine-tuning logic
- `pipeline.py`: Integration with main pipeline
- `api.py`: `/api/healing-actions` endpoint
- `FINE_TUNING.md`: Detailed documentation
