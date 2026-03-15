# Fine-Tuning & Self-Healing System

## Overview

When drift is detected, the system automatically applies one of three healing actions based on drift severity:

1. **Tier 1 (Monitor)**: KS < 0.05 → No action, continue monitoring
2. **Tier 2 (Fine-tune)**: KS 0.05-0.15 → Warm start with additional trees
3. **Tier 3 (Retrain)**: KS > 0.2 → Full retrain on rolling window

## Architecture

### FineTuner Class (`fine_tuner.py`)

```python
class FineTuner:
    def __init__(self, base_model, feature_names)
    def monitor_only(drift_report)
    def fine_tune_warm_start(X_current, y_current, X_val, y_val, drift_report)
    def full_retrain(X_train, y_train, X_val, y_val, drift_report)
    def decide_healing_action(drift_report, X_current, y_current, X_val, y_val, X_train, y_train)
    def save_healed_model(path)
```

### Integration with Pipeline

The pipeline now:
1. Trains initial model (Step 4)
2. Initializes FineTuner with trained model (Step 5)
3. For each month:
   - Detects drift
   - If drift detected → calls `decide_healing_action()`
   - Applies appropriate healing tier
   - Logs action and improvement
4. Aggregates healing statistics (Step 6)
5. Saves healed model if improvements made (Step 7)

## Healing Tiers

### Tier 1: Monitor Only

**Trigger**: Low drift (KS < 0.05)

**Action**: No model update, continue monitoring

**Use case**: Model is stable, no intervention needed

```python
action = {
    "action": "monitor",
    "severity": "none",
    "reason": "Low drift detected",
    "model_updated": False,
    "improvement": 0.0,
}
```

### Tier 2: Fine-Tune with Warm Start

**Trigger**: Mild drift (KS 0.05-0.15)

**Action**: Add trees proportional to drift magnitude

**Formula**: `trees_to_add = 10 + drift_magnitude * 40`

**Process**:
1. Calculate drift magnitude (0-1 scale)
2. Determine trees to add (10-50 trees)
3. Create new model with increased n_estimators
4. Fit on combined current + validation data
5. Validate on holdout set
6. Deploy if improvement ≥ 5%, else rollback

**Example**:
```python
action = {
    "action": "fine_tune",
    "severity": "mild",
    "trees_added": 25,
    "old_mae": 45230.50,
    "new_mae": 42100.75,
    "improvement": 0.0691,  # 6.91% improvement
    "model_updated": True,
}
```

### Tier 3: Full Retrain

**Trigger**: Severe drift (KS > 0.2)

**Action**: Complete retraining with optimized hyperparameters

**Process**:
1. Create new model with optimized hyperparameters
2. Fit on combined training + validation data
3. Validate on holdout set
4. Deploy if improvement ≥ 5%, else rollback

**Hyperparameters**:
- Random Forest: n_estimators=500, max_depth=30, min_samples_leaf=2
- Gradient Boosting: n_estimators=300, learning_rate=0.03, max_depth=5

**Example**:
```python
action = {
    "action": "retrain",
    "severity": "severe",
    "train_samples": 8500,
    "old_mae": 67500.00,
    "new_mae": 58200.00,
    "improvement": 0.1378,  # 13.78% improvement
    "model_updated": True,
}
```

## Validation & Rollback

All healing actions are validated on a holdout set:

```python
def _validate_improvement(old_mae, new_mae, threshold=0.05):
    improvement = (old_mae - new_mae) / (old_mae + 1e-9)
    return improvement >= threshold, improvement
```

**Rollback Conditions**:
- Improvement < 5%
- Exception during fine-tuning/retraining
- Model type not supported

**Rollback Action**:
```python
action = {
    "action": "rollback",
    "severity": "mild",
    "reason": "Fine-tune improvement 2.3% < 5% threshold",
    "model_updated": False,
    "improvement": 0.023,
}
```

## API Endpoints

### GET /api/healing-actions

Returns aggregated healing statistics:

```json
{
  "total_actions": 12,
  "monitor_only": 3,
  "fine_tuned": 7,
  "retrained": 1,
  "rollbacks": 1,
  "avg_improvement": 0.0456,
  "recommendation": "Severe drift detected: Healing actions applied"
}
```

## Logging & Monitoring

Each healing action is logged with:
- Timestamp
- Action type (monitor/fine_tune/retrain/rollback)
- Drift severity
- MAE before/after
- Improvement percentage
- Model update status

Example log output:
```
[INFO] 2024-03-13 10:45:23 | Tier 2 (Fine-tune): Warm start with additional trees
[INFO] 2024-03-13 10:45:45 | Fine-tune successful: MAE 45230 → 42100 (6.9% improvement)
[INFO] 2024-03-13 10:45:46 | Healing action: FINE_TUNE | Improvement: 6.9%
```

## Summary Statistics

After all months are processed, the pipeline generates:

```python
healing_stats = {
    "total_actions": 12,
    "monitor_only": 3,
    "fine_tuned": 7,
    "retrained": 1,
    "rollbacks": 1,
}
avg_improvement = 0.0456  # 4.56% average improvement
```

## Model Persistence

If any healing actions resulted in model updates:
- Healed model is saved to `models/active_model.pkl`
- Original model backed up to `models/baseline_model_rf.pkl`
- Version history maintained in logs

## Example Workflow

```
Month: 2012-03
├─ Predictions: 2,145 records
├─ Drift Detection: SEVERE (KS=0.28)
├─ Healing Decision: Tier 3 (Retrain)
├─ Retrain Process:
│  ├─ Train samples: 8,500
│  ├─ Old MAE: $67,394
│  ├─ New MAE: $58,200
│  ├─ Improvement: 13.78%
│  └─ Status: DEPLOYED ✓
└─ Model Updated: Yes

Month: 2012-04
├─ Predictions: 2,089 records
├─ Drift Detection: MILD (KS=0.12)
├─ Healing Decision: Tier 2 (Fine-tune)
├─ Fine-tune Process:
│  ├─ Trees added: 32
│  ├─ Old MAE: $58,200
│  ├─ New MAE: $55,100
│  ├─ Improvement: 5.32%
│  └─ Status: DEPLOYED ✓
└─ Model Updated: Yes

Month: 2012-05
├─ Predictions: 2,156 records
├─ Drift Detection: NONE (KS=0.03)
├─ Healing Decision: Tier 1 (Monitor)
└─ Model Updated: No
```

## Configuration

Fine-tuning parameters can be adjusted in `fine_tuner.py`:

```python
# Drift magnitude scaling
drift_magnitude = min(ks_max / 0.2, 1.0)

# Trees to add formula
trees_to_add = int(10 + drift_magnitude * 40)

# Improvement threshold
threshold = 0.05  # 5%

# Hyperparameters for retrain
n_estimators = 500
max_depth = 30
learning_rate = 0.03
```

## Future Enhancements

1. **A/B Testing**: Deploy healed model in shadow mode before production
2. **Multi-metric Validation**: Validate on MAE, RMSE, MAPE, business KPIs
3. **Adaptive Thresholds**: Adjust 5% improvement threshold per domain
4. **Model Versioning**: Track all model versions with performance metrics
5. **Automated Alerts**: Notify when healing actions fail or rollback occurs
6. **Feature Retraining**: Retrain feature engineering pipeline if drift detected
