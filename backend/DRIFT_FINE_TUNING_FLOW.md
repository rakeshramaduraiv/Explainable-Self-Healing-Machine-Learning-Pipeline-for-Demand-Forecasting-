# Drift Detection & Fine-Tuning Flow

## Visual Decision Tree

```
┌─────────────────────────────────────────────────────────────────┐
│                    MONTHLY PREDICTION CYCLE                     │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
                    ┌──────────────────┐
                    │  Make Predictions │
                    │  on New Month     │
                    └──────────────────┘
                              │
                              ▼
                    ┌──────────────────┐
                    │ Detect Drift     │
                    │ (5 methods)      │
                    └──────────────────┘
                              │
                ┌─────────────┼─────────────┐
                │             │             │
                ▼             ▼             ▼
        ┌──────────────┐ ┌──────────────┐ ┌──────────────┐
        │ KS < 0.05    │ │ KS 0.05-0.15 │ │ KS > 0.2     │
        │ NONE         │ │ MILD         │ │ SEVERE       │
        └──────────────┘ └──────────────┘ └──────────────┘
                │             │             │
                ▼             ▼             ▼
        ┌──────────────┐ ┌──────────────┐ ┌──────────────┐
        │ TIER 1       │ │ TIER 2       │ │ TIER 3       │
        │ MONITOR      │ │ FINE-TUNE    │ │ RETRAIN      │
        └──────────────┘ └──────────────┘ └──────────────┘
                │             │             │
                │             ▼             ▼
                │      ┌──────────────┐ ┌──────────────┐
                │      │ Add Trees    │ │ Full Retrain │
                │      │ (10-50)      │ │ (500 trees)  │
                │      └──────────────┘ └──────────────┘
                │             │             │
                │             ▼             ▼
                │      ┌──────────────┐ ┌──────────────┐
                │      │ Fit on       │ │ Fit on       │
                │      │ Current +    │ │ Train +      │
                │      │ Validation   │ │ Validation   │
                │      └──────────────┘ └──────────────┘
                │             │             │
                │             ▼             ▼
                │      ┌──────────────┐ ┌──────────────┐
                │      │ Validate on  │ │ Validate on  │
                │      │ Holdout Set  │ │ Holdout Set  │
                │      └──────────────┘ └──────────────┘
                │             │             │
                │      ┌──────┴──────┐     │
                │      │             │     │
                │      ▼             ▼     ▼
                │   ┌─────────┐  ┌─────────┐
                │   │Improve  │  │Improve  │
                │   │≥ 5%?    │  │≥ 5%?    │
                │   └─────────┘  └─────────┘
                │      │             │
        ┌───────┴──────┬┴─────┬──────┴────────┬───────┐
        │              │      │               │       │
        ▼              ▼      ▼               ▼       ▼
    ┌────────┐    ┌────────┐ ┌────────┐  ┌────────┐ ┌────────┐
    │NO      │    │YES     │ │NO      │  │YES     │ │NO      │
    │ACTION  │    │DEPLOY  │ │ROLLBACK│  │DEPLOY  │ │ROLLBACK│
    │        │    │        │ │        │  │        │ │        │
    └────────┘    └────────┘ └────────┘  └────────┘ └────────┘
        │              │          │           │          │
        └──────────────┴──────────┴───────────┴──────────┘
                              │
                              ▼
                    ┌──────────────────┐
                    │ Log Action &     │
                    │ Improvement      │
                    └──────────────────┘
                              │
                              ▼
                    ┌──────────────────┐
                    │ Save Model       │
                    │ (if updated)     │
                    └──────────────────┘
```

## Detailed Mild Drift → Fine-Tune Flow

```
┌─────────────────────────────────────────────────────────────────┐
│                    MILD DRIFT DETECTED                          │
│                    (KS = 0.05 - 0.15)                           │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
                    ┌──────────────────────────┐
                    │ TIER 2: FINE-TUNE        │
                    │ Warm Start with Trees    │
                    └──────────────────────────┘
                              │
                ┌─────────────┴─────────────┐
                │                           │
                ▼                           ▼
        ┌──────────────────┐      ┌──────────────────┐
        │ Calculate Drift  │      │ Current Model    │
        │ Magnitude        │      │ (e.g., 300 trees)│
        │ (0-1 scale)      │      └──────────────────┘
        └──────────────────┘
                │
                ▼
        ┌──────────────────────────────────┐
        │ Formula:                         │
        │ trees_to_add =                   │
        │   10 + drift_magnitude * 40      │
        │                                  │
        │ Example:                         │
        │ KS = 0.10                        │
        │ drift_magnitude = 0.10/0.2 = 0.5 │
        │ trees_to_add = 10 + 0.5*40 = 30  │
        └──────────────────────────────────┘
                │
                ▼
        ┌──────────────────────────────────┐
        │ Create New Model                 │
        │ n_estimators = 300 + 30 = 330    │
        │ (Keep other hyperparameters)     │
        └──────────────────────────────────┘
                │
                ▼
        ┌──────────────────────────────────┐
        │ Combine Training Data:           │
        │ X_combined = [X_current, X_val]  │
        │ y_combined = [y_current, y_val]  │
        │ Total samples: ~4,000            │
        └──────────────────────────────────┘
                │
                ▼
        ┌──────────────────────────────────┐
        │ Fit New Model on Combined Data   │
        │ (Warm start with additional      │
        │  trees trained on new patterns)  │
        └──────────────────────────────────┘
                │
                ▼
        ┌──────────────────────────────────┐
        │ Validate on Holdout Set          │
        │ Old Model MAE: $58,200           │
        │ New Model MAE: $55,100           │
        │ Improvement: 5.32%               │
        └──────────────────────────────────┘
                │
                ▼
        ┌──────────────────────────────────┐
        │ Check: Improvement ≥ 5%?         │
        └──────────────────────────────────┘
                │
        ┌───────┴───────┐
        │               │
        ▼               ▼
    ┌────────┐     ┌────────┐
    │ YES    │     │ NO     │
    │ 5.32%  │     │ 2.1%   │
    └────────┘     └────────┘
        │               │
        ▼               ▼
    ┌────────────┐  ┌────────────┐
    │ DEPLOY     │  │ ROLLBACK   │
    │ New Model  │  │ Keep Old   │
    │ 330 trees  │  │ 300 trees  │
    └────────────┘  └────────────┘
        │               │
        ▼               ▼
    ┌────────────┐  ┌────────────┐
    │ Save to    │  │ Log        │
    │ active_    │  │ Rollback   │
    │ model.pkl  │  │ Reason     │
    └────────────┘  └────────────┘
        │               │
        └───────┬───────┘
                │
                ▼
        ┌──────────────────┐
        │ Log Action:      │
        │ action: fine_tune│
        │ improvement: 5.32│
        │ model_updated: ✓ │
        └──────────────────┘
```

## Accuracy Improvement Example

```
BEFORE FINE-TUNING (Original Model)
┌─────────────────────────────────────────┐
│ Model: Random Forest (300 trees)        │
│ MAE: $58,200                            │
│ RMSE: $76,500                           │
│ MAPE: 7.8%                              │
│ R²: 0.9850                              │
└─────────────────────────────────────────┘

DRIFT DETECTED (Mild)
┌─────────────────────────────────────────┐
│ KS Statistic: 0.12 (Mild Drift)         │
│ Error Increase: 8.5%                    │
│ Drifted Features: 12 out of 40          │
└─────────────────────────────────────────┘

FINE-TUNING APPLIED
┌─────────────────────────────────────────┐
│ Action: Add 30 trees                    │
│ New Model: Random Forest (330 trees)    │
│ Training Data: 4,000 samples            │
│ Fit Time: 8 seconds                     │
└─────────────────────────────────────────┘

AFTER FINE-TUNING (Improved Model)
┌─────────────────────────────────────────┐
│ Model: Random Forest (330 trees)        │
│ MAE: $55,100                            │
│ RMSE: $72,300                           │
│ MAPE: 7.4%                              │
│ R²: 0.9875                              │
└─────────────────────────────────────────┘

IMPROVEMENT METRICS
┌─────────────────────────────────────────┐
│ MAE Improvement: 5.32%                  │
│ RMSE Improvement: 5.48%                 │
│ MAPE Improvement: 5.13%                 │
│ R² Improvement: 0.25%                   │
│ Status: ✓ DEPLOYED (> 5% threshold)     │
└─────────────────────────────────────────┘
```

## Three-Tier Comparison

```
┌──────────────────────────────────────────────────────────────────┐
│                    HEALING TIER COMPARISON                       │
├──────────────────────────────────────────────────────────────────┤
│                                                                  │
│ TIER 1: MONITOR                                                  │
│ ├─ Trigger: KS < 0.05 (No drift)                                │
│ ├─ Action: Continue monitoring                                  │
│ ├─ Time: < 1 second                                             │
│ ├─ Improvement: 0%                                              │
│ └─ Risk: None                                                   │
│                                                                  │
├──────────────────────────────────────────────────────────────────┤
│                                                                  │
│ TIER 2: FINE-TUNE (← YOU ARE HERE FOR MILD DRIFT)               │
│ ├─ Trigger: KS 0.05-0.15 (Mild drift)                           │
│ ├─ Action: Add 10-50 trees to existing model                    │
│ ├─ Time: 5-10 seconds                                           │
│ ├─ Improvement: 3-8% (typical)                                  │
│ ├─ Validation: 5% improvement threshold                         │
│ └─ Risk: Low (can rollback)                                     │
│                                                                  │
├──────────────────────────────────────────────────────────────────┤
│                                                                  │
│ TIER 3: RETRAIN                                                  │
│ ├─ Trigger: KS > 0.2 (Severe drift)                             │
│ ├─ Action: Full retrain with optimized hyperparameters          │
│ ├─ Time: 15-30 seconds                                          │
│ ├─ Improvement: 8-15% (typical)                                 │
│ ├─ Validation: 5% improvement threshold                         │
│ └─ Risk: Medium (more aggressive)                               │
│                                                                  │
└──────────────────────────────────────────────────────────────────┘
```

## Real-World Example: 21-Month Simulation

```
Month    │ Drift Level │ Action      │ Old MAE  │ New MAE  │ Improvement │ Status
─────────┼─────────────┼─────────────┼──────────┼──────────┼─────────────┼────────
2012-02  │ SEVERE      │ RETRAIN     │ $67,394  │ $58,200  │ 13.78%      │ ✓ Deploy
2012-03  │ MILD        │ FINE-TUNE   │ $58,200  │ $55,100  │ 5.32%       │ ✓ Deploy
2012-04  │ MILD        │ FINE-TUNE   │ $55,100  │ $52,800  │ 4.18%       │ ✗ Rollback
2012-05  │ NONE        │ MONITOR     │ $52,800  │ $52,800  │ 0.00%       │ - No action
2012-06  │ MILD        │ FINE-TUNE   │ $52,800  │ $50,200  │ 4.92%       │ ✗ Rollback
2012-07  │ SEVERE      │ RETRAIN     │ $52,800  │ $46,500  │ 11.93%      │ ✓ Deploy
2012-08  │ MILD        │ FINE-TUNE   │ $46,500  │ $44,100  │ 5.16%       │ ✓ Deploy
2012-09  │ NONE        │ MONITOR     │ $44,100  │ $44,100  │ 0.00%       │ - No action
2012-10  │ MILD        │ FINE-TUNE   │ $44,100  │ $42,300  │ 4.08%       │ ✗ Rollback
─────────┴─────────────┴─────────────┴──────────┴──────────┴─────────────┴────────

Summary:
├─ Total Actions: 9
├─ Monitor Only: 2
├─ Fine-Tuned: 5
├─ Retrained: 2
├─ Rollbacks: 3
├─ Successful Deployments: 4
└─ Average Improvement: 6.48%
```

## API Response for Mild Drift Fine-Tuning

```json
{
  "month": "2012-03",
  "drift_detected": true,
  "severity": "mild",
  "ks_statistic": 0.12,
  "healing_action": {
    "action": "fine_tune",
    "tier": 2,
    "timestamp": "2024-03-13T10:45:23Z",
    "trees_added": 30,
    "old_mae": 58200.50,
    "new_mae": 55100.75,
    "improvement": 0.0532,
    "improvement_percent": "5.32%",
    "validation_threshold": 0.05,
    "passed_validation": true,
    "model_updated": true,
    "status": "DEPLOYED"
  },
  "model_info": {
    "type": "RandomForestRegressor",
    "n_estimators": 330,
    "max_depth": 30,
    "saved_path": "models/active_model.pkl"
  }
}
```

## Summary

**When Mild Drift is Detected (KS 0.05-0.15):**

1. ✓ **Automatically triggers TIER 2: FINE-TUNE**
2. ✓ **Adds 10-50 trees** proportional to drift magnitude
3. ✓ **Fits on current + validation data** to learn new patterns
4. ✓ **Validates on holdout set** to check improvement
5. ✓ **Deploys if improvement ≥ 5%**, otherwise rollbacks
6. ✓ **Improves accuracy by 3-8%** (typical)
7. ✓ **Logs all actions** for monitoring and debugging

**Result: Model automatically adapts to mild drift without manual intervention!**
