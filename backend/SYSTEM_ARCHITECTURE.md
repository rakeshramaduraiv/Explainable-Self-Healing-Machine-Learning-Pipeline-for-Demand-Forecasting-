# Fine-Tuning System - Architecture Diagram

## Complete System Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         SH-DFS COMPLETE SYSTEM                             │
└─────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────┐
│                            PIPELINE (pipeline.py)                          │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  Step 1: Load Data                                                         │
│  Step 2: Split Data (Train/Test)                                           │
│  Step 3: Feature Engineering (40+ features)                                │
│  Step 4: Train Model (RF/GB/XGB + Stacking)                                │
│  Step 5: Simulate Months + DRIFT DETECTION + FINE-TUNING ← KEY STEP       │
│  Step 6: Generate Summary (with healing stats)                             │
│  Step 7: Save Results (healed model)                                       │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                    ┌───────────────┼───────────────┐
                    │               │               │
                    ▼               ▼               ▼
        ┌──────────────────┐ ┌──────────────────┐ ┌──────────────────┐
        │ DRIFT DETECTOR   │ │ FINE-TUNER       │ │ LOG BOOK         │
        │ (drift_detector) │ │ (fine_tuner.py)  │ │ (log_book.py)    │
        ├──────────────────┤ ├──────────────────┤ ├──────────────────┤
        │ • KS Test        │ │ • Tier 1: Monitor│ │ • Log actions    │
        │ • PSI Analysis   │ │ • Tier 2: Fine-  │ │ • Track stats    │
        │ • Wasserstein    │ │   Tune           │ │ • Save history   │
        │ • JS Divergence  │ │ • Tier 3: Retrain│ │                  │
        │ • Error Trend    │ │ • Validation     │ │                  │
        │ → Severity       │ │ • Rollback       │ │                  │
        └──────────────────┘ └──────────────────┘ └──────────────────┘
                    │               │               │
                    └───────────────┼───────────────┘
                                    │
                                    ▼
                        ┌──────────────────────┐
                        │ DATABASE (database)  │
                        ├──────────────────────┤
                        │ • Drift logs         │
                        │ • Model versions     │
                        │ • Feature importance │
                        │ • Healing history    │
                        └──────────────────────┘
                                    │
                                    ▼
                        ┌──────────────────────┐
                        │ API (api.py)         │
                        ├──────────────────────┤
                        │ GET /api/health      │
                        │ GET /api/summary     │
                        │ GET /api/drift       │
                        │ GET /api/healing-    │
                        │     actions ← NEW    │
                        │ GET /api/feature-    │
                        │     importances      │
                        │ POST /api/upload-    │
                        │      predict         │
                        └──────────────────────┘
                                    │
                                    ▼
                        ┌──────────────────────┐
                        │ REACT DASHBOARD      │
                        ├──────────────────────┤
                        │ • Overview           │
                        │ • Drift Analysis     │
                        │ • Model Performance  │
                        │ • Feature Importance │
                        │ • Store Analytics    │
                        │ • Predictions        │
                        │ • Upload & Monitor   │
                        └──────────────────────┘
```

---

## Monthly Simulation Flow

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                      FOR EACH MONTH IN TEST SET                            │
└─────────────────────────────────────────────────────────────────────────────┘

Month: 2012-03 (Example)
│
├─ Data: 2,089 records
│
├─ Step 1: Make Predictions
│  ├─ X = features for this month
│  ├─ y_pred = model.predict(X)
│  ├─ y_actual = actual sales
│  └─ errors = y_actual - y_pred
│
├─ Step 2: Detect Drift
│  ├─ KS Test: 0.12 ← MILD DRIFT!
│  ├─ PSI: 0.18
│  ├─ Wasserstein: 0.45
│  ├─ JS Divergence: 0.08
│  ├─ Error Trend: +8.5%
│  └─ Severity: MILD
│
├─ Step 3: Decide Healing Action
│  ├─ KS = 0.12 (0.05-0.15 range)
│  ├─ Severity = MILD
│  └─ Action = TIER 2: FINE-TUNE ← FINE-TUNING TRIGGERED!
│
├─ Step 4: Apply Fine-Tuning
│  ├─ Calculate drift magnitude: 0.12 / 0.2 = 0.6
│  ├─ Trees to add: 10 + 0.6*40 = 34
│  ├─ New model: RandomForest(n_estimators=334)
│  ├─ Fit on: [current_month_data, validation_data]
│  ├─ Validate on: holdout_set
│  │  ├─ Old MAE: $58,200
│  │  ├─ New MAE: $55,100
│  │  └─ Improvement: 5.32%
│  ├─ Check threshold: 5.32% >= 5% ✓
│  └─ Decision: DEPLOY ✓
│
├─ Step 5: Save Results
│  ├─ Save new model to models/active_model.pkl
│  ├─ Log action: "fine_tune"
│  ├─ Log improvement: 5.32%
│  ├─ Update stats
│  └─ Save predictions to processed/
│
└─ Step 6: Continue to Next Month
   └─ Repeat for 2012-04, 2012-05, ...
```

---

## Tier 2: Fine-Tuning Detailed Flow

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    TIER 2: FINE-TUNING (MILD DRIFT)                        │
└─────────────────────────────────────────────────────────────────────────────┘

INPUT:
├─ Current month data: X_current, y_current
├─ Validation data: X_val, y_val
├─ Drift report: severity="mild", ks_max=0.12
└─ Base model: RandomForest(n_estimators=300)

PROCESS:
│
├─ 1. Calculate Drift Magnitude
│  ├─ Formula: drift_magnitude = min(ks_max / 0.2, 1.0)
│  ├─ Example: min(0.12 / 0.2, 1.0) = 0.6
│  └─ Result: drift_magnitude = 0.6
│
├─ 2. Determine Trees to Add
│  ├─ Formula: trees_to_add = int(10 + drift_magnitude * 40)
│  ├─ Example: int(10 + 0.6 * 40) = 34
│  └─ Result: trees_to_add = 34
│
├─ 3. Create New Model
│  ├─ Old: RandomForest(n_estimators=300, max_depth=30, ...)
│  ├─ New: RandomForest(n_estimators=334, max_depth=30, ...)
│  └─ Result: new_model created
│
├─ 4. Prepare Training Data
│  ├─ X_combined = [X_current, X_val]
│  ├─ y_combined = [y_current, y_val]
│  ├─ Total samples: ~4,000
│  └─ Result: combined data ready
│
├─ 5. Fit New Model
│  ├─ new_model.fit(X_combined, y_combined)
│  ├─ Time: 5-10 seconds
│  └─ Result: model trained on new patterns
│
├─ 6. Validate on Holdout Set
│  ├─ old_pred = base_model.predict(X_val)
│  ├─ new_pred = new_model.predict(X_val)
│  ├─ old_mae = mean_absolute_error(y_val, old_pred) = $58,200
│  ├─ new_mae = mean_absolute_error(y_val, new_pred) = $55,100
│  └─ Result: metrics calculated
│
├─ 7. Calculate Improvement
│  ├─ improvement = (old_mae - new_mae) / old_mae
│  ├─ improvement = (58,200 - 55,100) / 58,200
│  ├─ improvement = 3,100 / 58,200
│  ├─ improvement = 0.0532 (5.32%)
│  └─ Result: improvement = 5.32%
│
├─ 8. Check Improvement Threshold
│  ├─ threshold = 0.05 (5%)
│  ├─ if improvement >= threshold:
│  │  └─ DEPLOY ✓
│  └─ else:
│     └─ ROLLBACK ✗
│
├─ 9. Decision: DEPLOY ✓
│  ├─ improvement (5.32%) >= threshold (5%) ✓
│  └─ Action: DEPLOY new model
│
└─ 10. Save Results
   ├─ Save new model to models/active_model.pkl
   ├─ Log action: "fine_tune"
   ├─ Log improvement: 0.0532
   ├─ Log trees_added: 34
   ├─ Log old_mae: 58200
   ├─ Log new_mae: 55100
   └─ Update healing_actions list

OUTPUT:
├─ action: "fine_tune"
├─ severity: "mild"
├─ trees_added: 34
├─ old_mae: 58200
├─ new_mae: 55100
├─ improvement: 0.0532
├─ model_updated: True
└─ status: "DEPLOYED"
```

---

## Decision Tree

```
                    DRIFT DETECTED?
                          │
        ┌─────────────────┼─────────────────┐
        │                 │                 │
        ▼                 ▼                 ▼
    ┌────────┐        ┌────────┐       ┌────────┐
    │ KS<0.05│        │0.05-0.15       │KS>0.2  │
    │ NONE   │        │ MILD   │       │SEVERE  │
    └────────┘        └────────┘       └────────┘
        │                 │                 │
        ▼                 ▼                 ▼
    ┌────────┐        ┌────────┐       ┌────────┐
    │TIER 1  │        │TIER 2  │       │TIER 3  │
    │MONITOR │        │FINE-   │       │RETRAIN │
    │        │        │TUNE    │       │        │
    └────────┘        └────────┘       └────────┘
        │                 │                 │
        │                 ▼                 ▼
        │            ┌────────────┐   ┌────────────┐
        │            │Add Trees   │   │Full Retrain│
        │            │(10-50)     │   │(500 trees) │
        │            └────────────┘   └────────────┘
        │                 │                 │
        │                 ▼                 ▼
        │            ┌────────────┐   ┌────────────┐
        │            │Fit on      │   │Fit on      │
        │            │Combined    │   │Combined    │
        │            │Data        │   │Data        │
        │            └────────────┘   └────────────┘
        │                 │                 │
        │                 ▼                 ▼
        │            ┌────────────┐   ┌────────────┐
        │            │Validate    │   │Validate    │
        │            │Improvement │   │Improvement │
        │            └────────────┘   └────────────┘
        │                 │                 │
        │            ┌────┴────┐       ┌────┴────┐
        │            │          │       │          │
        │            ▼          ▼       ▼          ▼
        │        ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐
        │        │≥5%?    │ │<5%?    │ │≥5%?    │ │<5%?    │
        │        │DEPLOY  │ │ROLLBACK│ │DEPLOY  │ │ROLLBACK│
        │        └────────┘ └────────┘ └────────┘ └────────┘
        │            │          │       │          │
        └────────────┴──────────┴───────┴──────────┘
                          │
                          ▼
                ┌──────────────────┐
                │ Log Action       │
                │ Save Model       │
                │ Update Stats     │
                └──────────────────┘
```

---

## Data Flow

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                            DATA FLOW DIAGRAM                               │
└─────────────────────────────────────────────────────────────────────────────┘

Raw Data (CSV)
    │
    ▼
┌──────────────────┐
│ Data Loader      │
│ (data_loader.py) │
└──────────────────┘
    │
    ▼
┌──────────────────┐
│ Feature Engineer │
│ (feature_eng)    │
│ 40+ features     │
└──────────────────┘
    │
    ├─ Train Data (40%)
    │  │
    │  ▼
    │ ┌──────────────────┐
    │ │ Model Trainer    │
    │ │ (model_trainer)  │
    │ │ RF/GB/XGB        │
    │ └──────────────────┘
    │  │
    │  ▼
    │ ┌──────────────────┐
    │ │ Trained Model    │
    │ │ (active_model)   │
    │ └──────────────────┘
    │  │
    │  ▼
    │ ┌──────────────────┐
    │ │ Fine-Tuner Init  │
    │ │ (fine_tuner.py)  │
    │ └──────────────────┘
    │
    └─ Test Data (60%)
       │
       ├─ For Each Month
       │  │
       │  ├─ Predictions
       │  │  │
       │  │  ▼
       │  │ ┌──────────────────┐
       │  │ │ Drift Detector   │
       │  │ │ (drift_detector) │
       │  │ │ 5 methods        │
       │  │ └──────────────────┘
       │  │  │
       │  │  ▼
       │  │ ┌──────────────────┐
       │  │ │ Fine-Tuner       │
       │  │ │ (fine_tuner.py)  │
       │  │ │ 3 tiers          │
       │  │ └──────────────────┘
       │  │  │
       │  │  ▼
       │  │ ┌──────────────────┐
       │  │ │ Updated Model    │
       │  │ │ (if improved)    │
       │  │ └──────────────────┘
       │  │
       │  └─ Log Results
       │     │
       │     ▼
       │  ┌──────────────────┐
       │  │ Log Book         │
       │  │ (log_book.py)    │
       │  └──────────────────┘
       │     │
       │     ▼
       │  ┌──────────────────┐
       │  │ Database         │
       │  │ (database.py)    │
       │  └──────────────────┘
       │
       └─ Aggregate Stats
          │
          ▼
       ┌──────────────────┐
       │ Summary Report   │
       │ (healing_stats)  │
       └──────────────────┘
          │
          ▼
       ┌──────────────────┐
       │ API              │
       │ (api.py)         │
       │ /api/healing-    │
       │  actions         │
       └──────────────────┘
          │
          ▼
       ┌──────────────────┐
       │ React Dashboard  │
       │ (frontend)       │
       └──────────────────┘
```

---

## Summary

✅ **Complete system architecture**
✅ **Automatic drift detection** (5 methods)
✅ **Automatic fine-tuning** (Tier 2 for mild drift)
✅ **Automatic retraining** (Tier 3 for severe drift)
✅ **Validation & rollback** (5% threshold)
✅ **Logging & monitoring** (complete history)
✅ **API integration** (healing stats exposed)
✅ **Production ready** (error handling, validation)

**System is complete and ready to use! 🎉**
