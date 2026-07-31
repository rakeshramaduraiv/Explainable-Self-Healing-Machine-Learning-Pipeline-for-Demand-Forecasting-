# PROJECT REPORT: Explainable Self-Healing Demand Forecasting System

---

## 1. DATASET

### Source
- **File**: `data/raw/train.csv` (Superstore Sales Dataset)
- **Records**: 9,800 orders
- **Period**: January 3, 2015 to December 30, 2018 (4 years)
- **Format**: CSV with 18 columns

### Columns Used
| Column | Type | Role |
|--------|------|------|
| Order Date | datetime | Time index |
| Ship Date | datetime | Shipping speed calculation |
| Ship Mode | categorical | Urgency indicator |
| Segment | categorical | Customer type |
| Category | categorical | Product category (3: Furniture, Office Supplies, Technology) |
| Sub-Category | categorical | Product sub-type (17 types) |
| Region | categorical | Geographic area (4: South, West, Central, East) |
| Product Name | categorical | Individual product (1,849 unique) |
| Sales | numeric | Target variable (revenue per order) |
| Order ID | categorical | Unique order identifier |
| Customer ID | categorical | Customer identifier |
| State | categorical | US state |

### Data Characteristics
- **3 Categories**: Furniture, Office Supplies, Technology
- **4 Regions**: South, West, Central, East
- **3 Segments**: Consumer, Corporate, Home Office
- **4 Ship Modes**: Same Day, First Class, Second Class, Standard Class
- **Monthly avg**: ~204 orders, ~$47,115 sales
- **Seasonality**: Nov-Dec are peak months ($83K-$118K), Jan is lowest ($14K-$43K)

---

## 2. DATA CLEANING & PREPROCESSING

### Step 1: Date Parsing
```python
pd.read_csv(DATA_PATH, parse_dates=["Order Date"], dayfirst=True)
```
- Parses dates in DD/MM/YYYY format
- Ship Date parsed separately with `errors="coerce"` to handle malformed dates

### Step 2: Categorical Encoding
| Original | Encoded | Why |
|----------|---------|-----|
| Ship Mode → ship_speed | Same Day=4, First=3, Second=2, Standard=1 | Ordinal: urgency level |
| Segment → segment_encoded | Consumer=0, Corporate=1, Home Office=2 | Ordinal: business type |

### Step 3: Derived Column
```python
shipping_days = (Ship Date - Order Date).days.clip(lower=0)
```
- Measures fulfillment speed
- Clipped to 0 minimum (no negative days)

### Step 4: Daily Aggregation
Raw orders are grouped by **Date × Category × Region** to create daily time series:
```python
groupby([Date, Category, Region]).agg(
    sales = sum(Sales),
    order_count = nunique(Order ID),
    avg_order_value = mean(Sales),
    ship_speed = mean(ship_speed),
    segment_encoded = mean(segment_encoded),
    shipping_days = mean(shipping_days),
    subcategory_avg_sales = median(Sales)
)
```
- **Why daily?** Time-series model needs regular intervals
- **Why Category×Region?** 12 groups (3×4) capture different demand patterns
- **Result**: ~5,110 daily rows (not all days have orders in all CR groups)

---

## 3. FEATURE ENGINEERING (27 Features)

### Raw Features (7) — Direct from data
| Feature | Source | Purpose |
|---------|--------|---------|
| dayofweek | Order Date | Weekend vs weekday patterns (0=Mon, 6=Sun) |
| month | Order Date | Seasonal patterns (1-12) |
| year | Order Date | Long-term growth trend (2015-2018) |
| order_count | Order ID | Daily demand volume |
| avg_order_value | Sales | Buying behavior indicator |
| ship_speed | Ship Mode | Urgency of orders |
| segment_encoded | Segment | Customer type mix |

### Aggregated Features (9) — From sales history
| Feature | Formula | Purpose |
|---------|---------|---------|
| lag_1 | sales shifted 1 day | Yesterday's sales (immediate momentum) |
| lag_7 | sales shifted 7 days | Same day last week (weekly cycle) |
| lag_14 | sales shifted 14 days | Bi-weekly pattern |
| lag_28 | sales shifted 28 days | Same day last month |
| rmean_3 | rolling mean 3 days | Very short-term trend |
| rmean_7 | rolling mean 7 days | Short-term trend |
| rmean_14 | rolling mean 14 days | Medium-term trend |
| rmean_28 | rolling mean 28 days | Long-term baseline |
| rstd_7 | rolling std 7 days | Sales volatility |

### Engineered Features (11) — Derived combinations
| Feature | Formula | Purpose |
|---------|---------|---------|
| sales_momentum | rmean_7 - rmean_28 | Trend direction (+rising, -falling) |
| sales_volatility | rstd_7 / (rmean_7 + 1) | Demand predictability |
| region_strength | expanding mean by Region | Regional demand level |
| category_popularity | expanding mean by Category | Category demand level |
| relative_demand | sales / (region_strength + 1) | Above/below regional norm |
| weekly_pattern | expanding mean by dayofweek | Recurring weekly behavior |
| trend_slope | polyfit slope of last 7 days | Linear trend direction |
| subcategory_avg_sales | median Sales per day | Product-level context |
| shipping_days | mean fulfillment time | Urgency correlation |
| sales_acceleration | momentum change over 7 days | Is trend speeding up? |
| weekend_flag | dayofweek >= 5 | Binary weekend indicator |

### Key Design Decisions
1. **Expanding means** (not global transform) for region_strength, category_popularity, weekly_pattern — prevents future data leakage
2. **No gap-filling** — zero-filled days inflate dataset with artificial zeros, causing 425% MAPE
3. **All features computed per Category×Region group** — each group has its own lag/rolling history

---

## 4. MODEL

### Algorithm: LightGBM (Light Gradient Boosting Machine)

### Why LightGBM?
- Handles tabular data excellently
- Fast training (200 trees in ~2 seconds)
- Handles missing values natively
- Feature importance built-in
- Works well with mixed feature types (numeric + encoded categorical)

### Hyperparameters
| Parameter | Value | Why |
|-----------|-------|-----|
| n_estimators | 200 | Enough trees for complex patterns without overfitting |
| learning_rate | 0.05 | Slow learning for better generalization |
| max_depth | 8 | Deep enough for feature interactions |
| num_leaves | 31 | Controls tree complexity |

### Training Split
- **80% train / 20% validation** (time-ordered, no shuffle)
- Validation on the most recent 20% of data (simulates future prediction)

### Metrics
| Metric | Value | Meaning |
|--------|-------|---------|
| MAE | $27.92 | Average prediction error per daily CR group |
| RMSE | $177.19 | Penalizes large errors more |
| MAPE | 15.9% | Percentage error relative to actual |

---

## 5. PREDICTION ENGINE

### Method: Recursive Day-by-Day Forecasting

### How It Works
```
For each Category×Region group:
  1. Take the last known day's features as starting point
  2. For each future day (Jan 1, Jan 2, ... Jan 31):
     a. Set dayofweek, month, year, weekend_flag for this date
     b. Use previous day's PREDICTED value as lag_1
     c. Update rmean_3/7/14/28 from rolling buffer of predictions
     d. Recompute sales_momentum, trend_slope, sales_acceleration
     e. Predict this day's sales using the model
     f. Append prediction to buffer → next day uses it
```

### Why Recursive?
- **Without recursive**: Same features every day → same prediction → flat line
- **With recursive**: Each day's prediction changes the next day's features → realistic daily variation

### Historical Calibration
Raw recursive predictions are scaled to match the historical average for the target month:
```python
scale = historical_avg_for_this_month / raw_prediction_total
```
- January historical avg: ~$23K → prediction calibrated to ~$23K
- Prevents over/under-prediction from lag feature inflation

### Per-Product Predictions
- Model predicts at **Category×Region level** (12 groups)
- Individual product predictions derived by **proportional allocation**:
  ```
  product_daily_sales = CR_daily_prediction × product_sales_share
  ```
- Product's share = its historical sales / total CR sales

---

## 6. SELF-HEALING PIPELINE

### Design Philosophy
```
Train ONCE on 2015-2018 → Predict month-by-month
→ Only retrain when HIGH drift → Use 24-month sliding window
```

### Pipeline Flow
```
TRAIN (2015-2018, one-time)
     ↓
PREDICT January 2019
     ↓
USER UPLOADS actual January data
     ↓
EVALUATE: predicted vs actual (accuracy %)
     ↓
DRIFT CHECK (KS + PSI + JS on 27 features)
     ├── LOW → Monitor (no retrain, model stays same)
     ├── MEDIUM → Monitor (no retrain)
     └── HIGH → Retrain (24-month sliding window)
     ↓
PREDICT February 2019
     ↓
REPEAT
```

### Key Rules
1. **Upload stores data but does NOT retrain** — dataset grows, model stays same
2. **Retrain only on HIGH drift** — controlled adaptation, not constant retraining
3. **Sliding window = last 24 months** — drops old patterns, focuses on recent
4. **Rollback if new model is worse** — only deploy if >5% MAE improvement

---

## 7. DRIFT DETECTION

### What It Detects
Whether the newly uploaded data has shifted from what the model was trained on.

### Statistical Tests (per feature)
| Test | What It Measures | Range |
|------|-----------------|-------|
| KS Test (Kolmogorov-Smirnov) | Distribution shape change | 0-1 |
| PSI (Population Stability Index) | Population shift | 0-∞ (normalized to 0-1) |
| JS Divergence (Jensen-Shannon) | Symmetric divergence | 0-1 |

### Composite Score
```python
per_feature_composite = max(KS, JS, PSI/0.25)
```
- Uses **max** (not weighted average) to avoid diluting strong signals

### Overall Drift Score (Voting-Based)
```python
if >20% features are HIGH (>0.25): drift_score = max(all scores) [severe]
elif >40% features are MED+HIGH:   drift_score = average(all scores) [mild]
else:                               drift_score = average(all scores) [none]
```

### Features Monitored
All 27 model features are checked for drift (not just input features).

### Decision Engine
```python
if drift_score >= HIGH_threshold OR prediction_error >= 50%:
    → RETRAIN (sliding window)
elif drift_score >= MED_threshold OR prediction_error >= 30%:
    → FINE-TUNE
else:
    → MONITOR (do nothing)
```

### Dynamic Thresholds
- **First 5 runs**: Static (medium=0.1, high=0.2)
- **After 5 runs**: Dynamic from rolling history
  ```
  medium = μ + 0.5σ (clamped to 0.05-0.25)
  high   = μ + 1.5σ (clamped to 0.15-0.35)
  ```

### Concept Drift (Prediction Accuracy)
- `LAST_PREDICTION_ERROR` = |actual - predicted| / actual
- Used in decision: if prediction is >50% off → force retrain regardless of feature drift

### Retrain Cooldown
- Minimum 30 days between forced retrains
- Prevents thrashing from noisy data

---

## 8. SLIDING WINDOW RETRAIN

### Window Size: 24 months (date-based)
```python
cutoff = max_date - 24 months
window_df = FEATURED_DF[date >= cutoff]
```

### Validation Before Deploy
```python
if new_model_MAE is >5% better than current_MAE:
    → Deploy new model ✅
    → Save old model to history (max 5 versions)
else:
    → Rollback ❌ (keep current model)
    → Log the rejection
```

### Emergency Rollback
- `/api/rollback` endpoint restores previous model version
- Up to 5 historical versions stored

---

## 9. PRODUCT CACHE

### Purpose
Pre-compute all per-product data at startup so the dashboard loads instantly.

### What's Cached
| Key | Content | Size |
|-----|---------|------|
| product_list | All 1,849 product names sorted by order count | 1,849 items |
| product_details | Category, sub-cat, total orders, total sales, avg monthly orders, regions, segments | per product |
| product_monthly | Orders per month for all 48 months (zero-filled) | per product |
| product_shares | Sales share per Category×Region for proportional allocation | per product |

### When Rebuilt
- At startup
- After each upload (new data changes shares)

---

## 10. TECHNOLOGY STACK

| Layer | Technology | Role |
|-------|-----------|------|
| **ML Model** | LightGBM | Gradient boosting for tabular time-series |
| **Backend** | FastAPI + Uvicorn | REST API server (async, fast) |
| **Data** | Pandas + NumPy | Data manipulation and feature engineering |
| **Statistics** | SciPy | KS test, JS divergence for drift detection |
| **Metrics** | Scikit-learn | MAE, RMSE calculation |
| **Frontend** | React 18 + Vite | Interactive dashboard UI |
| **Charts** | Recharts | Line, bar, pie charts |
| **HTTP** | Axios | API client |
| **Runtime** | Python 3.x + Node.js | Backend + frontend servers |

---

## 11. API ENDPOINTS

| Method | Endpoint | Purpose |
|--------|----------|---------|
| GET | /api/health | Server status check |
| GET | /api/status | Full system state (dataset, model, prediction, caches) |
| GET | /api/metrics | MAE, RMSE, MAPE, top error segments |
| GET | /api/feature-importance | 27 features ranked by importance |
| POST | /api/predict | Return current month's prediction |
| POST | /api/upload | Upload actual data, evaluate, store |
| POST | /api/drift | Run drift detection (KS+PSI+JS) |
| POST | /api/retrain/sliding | Retrain with 24-month sliding window |
| POST | /api/retrain/finetune | Fine-tune with 9-month window |
| POST | /api/rollback | Emergency rollback to previous model |
| GET | /api/logbook | Audit trail of all drift/retrain actions |
| GET | /api/product/{name} | Per-product details and monthly history |
| GET | /api/system-log | Real-time system activity log |
| GET | /api/predict/download | Download predictions as CSV |

---

## 12. FRONTEND PAGES

| Page | Purpose |
|------|---------|
| **Dashboard** | Product slicer, monthly trends, regional/category charts, prediction chart, feature importance |
| **Pipeline** | 5-step self-healing flow: Predict → Upload → Evaluate → Drift → Retrain |
| **Analytics** | Real-time model performance, error segments, feature details |
| **How Features Work** | Interactive explanation of all 27 features |
| **XAI** | Explainable AI: why predictions are made, why drift happens |
| **Logbook** | Complete audit trail with charts (MAE over time, drift history) |

---

## 13. KEY DESIGN DECISIONS & WHY

| Decision | Why |
|----------|-----|
| Category×Region granularity (not product-level) | 1,849 products would have sparse data; 12 CR groups have enough history |
| Expanding means (not global) | Prevents future data leakage in training |
| No gap-filling | Zero-filled days inflate dataset, cause 425% MAPE |
| Recursive forecasting | Static features → flat prediction line; recursive → realistic variation |
| Historical calibration | Raw predictions inflated by lag features from high-sales periods |
| Max-based composite drift | Average dilutes strong signals from individual features |
| OR-based decision logic | Either high drift OR high prediction error should trigger retrain |
| 24-month sliding window | Recent enough to capture trends, long enough for seasonality |
| >5% improvement threshold | Prevents deploying marginally better models that might be noise |
| Proportional product allocation | Practical alternative to training 1,849 individual models |

---

## 14. SYSTEM FLOW SUMMARY

```
┌─────────────────────────────────────────────────────────────┐
│                    STARTUP (ONE-TIME)                        │
│                                                             │
│  train.csv → aggregate_daily() → engineer_features(27)      │
│           → do_train(LightGBM) → make_prediction(Jan 2019)  │
│           → build_product_cache(1,849 products)             │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│                    MONTHLY CYCLE                             │
│                                                             │
│  1. PREDICT next month (recursive day-by-day)               │
│  2. USER UPLOADS actual data                                │
│  3. EVALUATE: predicted vs actual → accuracy %              │
│  4. DRIFT CHECK: KS+PSI+JS on 27 features                  │
│     ├── LOW/MEDIUM → Monitor (keep model)                   │
│     └── HIGH → Retrain (24-month sliding window)            │
│              ├── Better → Deploy new model                  │
│              └── Worse → Rollback (keep old)                │
│  5. PREDICT next month → REPEAT                             │
└─────────────────────────────────────────────────────────────┘
```

---

## 15. METRICS & PERFORMANCE

| Metric | Baseline (2015-2018) | After Retrain |
|--------|---------------------|---------------|
| MAE | $27.92 | Varies (must be >5% better to deploy) |
| MAPE | 15.9% | — |
| RMSE | $177.19 | — |
| Accuracy | 84.1% | — |
| Products | 1,849 | — |
| Features | 27 | — |
| Training time | ~2 seconds | — |
| Prediction time | ~7 seconds (recursive, 31 days × 12 groups) | — |

---

## 16. EXPLAINABILITY (XAI)

The system explains:
1. **Why this prediction** — Top 5 features driving the forecast with importance scores
2. **Why drift happened** — Which features shifted, by how much, and what it means
3. **Why this action** — Decision logic: drift score + accuracy drop → monitor/retrain
4. **Audit trail** — Every drift check, retrain, rollback logged with timestamps and reasoning
