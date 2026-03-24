# SH-DFS — Staff Explanation

## What Is This System?

SH-DFS (Self-Healing Demand Forecasting System) is a machine learning platform that **predicts product demand** (units per product per week). It has two modes:

1. **Training mode** — runs an 8-step pipeline on 2 years of historical data, trains a model, simulates 12 test months, detects drift, and applies self-healing
2. **Prediction cycle** — after training, predicts the next month, accepts uploaded actuals, compares predictions vs reality, and repeats indefinitely

---

## Dataset

**Retail Sales Forecasting Dataset** (`retail_sales.csv`)

- **4,565,000 rows** of daily sales — 5 years (2019-01-01 to 2023-12-31)
- **50 stores** (`store_1`…`store_50`) × **50 products** (`item_1`…`item_50`) = 2,500 unique combinations
- Each store-product pair has exactly **1,826 daily rows** — no missing values
- Columns: `date`, `store_id`, `item_id`, `sales`, `price`, `promo`, `weekday`, `month`
- Aggregated to weekly demand via `generate_data.py` before entering the pipeline

The system auto-renames: `sales`→Demand, `item_id`→Product, `store_id`→Store, `date`→Date.

---

## How It Works — Complete User Flow

### Step 1: Upload CSV (Upload & Monitor page)

The user uploads a CSV with **3 required columns**:

| Column | Type | Example |
|--------|------|---------|
| Date | DD-MM-YYYY | 05-01-2019 |
| Product | str/int | item_1 … item_50 |
| Demand | integer (units) | 41 |

**Optional columns** (auto-detected and used as features):
- Store (`store_1`…`store_50`), Price (8.02–99.99), Promo (0/1), Weekday (0–6), Month (1–12)
- Any other numeric or text columns — treated as features automatically

Missing required columns → file rejected with a clear error message.

### Step 2: 8-Step Pipeline Runs Automatically

```
Step 1: Load & Inspect   → Read CSV, validate columns, compute data stats
Step 2: Split            → Year 1 = Training, Year 2 = Testing (based on uploaded data date range)
Step 3: Feature Eng.     → Generate 63 features from 4 columns (see below)
Step 4: Train Model      → RF + GB + XGB → Gradient Boosting selected (best MAE)
Step 5: Simulate Months  → Test month-by-month, detect drift, apply self-healing
Step 6: Summary          → Aggregate severity counts, healing stats
Step 7: Save Results     → Logs, processed CSVs, model files
Step 8: First Prediction → Predict first future month after the data range
```

Pipeline runs asynchronously in a thread executor with a 600-second timeout. Returns HTTP 504 if it exceeds the limit.

### Step 3: Monthly Prediction Cycle (Predict Cycle page)

```
Model predicts Month N+1 demand (50 products × ~4 weeks)
        ↓
User uploads ACTUAL Month N+1 data (Date + Product + Demand)
        ↓
System compares predictions vs actuals (MAE, MAPE, RMSE)
        ↓
System auto-predicts Month N+2
        ↓
User uploads next month actuals → System predicts following month → Repeat forever
```

---

## Dynamic Feature Engineering — How 4 Columns Become 63 Features

The user uploads 4 columns (Date, Store, Product, Demand). The system auto-generates **63 features** inside `feature_engineering.py`. The user never touches these.

### Feature Breakdown (63 features with Date + Store + Product + Demand)

| Group | Count | Source | What It Captures |
|-------|-------|--------|-----------------|
| **Temporal** | 18 | From Date | Year, Month, Week, Quarter, DayOfYear, sin/cos cycles, holiday proximity (weeks 6/47/51), Near_Holiday, Season |
| **Lag (Sliding Window)** | 9 | From Demand history | Demand 1, 2, 3, 4, 8, 12, 26, 52 weeks ago per Product+Store; Lag_52_ratio |
| **Rolling Stats** | 16 | From Demand history | Mean/Std/Max/Min over 4, 8, 12, 26 week windows (shift(1) to prevent leakage) |
| **Momentum/Volatility** | 4 | Lag + Rolling | Momentum_4, Momentum_12, Volatility_4, Volatility_12 |
| **Store Stats** | 8 | Store column | Store_Mean, Store_Median, Store_Std, Store_Max, Store_Min, Demand_vs_Store_Mean, Demand_vs_Store_Median, Store_CV |
| **Product Stats** | 8 | Product column | Product_Mean, Product_Median, Product_Std, Product_Max, Product_Min, Demand_vs_Product_Mean, Demand_vs_Product_Median, Product_CV |

With additional optional columns (Price, Promo, etc.), up to 19 more interaction features are added, reaching 87+ total.

### Feature Count by Input

| User Uploads | Features Generated |
|-------------|-------------------|
| Date + Product + Demand | ~48 |
| + Store | ~56 |
| + Store + Price + Promo + Weekday + Month | ~87 |
| Current dataset (4 cols) | **63** |

---

## Model Training

- **Algorithms**: Random Forest (tuned), Gradient Boosting (fixed params), XGBoost (fixed params)
- **Tuning**: RandomizedSearchCV with TimeSeriesSplit cross-validation (20 iterations)
- **Selection**: Best model by MAE on training data → **Gradient Boosting won**
- **Stacking**: When XGBoost available + ≥100 rows → StackingRegressor (RF+GB+XGB → Ridge meta-learner)
- **Confidence Intervals**: 95% CI from Random Forest tree variance (±1.96 × std of tree predictions)
- **Saved as**: `models/active_model.pkl`

---

## Self-Healing — How It Works

During Step 5 (Simulate Months), for each of the 12 test months:

### 1. Drift Detection (`drift_detector.py`) — 5 methods

| Method | What It Measures |
|--------|-----------------|
| **KS Test** | Whether feature distributions shifted (threshold: 0.05/0.15/0.2) |
| **PSI** | Magnitude of distribution shift (threshold: 0.1/0.25) |
| **Wasserstein Distance** | Earth mover's distance on top-10 features |
| **JS Divergence** | Symmetric distribution difference (20 bins) |
| **Error Trend** | MAE increase % vs baseline (threshold: 10%) |

### 2. Feature-Importance Weighting

- Top 20% importance features → thresholds × 0.7 (stricter)
- Bottom 20% importance features → thresholds × 1.3 (relaxed)
- Reduces false positives on low-impact features

### 3. Severity Classification

- **Severe**: Any feature KS > 0.2 or PSI > 0.25, OR error increase > 10%
- **Mild**: >30% of features show mild drift
- **None**: Otherwise

### 4. Healing Action (`fine_tuner.py`)

| Severity | Action |
|----------|--------|
| None | Monitor only — no model change |
| Mild / Severe | Fine-tune: add estimators using current month's data |
| Fine-tune result < 5% improvement | **Rollback** to previous model version |

Each fine-tuned model is saved as `models/model_v1_{timestamp}.pkl` with metadata JSON. Rollback restores the previous version atomically.

---

## Sequential Predictor — Auto-Fill for Future Months

When predicting a future month (e.g., 2018-01), optional columns like Temperature and CPI are not yet available. `sequential_predictor.py` handles this:

1. Gets the **last row** of all existing data (last week of the training period)
2. Reads last-known values for optional columns (Price, Promo, etc.)
3. Creates **scaffold rows**: 4 weeks × 50 products = 200 rows for the next month
4. Fills each scaffold row with those last-known values
5. Sets Demand = NaN (what the model will predict)
6. Runs full feature engineering on combined historical + scaffold data
7. Lag/rolling features use **real historical demand** — only optional columns use last-known values
8. Model predicts Demand for each scaffold row

---

## Backend Technology Stack

| Component | Technology | File |
|-----------|-----------|------|
| API Server | FastAPI + GZip + CORS | `api.py` |
| ML Models | scikit-learn, XGBoost | `model_trainer.py` |
| Feature Engineering | pandas, numpy, LabelEncoder | `feature_engineering.py` |
| Drift Detection | scipy (KS, Wasserstein, JS) | `drift_detector.py` |
| Self-Healing | Custom fine-tuner + rollback | `fine_tuner.py` |
| Data Loading | pandas with alias auto-rename | `data_loader.py` |
| Prediction Cycle | Sequential monthly predictor | `sequential_predictor.py` |
| Demand Analysis | Aggregation + metrics | `demand_analyzer.py` |
| Caching | In-memory dict with TTL per endpoint | `api.py` |
| Async Upload | `asyncio.run_in_executor` + 600s timeout | `api.py` |
| NaN Sanitizer | Recursive `_clean()` before JSON | `api.py` |

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
| State | useState, useMemo, useCallback, useEffect, useTransition |
| API Layer | `useFetch` hook: dedup, 60s memory cache, stale-while-revalidate, polling |
| Real-time | `usePredictions` hook: polls `/api/predictions-meta` every 12s for file changes |
| Lazy Loading | React.lazy + Suspense for all 10 pages |
| API Pre-warming | `requestIdleCallback` fires 12 slow endpoints on idle startup |
| Styling | CSS variables, responsive grid |

---

## UI Pages — What Each Dashboard Shows

### Group 1: Baseline vs Test Set

**1. Training Overview** (`Overview.jsx`)
- KPIs: R², MAE, RMSE, MAPE, Accuracy, Severe Drift count
- Charts: MAE trend bar, drifted features per month, test set vs predicted area, monthly MAE
- Healing summary: total actions, fine-tuned, rollbacks, avg improvement

**2. Drift Detection** (`Drift.jsx`)
- Interactive month/severity filter
- Charts: Error increase % per month (color-coded), drifted feature count stacked bar
- Full drift table: every test month with KS, PSI, Wasserstein, severity, error increase %

**3. Baseline Performance** (`Performance.jsx`)
- KPIs: R², MAE, RMSE, MAPE, WMAPE
- Charts: MAE trend with brush, error increase % with mild threshold reference line
- Metrics glossary: explains R², MAE, RMSE, MAPE, WMAPE, KS, PSI, Wasserstein, JS

### Group 2: Analysis

**4. Feature Importance** (`Features.jsx`)
- KPIs: total features (63), feature groups, top feature, top-20 coverage %, model accuracy
- Group filter pills: Lag, Rolling, Temporal, Product Stats, Interaction, Raw Inputs
- Charts: top-20 horizontal bar, feature group treemap, group importance bar, radial chart
- Per-group feature cards with click-to-inspect

**5. Forecasting** (`StoreStats.jsx`)
- KPIs: forecast accuracy, MAE, MAPE, product count, test months, best product
- Product filter pills: click to filter all charts
- Charts: monthly forecast vs test set (area+line), accuracy by product bar, MAE by product, radar
- Detail table: every product with avg demand, avg forecast, MAE, MAPE, accuracy, quality badge

**6. Predictions Explorer** (`Predictions.jsx`)
- Month selector: click any test month
- Product filter pills: cross-filter by product
- Charts: test set vs predicted with 95% CI band + brush (150 rows), product demand summary bar, monthly avg area, absolute error bar
- Detail table: 100 rows with test set, predicted, CI lower/upper, abs error, error %, quality badge
- Live: polls `/api/predictions-meta` every 12s, refreshes when file changes

**7. Demand Insights** (`Demand.jsx`)
- KPIs: avg weekly demand, growth rate, peak month, top product, total demand
- Product filter pills: click to see individual product monthly trend
- Charts: avg demand vs forecast bar, demand share pie (no legend — hover for details), monthly aggregation bar, normalized radar (Demand % + Accuracy %)
- Heatmap: Product × Month demand matrix with color intensity
- Key insights cards: demand trend, highest/lowest demand product, dataset stats
- Polls all endpoints every 120s

**8. Datasets** (`Datasets.jsx`)
- KPIs: train rows, test rows, cutoff date, stores, batches
- Reference dataset info: source, total records, date range, train/test split
- Drift severity summary: severe/mild/none counts
- Monitored batches table: every month with records, test set, predicted, MAE, error ratio, severity

### Group 3: Data

**9. Upload & Monitor** (`Upload.jsx`)
- Drag-and-drop or click to browse CSV
- Async pipeline progress with real-time status
- Expected CSV format table (required + optional columns)
- Post-pipeline: KPIs, metric comparison, MAE trend, error increase, drifted features, test set vs predicted

**10. Predict Cycle** (`Predict.jsx`)
- Status KPIs: data range, products, last data month, last prediction, status
- Visual 6-step workflow timeline
- Upload actuals: drag-and-drop CSV
- Comparison: MAE, MAPE, actual vs predicted bar chart
- Next prediction result: product-level prediction summary
- Accuracy history: MAE + MAPE trend across all uploaded months
- Saved predictions browser: browse all saved predictions with product-level bar chart

---

## Real-Time Data Flow

```
User uploads CSV → Pipeline runs (async, 600s timeout) → Results saved to logs/ and processed/
                                                                    ↓
                                                        Backend API reads from disk
                                                        Cache TTL: 30–600s per endpoint
                                                        Cache busted after every upload
                                                                    ↓
                                                        Frontend polls every 30–120s
                                                        Memory cache TTL: 60s
                                                        Stale-while-revalidate pattern
                                                                    ↓
                                                        All dashboards update automatically
```

- **Backend cache**: In-memory dict with TTL per endpoint; `_bust()` clears all caches after upload
- **Frontend cache**: `memCache` Map with 60s TTL; dedup fetch prevents duplicate in-flight requests
- **Polling**: `useFetch` hook with `pollMs` (30s for processed-months, 60s for monthly-sales, 120s for demand/forecast endpoints)
- **Predictions**: `usePredictions` hook polls `/api/predictions-meta` every 12s; only re-fetches when file mtime changes

---

## Current Pipeline Run Results

| Metric | Value |
|--------|-------|
| Dataset | Retail Sales Forecasting (2019–2023) |
| Source rows | 4,565,000 daily |
| Stores | 50 (`store_1`…`store_50`) |
| Products | 50 (`item_1`…`item_50`) |
| Store-Product combos | 2,500 |
| Features generated | 63–87+ |
| Model | Gradient Boosting |
| Training R² | ~1.0 (near-perfect fit) |
| Training MAPE | < 1% |
| Test Months | 12 (Year 2) |
| First Prediction | Year 3 Month 1 |
| Sequential Predictions | Ongoing monthly cycle |
