# SH-DFS — Staff Explanation

## What Is This System?

SH-DFS (Self-Healing Demand Forecasting System) is a machine learning platform that **predicts product demand** (units per product per week). It has two distinct operational modes:

1. **Full pipeline** (`python main.py`) — runs an 8-step pipeline on historical data, trains an XGBoost model from scratch, simulates 12 test months, detects drift, and applies self-healing. Runs once to set up the system.
2. **Upload & Monitor** (frontend page) — scores any new CSV against the **already-trained model** without retraining. Produces full drift analysis + healing recommendations per month. Fast (seconds, not minutes).

---

## Dataset

**Retail Sales Forecasting Dataset** (`retail_sales.csv`)

- **4,565,000 rows** of daily sales — 5 years (2019-01-01 to 2023-12-31)
- **50 stores** (`store_1`…`store_50`) × **50 products** (`item_1`…`item_50`) = 2,500 unique combinations
- Each store-product pair has exactly **1,826 daily rows** — no missing values
- Columns: `date`, `store_id`, `item_id`, `sales`, `price`, `promo`, `weekday`, `month`
- Aggregated to **weekly demand** via `generate_data.py` → ~237,250 weekly rows
- The system auto-renames: `sales`→Demand, `item_id`→Product, `store_id`→Store, `date`→Date

**Train/Test Split:**
- Train: 2019–2022 (4 years, ~189,800 weekly rows)
- Test: 2023 (1 year, ~47,450 weekly rows)

---

## Two Operational Modes

### Mode 1: Full Pipeline (`python main.py`)

Runs once. Takes 5–15 minutes on the full dataset.

```
Step 1: Load & Inspect   → Read CSV, validate columns, compute data stats
Step 2: Split            → 2019–2022 = Training, 2023 = Testing
Step 3: Feature Eng.     → Generate 63–87+ features (see below)
Step 4: Train Model      → XGBoost (primary) + Random Forest (for CI intervals)
Step 5: Simulate Months  → Test month-by-month: predict → detect drift → heal
Step 6: Summary          → Aggregate severity counts, healing stats
Step 7: Save Results     → Logs, processed CSVs, model files
Step 8: First Prediction → Predict first future month (2024-01)
```

Saves: `models/active_model.pkl`, `models/feature_engineer.pkl`, `models/baseline_model_rf.pkl`, all log files.

### Mode 2: Upload & Monitor (frontend Upload page → `POST /api/upload-monitor`)

Runs in seconds. No retraining.

```
Load existing model (active_model.pkl) + feature engineer (feature_engineer.pkl)
        ↓
Run feature engineering on uploaded CSV (fit=False — uses saved state)
        ↓
Build baseline distributions from 50K-row sample of training data
        ↓
For each month in uploaded data:
  → Predict with existing model
  → Run 5-method drift detection (KS, PSI, Wasserstein, JS, Error Trend)
  → Assess healing action (no model.fit() — assessment only)
  → Save predictions to processed/
        ↓
Return: drift reports + healing actions + summary
```

**Why fast:** baseline uses 50K-row sample (not full 190K training rows), no model.fit() called, single timestamp for all output files.

---

## Dynamic Feature Engineering — How Columns Become 63–87+ Features

The user uploads 4–9 columns. The system auto-generates features inside `feature_engineering.py`. The user never touches these.

### Feature Breakdown

| Group | Count | Source | What It Captures |
|-------|-------|--------|-----------------|
| **Temporal** | 18 | From Date | Year, Month, Week, Quarter, DayOfYear, sin/cos cycles, holiday flags, season flags |
| **Lag (Sliding Window)** | 7 | From Demand history | Demand 1, 2, 3, 4, 6, 8, 12 weeks ago per Product+Store |
| **Rolling Stats** | 20 | From Demand history | Mean/Std/Max/Min over 3, 4, 6, 8, 12 week windows (shift(1) to prevent leakage) |
| **Momentum/Volatility** | 4 | Lag + Rolling | Momentum_3, Momentum_6, Volatility_4, Volatility_8 |
| **Store Stats** | 4 | Store column | Store_Mean, Store_Std, Demand_vs_Store_Mean, Store_CV |
| **Product Stats** | 4 | Product column | Product_Mean, Product_Std, Demand_vs_Product_Mean, Product_CV |
| **Interactions** | 10+ | Numeric columns | Pairwise products of numeric cols (Price×Promo, Lag×Price, etc.) |

### Feature Count by Input

| User Uploads | Features Generated |
|-------------|-------------------|
| Date + Product + Demand | ~48 |
| + Store | ~56 |
| + Store + Price + Promo | ~63 |
| + Store + Price + Promo + Weekday + Month | ~87+ |

---

## Model Training

- **Primary model**: XGBoost (`tree_method='hist'`, `max_bin=256` — optimised for large datasets)
- **CI model**: Random Forest (100 trees, `max_depth=8`) — saved separately as `baseline_model_rf.pkl`, used only for confidence intervals
- **Tuning**: RandomizedSearchCV with TimeSeriesSplit (10 iterations × 2 folds = 20 fits on full dataset)
- **Confidence Intervals**: 95% CI from RF tree variance — `CI = mean_pred ± 1.96 × std(tree_predictions)`
- **Saved as**: `models/active_model.pkl` (XGBoost), `models/baseline_model_rf.pkl` (RF)

---

## Self-Healing — How It Works

During Step 5 (Simulate Months in full pipeline) or during Upload & Monitor, for each month:

### 1. Drift Detection (`drift_detector.py`) — 5 methods, all features

| Method | What It Measures |
|--------|-----------------|
| **KS Test** | Whether feature distributions shifted (dynamic thresholds per feature importance) |
| **PSI** | Magnitude of distribution shift (threshold: 0.1/0.25) |
| **Wasserstein Distance** | Earth mover's distance — applied to **all features** (`top_n=None`) |
| **JS Divergence** | Symmetric distribution difference — applied to **all features** (`top_n=None`) |
| **Error Trend** | MAE increase % vs baseline (threshold: 10%) |

### 2. Feature-Importance Weighting

- Top 20% importance features → thresholds × 0.7 (stricter — these matter more)
- Bottom 20% importance features → thresholds × 1.3 (relaxed — less impact)
- Reduces false positives on low-impact features

### 3. Severity Classification

- **Severe**: Any feature KS > 0.2 or PSI > 0.25, OR error increase > 10%
- **Mild**: >30% of features show mild drift
- **None**: Otherwise

### 4. Healing Action

| Mode | Severity | Action |
|------|----------|--------|
| Full pipeline | None | Monitor only |
| Full pipeline | Mild/Severe | Fine-tune: add estimators, require ≥5% MAE improvement or rollback |
| Upload & Monitor | None | Monitor only (no model.fit()) |
| Upload & Monitor | Mild/Severe | Recommend fine-tune (assessment only, no actual refit) |

In Upload & Monitor mode, healing actions are **recommendations** — the model is never modified. This is what makes it fast.

---

## Sequential Predictor — Monthly Prediction Cycle

After the full pipeline runs, the system enters a continuous cycle managed by `sequential_predictor.py`:

```
Model predicts Month N+1 demand (50 products × ~4 weeks = ~200 rows)
        ↓
User uploads ACTUAL Month N+1 data (Date + Product + Demand)
        ↓
System compares predictions vs actuals (MAE, MAPE, RMSE)
        ↓
System auto-predicts Month N+2
        ↓
Repeat forever
```

**Auto-fill for future months:** When predicting a future month, optional columns (Price, Promo, etc.) are not yet available. The system fills them with the last known values from the most recent historical row, so lag/rolling features still use real historical demand.

---

## Backend Technology Stack

| Component | Technology | File |
|-----------|-----------|------|
| API Server | FastAPI + GZip + CORS | `api.py` |
| Primary ML Model | XGBoost (`tree_method='hist'`) | `model_trainer.py` |
| CI Model | Random Forest (100 trees) | `model_trainer.py` |
| Feature Engineering | pandas, numpy, LabelEncoder | `feature_engineering.py` |
| Drift Detection | scipy (KS, Wasserstein, JS), all features | `drift_detector.py` |
| Self-Healing | Fine-tuner + rollback (≥5% threshold) | `fine_tuner.py` |
| Data Loading | pandas with alias auto-rename | `data_loader.py` |
| Full Pipeline | 8-step Phase1Pipeline | `pipeline.py` |
| Monitor Pipeline | `run_monitor_pipeline()` — no retraining | `main.py` |
| Prediction Cycle | Sequential monthly predictor | `sequential_predictor.py` |
| Caching | In-memory dict with TTL per endpoint | `api.py` |
| Async Upload | `asyncio.run_in_executor` | `api.py` |

### Key API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/upload-monitor` | POST | Upload CSV → score against existing model → drift analysis (fast, no retrain) |
| `/api/upload-predict` | POST | Upload CSV → run full pipeline (slow, retrains model) |
| `/api/seq/predict-next` | POST | Predict next month |
| `/api/seq/upload-actuals` | POST | Upload actuals → compare → predict next |
| `/api/drift` | GET | Drift history per month |
| `/api/healing-history` | GET | Healing actions per month |
| `/api/predictions/{month}` | GET | Test set predictions for a month |
| `/api/feature-importances` | GET | Model feature importances |

### Backend Cache TTLs

| Endpoint Group | TTL |
|---------------|-----|
| demand_metrics, monthly_demand, product_demand | 600s |
| product_forecast, product_monthly, feature_importances | 300s |
| product_names | 300s |
| drift, batches, store_stats | 60–120s |
| processed_months | 30s |
| predictions_meta | no cache (always fresh) |

---

## Frontend Technology Stack

| Component | Technology |
|-----------|-----------|
| Framework | React 18 + Vite |
| Charts | Recharts (bar, line, area, composed, radar, treemap, pie) |
| API Layer | `useFetch` hook: dedup, 15s memory cache, stale-while-revalidate, polling |
| Real-time | `usePredictions` hook: polls `/api/predictions-meta` every 12s |
| Lazy Loading | React.lazy + Suspense for all 10 pages |
| API Pre-warming | `requestIdleCallback` fires slow endpoints on idle startup |

---

## UI Pages — What Each Dashboard Shows

### Group 1: Baseline vs Test Set

**1. Training Overview** — R², MAE, RMSE, MAPE KPIs; MAE trend; drifted features per month; test set vs predicted area chart; healing summary

**2. Drift Detection** — Error increase % per month (color-coded); drifted feature count stacked bar; full drift table with KS/PSI/Wasserstein/severity/error increase

**3. Baseline Performance** — MAE/RMSE/MAPE/R² KPIs; MAE trend with brush; error increase % with threshold reference lines; metrics glossary

### Group 2: Analysis

**4. Feature Importance** — Top-20 horizontal bar; feature group treemap; group filter pills; radial chart; per-group feature cards

**5. Forecasting** — Monthly forecast vs test set; accuracy by product bar; MAE by product; radar chart; product detail table

**6. Predictions Explorer** — Test set vs predicted with 95% CI band + brush; product demand summary; absolute error bar; detail table with quality badges

**7. Demand Insights** — Avg weekly demand, growth rate, peak month KPIs; demand vs forecast bar; demand share pie; monthly aggregation; product×month heatmap

### Group 3: Data

**8. Datasets** — Train/test split info; drift severity summary; monitored batches table

**9. Upload & Monitor** — Drag-and-drop CSV upload; monitor mode (no retraining); drift analysis results per month; healing actions; MAE trend; error increase chart

**10. Predict Cycle** — Sequential prediction workflow; upload actuals; comparison charts; accuracy history; saved predictions browser

---

## Current Pipeline Run Results

| Metric | Value |
|--------|-------|
| Dataset | Retail Sales Forecasting (2019–2023) |
| Source rows | 4,565,000 daily |
| Weekly rows (pipeline input) | ~237,250 |
| Stores | 50 (`store_1`…`store_50`) |
| Products | 50 (`item_1`…`item_50`) |
| Store-Product combos | 2,500 |
| Train years | 2019–2022 |
| Test year | 2023 |
| Features generated | 63–87+ |
| Primary model | XGBoost |
| CI model | Random Forest (100 trees) |
| Training R² | ~1.0 (near-perfect fit) |
| Training MAPE | < 1% |
| Test Months | 12 (2023) |
| First Prediction | 2024-01 |
| Upload & Monitor speed | 15–60 seconds |
| Full pipeline speed | 5–15 minutes |
