# SH-DFS — Platform Explanation for Staff

## What Is This System?

SH-DFS (Self-Healing Demand Forecasting System) is a machine learning platform that **predicts product demand** (how many units of each product will be sold next month). It has a **self-healing** capability — when the model detects that real-world data is drifting away from what it learned, it automatically fine-tunes itself.

---

## How It Works — Complete User Flow

### Step 1: User Uploads CSV (Upload & Monitor page)

The user uploads a CSV file with **2 years of data** containing **3 required columns**:

| Column | Type | Example | Required |
|--------|------|---------|----------|
| Date | DD-MM-YYYY | 05-01-2024 | ✅ Yes |
| Product | integer | 1, 2, 3... | ✅ Yes |
| Demand | integer (units) | 152 | ✅ Yes |

**Optional columns** (the system auto-detects them):
- Store, Holiday_Flag, Temperature, Fuel_Price, CPI, Unemployment
- Or ANY other numeric/text columns — the system treats them as features automatically

**If any of the 3 required columns are missing, the system rejects the file with a clear error message.**

The system also auto-renames common aliases:
- `sales` or `Weekly_Sales` → Demand
- `item` or `category` → Product
- `date` or `week` → Date

### Step 2: Pipeline Runs Automatically (8 Steps)

When the user clicks "Run Pipeline", the backend executes 8 steps:

```
Step 1: Load Data        → Read CSV, validate 3 required columns, auto-detect optional columns
Step 2: Split Data       → Year 1 = Training (e.g., 2024), Year 2 = Testing (e.g., 2025)
Step 3: Feature Eng.     → Generate 87 features from the user's 3-9 columns (see below)
Step 4: Train Model      → Train RF, GB, XGB models → pick best one (Gradient Boosting won)
Step 5: Simulate Months  → Test on Year 2 month-by-month, detect drift, apply self-healing
Step 6: Generate Summary → Calculate final metrics, healing stats
Step 7: Save Results     → Save model, logs, predictions
Step 8: First Prediction → Predict the first future month (e.g., 2026-01)
```

### Step 3: Monthly Prediction Cycle (Predict Cycle page)

After the pipeline completes:

```
Model predicts 2026-01 demand (75 rows: 15 products × ~5 weeks)
        ↓
User uploads ACTUAL January 2026 data (Date + Product + Demand)
        ↓
System compares predictions vs actuals (MAE, MAPE, RMSE)
        ↓
System auto-predicts 2026-02
        ↓
User uploads February actuals → System predicts March → Repeat forever
```

---

## Dynamic Feature Engineering — How 3 Columns Become 87 Features

The user uploads **3 columns**. The system **auto-generates 87 features** from them. The user never sees or touches these features — it all happens inside `feature_engineering.py`.

### Feature Breakdown (87 total with full dataset)

| Group | Count | Source | What It Does |
|-------|-------|--------|-------------|
| **Raw Inputs** | 5 | User's optional columns | Holiday_Flag, Temperature, Fuel_Price, CPI, Unemployment — used directly |
| **Temporal** | 17 | Extracted from Date | Year, Month, Week, Quarter, DayOfYear, sin/cos cycles, holiday proximity, season encoding |
| **Lag (Sliding Window)** | 9 | From Demand history | "What was demand 1, 2, 3, 4, 8, 12, 26, 52 weeks ago for this Product?" |
| **Rolling Stats** | 16 | From Demand history | Rolling Mean/Std/Max/Min over 4, 8, 12, 26 week windows |
| **Momentum/Volatility** | 4 | From Lag + Rolling | Momentum_4, Momentum_12, Volatility_4, Volatility_12 |
| **Store Stats** | 8 | If Store column exists | Store_Mean, Store_Median, Store_Std, Store_Max, Store_Min, Demand_vs_Store_Mean, etc. |
| **Product Stats** | 8 | From Product column | Product_Mean, Product_Median, Product_Std, etc. — per-product historical averages |
| **Known Interactions** | 10 | From known column pairs | Store×Holiday, Product×Holiday, Temp×Fuel, CPI×Unemployment, etc. |
| **Dynamic Pairwise** | 10 | Auto-generated | All numeric column pairs multiplied: Holiday_Flag×Temperature, Fuel_Price×CPI, etc. (up to 10 pairs) |

### What Happens With Different Uploads

| User Uploads | Features Generated |
|-------------|-------------------|
| Date + Product + Demand (3 cols) | ~48 features (temporal + lag + rolling + product stats) |
| Date + Product + Demand + Store (4 cols) | ~56 features (adds store stats) |
| All 9 columns | **87 features** (full feature set) |

### How Auto-Detection Works (data_loader.py → feature_engineering.py)

1. `data_loader.py` reads the CSV, checks for Date + Product + Demand
2. Scans all remaining columns:
   - Numeric columns with many unique values → `numeric_features` (Temperature, CPI, etc.)
   - Numeric columns with few unique values → `categorical_features` (Holiday_Flag)
   - Text columns with < 50 unique values → `categorical_features`
3. `feature_engineering.py` receives this info and:
   - **Always creates**: temporal (17) + lag (9) + rolling (16) + momentum (4) = 46 features
   - **If Product exists**: adds 8 product stats
   - **If Store exists**: adds 8 store stats
   - **If numeric columns exist**: creates up to 10 pairwise interactions + known interactions
   - **If categorical columns exist**: label-encodes them

---

## Auto-Fill for Future Predictions

When predicting a future month (e.g., 2026-01), the system doesn't have Temperature, CPI, etc. for that month yet.

**What happens in `sequential_predictor.py`:**

1. Gets the **last row** of all existing data (e.g., last week of December 2025)
2. Reads: Temperature=35.0, Fuel_Price=3.44, CPI=238.2, Unemployment=5.8
3. Creates **scaffold rows** for January 2026: 4 weeks × 15 products = 60 rows
4. Fills each scaffold row with those last-known values
5. Sets Demand = NaN (this is what the model will predict)
6. Runs feature engineering on the combined data (historical + scaffold)
7. The lag/rolling features use **real historical demand** — only optional columns use last-known values
8. Model predicts Demand for each scaffold row

---

## Self-Healing — How It Works

During Step 5 (Simulate Months), for each test month:

1. **Drift Detection** (`drift_detector.py`) — 5 statistical tests:
   - **KS Test** (Kolmogorov-Smirnov): Detects if feature distributions shifted
   - **PSI** (Population Stability Index): Measures magnitude of shift
   - **Wasserstein Distance**: Earth mover's distance between distributions
   - **JS Divergence** (Jensen-Shannon): Symmetric distribution difference
   - **Error Trend**: Tracks MAE increase over time

2. **Dynamic Thresholds**: High-importance features get stricter thresholds (0.7×), low-importance features get relaxed thresholds (1.3×)

3. **Healing Action** (`fine_tuner.py`):
   - **No drift**: Monitor only
   - **Mild/Severe drift**: Fine-tune model (add more trees to the ensemble)
   - If fine-tuning improves MAE by ≥5%: Keep the updated model
   - If improvement < 5%: **Rollback** to previous model

4. **Result from last pipeline run**: 12 months tested, 4 successful fine-tunes, 8 rollbacks, 4.18% average improvement

---

## Backend Technology Stack

| Component | Technology | File |
|-----------|-----------|------|
| **API Server** | FastAPI (Python) | `api.py` |
| **ML Models** | scikit-learn, XGBoost | `model_trainer.py` |
| **Model Selection** | RandomForest, GradientBoosting, XGBoost, Stacking Ensemble | `model_trainer.py` |
| **Hyperparameter Tuning** | RandomizedSearchCV with TimeSeriesSplit | `model_trainer.py` |
| **Feature Engineering** | pandas, numpy, sklearn LabelEncoder | `feature_engineering.py` |
| **Drift Detection** | scipy (KS test, Wasserstein, JS divergence) | `drift_detector.py` |
| **Self-Healing** | Custom fine-tuner with rollback | `fine_tuner.py` |
| **Data Loading** | pandas with alias auto-rename | `data_loader.py` |
| **Prediction Cycle** | Sequential monthly predictor | `sequential_predictor.py` |
| **Confidence Intervals** | Random Forest tree variance (95% CI) | `model_trainer.py` |
| **Caching** | In-memory cache with TTL (5-10s) | `api.py` |
| **Real-time Updates** | Cache busting after every upload/pipeline run | `api.py` |

### Model Training Details

- **Algorithms tested**: Random Forest, Gradient Boosting, XGBoost, Stacking (RF+GB+XGB→Ridge)
- **Winner**: Gradient Boosting (lowest MAE on training data)
- **Hyperparameter tuning**: 20 iterations of RandomizedSearchCV with TimeSeriesSplit cross-validation
- **Confidence intervals**: 95% CI from Random Forest tree variance (±1.96 × std of tree predictions)

---

## Frontend Technology Stack

| Component | Technology |
|-----------|-----------|
| **Framework** | React 18 with Vite |
| **Charts** | Recharts (bar, line, area, composed, radar, treemap, radial, pie) |
| **State Management** | React hooks (useState, useMemo, useCallback, useEffect) |
| **API Communication** | Custom fetch wrapper with dedup, caching, polling |
| **Real-time Updates** | 10-second memory cache TTL, 10-15s polling intervals |
| **Lazy Loading** | React.lazy + Suspense for all pages |
| **Styling** | CSS variables, responsive grid layout |

---

## UI Pages — What Each Dashboard Shows

### 1. Training Overview (`Overview.jsx`)
- **KPIs**: R², MAE, RMSE, MAPE, Accuracy, Severe Drift count — all **live from test set data**
- **Charts**: MAE trend (baseline vs test set), drifted features per month, test set vs predicted demand, monthly MAE
- **Self-Healing Actions**: Total actions, fine-tuned count, rollback count, avg improvement
- **System Summary**: Dataset info, date range, train/test split, model type, feature count

### 2. Drift Detection (`Drift.jsx`)
- **Interactive slicer**: Filter by month or severity
- **Charts**: Error increase % per month (color-coded by severity), drifted feature count (severe vs mild stacked)
- **Full drift table**: Every test month with severity, feature counts, baseline MAE, test MAE, error increase %

### 3. Baseline Performance (`Performance.jsx`)
- **KPIs**: R², MAE, RMSE, MAPE, WMAPE — live from test set
- **Charts**: MAE trend with brush control, error increase % with mild threshold line
- **Metrics Glossary**: Explains every metric (R², MAE, RMSE, MAPE, WMAPE, KS Test, PSI, Wasserstein, JS Divergence)
- **Confidence Intervals**: Coverage % and average width

### 4. Feature Importance (`Features.jsx`)
- **KPIs**: Total features (87), feature groups (6), top feature, top 20 coverage %, model accuracy
- **Group filter pills**: Click to filter by Lag, Rolling, Temporal, Product Stats, Interaction, Raw Inputs
- **Charts**: Top 20 features horizontal bar, feature group treemap, product accuracy vs features, group importance bar
- **Radial chart**: Top 10 features importance scale
- **Feature group cards**: Every feature listed with click-to-inspect

### 5. Product Demand Forecasting (`StoreStats.jsx`)
- **KPIs**: Forecast accuracy, MAE, MAPE, product count, test months, best product
- **Product filter pills**: Click any product to filter all charts
- **Charts**: Monthly forecast vs test set (area + line), accuracy by product (horizontal bar), accuracy by month, MAE by product, radar chart
- **Detail table**: Every product with avg demand, avg forecast, MAE, MAPE, accuracy, quality badge

### 6. Predictions Explorer (`Predictions.jsx`)
- **Month selector**: Click any test month to view predictions
- **Product filter pills**: Cross-filter by product
- **Charts**: Test set vs predicted with 95% confidence band + brush, product demand summary, monthly avg, absolute error per row
- **Detail table**: Every prediction row with test set, predicted, CI lower/upper, abs error, error %, quality badge
- **Live polling**: Auto-refreshes every 12 seconds

### 7. Demand Insights (`Demand.jsx`)
- **KPIs**: Avg weekly demand, growth rate, peak month, top product, total demand
- **Product filter**: Click to see individual product trends
- **Charts**: Weekly demand trend, demand vs forecast by product, demand share pie, monthly aggregation, radar profile
- **Heatmap table**: Product × Month demand matrix with color intensity

### 8. Datasets (`Datasets.jsx`)
- **KPIs**: Train rows, test rows, cutoff date, stores, batches
- **Reference dataset info**: Source, total records, date range, train/test split, missing values
- **Drift severity summary**: Severe/mild/none counts
- **Monitored batches table**: Every month with records, test set, predicted, MAE, error ratio, drift severity

### 9. Upload & Monitor (`Upload.jsx`)
- **Upload zone**: Drag-and-drop or click to browse CSV files
- **Pipeline progress**: Real-time progress bar during pipeline execution
- **Healing status**: Live display of self-healing actions during pipeline run
- **Expected CSV format table**: Shows required (Date, Product, Demand) and optional columns
- **Results tab**: After pipeline — KPIs, metric comparison table, MAE trend, error increase, drifted features, test set vs predicted

### 10. Predict Cycle (`Predict.jsx`)
- **Status KPIs**: Data range, products, last data month, last prediction, status
- **Workflow timeline**: Visual 6-step timeline (Train → Test → Predict → Upload Actuals → Compare → Repeat)
- **Upload section**: Drag-and-drop for monthly actuals CSV
- **Comparison section**: After upload — MAE, MAPE, actual vs predicted bar chart
- **Next prediction result**: Product-level prediction summary
- **Accuracy history**: MAE + MAPE trend across all uploaded months
- **Saved predictions browser**: Browse all saved predictions with product-level bar chart

---

## Real-Time Data Flow

```
User uploads CSV → Pipeline runs → Results saved to logs/ and processed/
                                            ↓
                                    Backend API reads from disk
                                    Cache TTL: 5-10 seconds
                                    Cache busted after every upload
                                            ↓
                                    Frontend polls every 10-15 seconds
                                    Memory cache TTL: 10 seconds
                                    Stale-while-revalidate pattern
                                            ↓
                                    All dashboards update automatically
```

- **Backend cache**: In-memory dict with TTL per endpoint (5-10s for real-time data, 60-300s for static data)
- **Frontend cache**: `memCache` Map with 10s TTL, dedup fetch to prevent duplicate requests
- **Polling**: `useFetch` hook with configurable `pollMs` (10s for drift/monthly, 15s for summary, 60s for datasets)
- **Cache bust**: `_bust()` clears all backend caches immediately after upload or pipeline run

---

## Dataset Source

The system uses a **dynamic feature engineering approach** — it accepts ANY CSV with Date + Product + Demand. Compatible public datasets:

- **Store Item Demand Forecasting**: https://www.kaggle.com/competitions/demand-forecasting-kernels-only
  - 5 years, 50 items, 10 stores, ~913K rows
  - Columns: date, store, item, sales → auto-renames to Date, Store, Product, Demand

- **Walmart Dataset**: https://www.kaggle.com/datasets/yasserh/walmart-dataset
  - Store, Date, Weekly_Sales, Holiday_Flag, Temperature, Fuel_Price, CPI, Unemployment
  - Would need Product column added

The current demo uses synthetic data generated by `generate_data.py` (15 product categories, 1,560 rows, 2 years).

---

## Last Pipeline Run Results

| Metric | Value |
|--------|-------|
| Model | Gradient Boosting |
| Features | 87 |
| Training R² | 100% |
| Training MAE | 0 units |
| Test Months | 12 |
| Fine-Tunes | 4 successful |
| Rollbacks | 8 |
| Avg Improvement | 4.18% |
| First Prediction | 2026-01 (75 rows, 15 products) |
