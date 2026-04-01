# Architecture & Workflow — Sales Forecasting System

## System Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│                        FORECASTING SYSTEM                          │
│                                                                     │
│  ┌──────────────┐    HTTP/REST     ┌──────────────────────────┐    │
│  │   Frontend    │ ◄──────────────► │       Backend            │    │
│  │  React + Vite │   /api/*        │  FastAPI + LightGBM      │    │
│  │  Port: 5173   │                 │  Port: 8000              │    │
│  └──────────────┘                  └──────────────────────────┘    │
│                                              │                      │
│                                    ┌─────────┴──────────┐          │
│                                    │    Data Layer       │          │
│                                    │  data/raw/train.csv │          │
│                                    │  data/uploads/*.csv │          │
│                                    │  models/            │          │
│                                    └────────────────────┘          │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Startup Flow

```
start_light.py
     │
     ├── [Thread 1] Start Backend (backend_minimal.py)
     │        │
     │        ├── Load train.csv (9,800 orders, 2015-01 to 2018-12)
     │        ├── aggregate_daily()        → Daily rows per Category×Region
     │        ├── engineer_features()      → 27 features (7R + 9A + 11E)
     │        ├── do_train()               → LightGBM (200 trees, depth 8)
     │        ├── build_product_cache()    → Precompute all 1,861 products
     │        ├── make_prediction()        → Predict January 2019
     │        └── Uvicorn server on :8000
     │
     ├── [Thread 2] Start Frontend (npm run dev)
     │        └── Vite dev server on :5173
     │
     └── Open browser → http://localhost:5173
```

---

## Data Flow — Training Pipeline

```
                        train.csv (9,800 orders)
                               │
                               ▼
                    ┌─────────────────────┐
                    │   aggregate_daily()  │
                    │                     │
                    │  Group by:          │
                    │  Date × Category    │
                    │       × Region      │
                    │                     │
                    │  Compute per group: │
                    │  • sales (sum)      │
                    │  • order_count      │
                    │  • avg_order_value  │
                    │  • ship_speed       │
                    │  • segment_encoded  │
                    │  • shipping_days    │
                    │  • subcat_avg_sales │
                    └────────┬────────────┘
                             │
                             ▼
                    ┌─────────────────────┐
                    │ engineer_features() │
                    │                     │
                    │  RAW (7):           │
                    │  dayofweek, month,  │
                    │  year, order_count, │
                    │  avg_order_value,   │
                    │  ship_speed,        │
                    │  segment_encoded    │
                    │                     │
                    │  AGGREGATED (9):    │
                    │  lag_1/7/14/28,     │
                    │  rmean_3/7/14/28,   │
                    │  rstd_7             │
                    │                     │
                    │  ENGINEERED (11):   │
                    │  sales_momentum,    │
                    │  sales_volatility,  │
                    │  region_strength,   │
                    │  category_popularity│
                    │  relative_demand,   │
                    │  weekly_pattern,    │
                    │  trend_slope,       │
                    │  subcat_avg_sales,  │
                    │  shipping_days,     │
                    │  sales_acceleration,│
                    │  weekend_flag       │
                    └────────┬────────────┘
                             │
                             ▼
                    ┌─────────────────────┐
                    │     do_train()      │
                    │                     │
                    │  80/20 split        │
                    │  LightGBM:          │
                    │  • 200 trees        │
                    │  • lr = 0.05        │
                    │  • depth = 8        │
                    │  • 31 leaves        │
                    │                     │
                    │  Output:            │
                    │  • MODEL            │
                    │  • METRICS (MAE,    │
                    │    RMSE, MAPE)      │
                    │  • IMPORTANCE       │
                    └────────┬────────────┘
                             │
                             ▼
                    ┌─────────────────────┐
                    │ make_prediction()   │
                    │                     │
                    │  Last 30 days per   │
                    │  Category×Region    │
                    │       │             │
                    │       ▼             │
                    │  Model.predict()    │
                    │       │             │
                    │       ▼             │
                    │  Aggregate:         │
                    │  • Total predicted  │
                    │  • Daily chart      │
                    │  • By category      │
                    │  • By region        │
                    │       │             │
                    │       ▼             │
                    │  Per-product:       │
                    │  Distribute using   │
                    │  historical sales   │
                    │  share from         │
                    │  PRODUCT_CACHE      │
                    └─────────────────────┘
```

---

## Self-Healing Pipeline — Monthly Cycle

```
 ┌──────────────────────────────────────────────────────────────────┐
 │                    SELF-HEALING PIPELINE                         │
 │                                                                  │
 │   STEP 1              STEP 2              STEP 3                │
 │  ┌──────────┐       ┌──────────┐       ┌──────────────┐        │
 │  │ PREDICT  │──────►│ UPLOAD   │──────►│ DRIFT CHECK  │        │
 │  │ Next     │       │ Actual   │       │              │        │
 │  │ Month    │       │ Data     │       │ KS + PSI + JS│        │
 │  └──────────┘       └──────────┘       └──────┬───────┘        │
 │                                                │                │
 │                                    ┌───────────┼───────────┐    │
 │                                    │           │           │    │
 │                                    ▼           ▼           ▼    │
 │                               ┌────────┐ ┌─────────┐ ┌───────┐ │
 │                    STEP 4     │  LOW   │ │ MEDIUM  │ │ HIGH  │ │
 │                               │Monitor │ │Fine-Tune│ │Retrain│ │
 │                               └───┬────┘ └────┬────┘ └───┬───┘ │
 │                                   │           │           │     │
 │                                   └─────┬─────┘───────────┘     │
 │                                         │                       │
 │                                         ▼                       │
 │                    STEP 5        ┌──────────────┐               │
 │                                  │ PREDICT NEXT │               │
 │                                  │    MONTH     │──── Loop ───► │
 │                                  └──────────────┘               │
 └──────────────────────────────────────────────────────────────────┘
```

### Step-by-Step Detail

```
STEP 1: Predict Next Month
│   POST /api/predict
│   └── make_prediction(MODEL, FEATURED_DF, NEXT_MONTH)
│       └── Returns: total $, daily chart, by category, by region, per-product
│
STEP 2: Upload Actual Data
│   POST /api/upload
│   ├── Read uploaded CSV
│   ├── Evaluate: compare predicted vs actual sales
│   │   └── accuracy_pct = (1 - |actual - predicted| / actual) × 100
│   ├── Append to TRAIN_DF
│   ├── Rebuild PRODUCT_CACHE
│   ├── Re-engineer features
│   └── Auto-predict next month
│
STEP 3: Drift Detection (Dynamic Thresholding)
│   POST /api/drift
│   ├── Split FEATURED_DF using PRE_UPLOAD_FEATURED_DF snapshot vs appended data
│   ├── For ALL 27 features:
│   │   ├── KS Test (distribution shape)
│   │   ├── PSI (population stability)
│   │   └── JS Divergence (symmetric divergence)
│   │   └── Feature drift = max(KS, PSI_norm, JS)
│   ├── Voting logic: severity based on % of features with high drift
│   ├── Threshold Decision:
│   │   ├── Run 1-4 (insufficient history): Static → med=0.1, high=0.2
│   │   └── Run 5+ (has history): Dynamic → med=μ+0.5σ, high=μ+1.5σ (clamped)
│   ├── Check prediction error increase vs ORIGINAL_BASELINE_MAE
│   └── Decide action based on drift OR accuracy drop
│
STEP 4: Model Update & Rollback Validation
│   ├── LOW  → Monitor (no action)
│   ├── MEDIUM → POST /api/retrain/finetune
│   │   ├── Smart window: 9 months (with fallback to 12m, 18m if needed)
│   │   └── Deploy if >5% improvement vs current MAE
│   └── HIGH → POST /api/retrain/sliding (with 30-day cooldown)
│       ├── Smart window: 36 months
│       └── Deploy if >5% improvement vs current MAE (else Rollback)
│
STEP 5: Predict Next Month → Back to Step 1
```

---

## Dynamic Drift Thresholding — Detail

```
                    ┌─────────────────────────────┐
                    │      27 Monitored Features  │
                    │                             │
                    │  • Lags (1, 7, 14, 28)      │
                    │  • Rolling means/stds       │
                    │  • Engineered signals       │
                    │  • Raw temporal/categorical │
                    │                             │
                    └──────────┬──────────────────┘
                               │
                    ┌──────────▼──────────────────┐
                    │   Per-Feature Max Score     │
                    │                             │
                    │  ┌─────┐ ┌─────┐ ┌──────┐  │
                    │  │ KS  │ │ PSI │ │  JS  │  │
                    │  │Test │ │     │ │Diver.│  │
                    │  └──┬──┘ └──┬──┘ └──┬───┘  │
                    │     └───────┼───────┘       │
                    │             ▼               │
                    │     Composite Score         │
                    │  (per feature, 0 to 1)      │
                    └──────────┬──────────────────┘
                               │
                    ┌──────────▼──────────────────┐
                    │  Average Composite Score     │
                    │  (across all 5 features)     │
                    └──────────┬──────────────────┘
                               │
              ┌────────────────┼────────────────┐
              ▼                                 ▼
    ┌──────────────────┐              ┌──────────────────┐
    │  RUN 1 (Static)  │              │  RUN 2+ (Dynamic)│
    │                  │              │                  │
    │  No history yet  │              │  From past runs: │
    │  med ≥ 0.1       │              │  μ = mean(past)  │
    │  high ≥ 0.2      │              │  σ = std(past)   │
    │                  │              │  med ≥ μ + 1σ    │
    │                  │              │  high ≥ μ + 2σ   │
    └──────────────────┘              └──────────────────┘
              │                                 │
              └────────────┬────────────────────┘
                           ▼
                  ┌─────────────────┐
                  │  Drift Level    │
                  │                 │
                  │  < med  → LOW   │
                  │  < high → MED   │
                  │  ≥ high → HIGH  │
                  └─────────────────┘
```

---

## Product Prediction — Distribution Model

```
    Model predicts at Category × Region level (12 combos)
    Products get predictions via historical sales share

    ┌──────────────────────────────────────────────────┐
    │  Category × Region Prediction                    │
    │  e.g. Technology × West = $15,000                │
    └──────────────────┬───────────────────────────────┘
                       │
         ┌─────────────┼─────────────┐
         ▼             ▼             ▼
    ┌─────────┐  ┌─────────┐  ┌─────────┐
    │Product A│  │Product B│  │Product C│
    │share=40%│  │share=35%│  │share=25%│
    │= $6,000 │  │= $5,250 │  │= $3,750 │
    └─────────┘  └─────────┘  └─────────┘

    Orders: Uses avg_monthly_orders from product history
    (not distributed — uses actual historical average)
```

---

## Product Cache — Precomputed at Startup & Upload

```
    build_product_cache(TRAIN_DF)
              │
              ├── product_list: 1,861 names sorted by order count (desc)
              │
              ├── product_details: per product
              │   ├── category, sub_category
              │   ├── total_orders, total_sales
              │   ├── avg_monthly_orders
              │   ├── regions: {region: order_count}
              │   └── segments: {segment: order_count}
              │
              ├── product_monthly: per product
              │   └── All 48 months (2015-01 to 2018-12), 0-filled
              │
              └── product_shares: per product
                  └── [(category, region, sales_share), ...]
```

---

## Frontend Architecture

```
    App.jsx
     │
     ├── Navbar.jsx ─────────── Navigation + model status indicator
     │
     ├── Dashboard.jsx ──────── Product slicer + 7 chart cards
     │   ├── Product Filter (1,861 products, sorted by orders)
     │   ├── Model Info KPIs
     │   ├── Monthly Sales Trend (LineChart — filtered: orders, all: $)
     │   ├── Regional Demand (BarChart — filtered: per-product, all: overview)
     │   ├── Customer Segments (PieChart — filtered only)
     │   ├── Category Demand (BarChart — all products only)
     │   ├── Top 10 Products (horizontal BarChart — all only)
     │   ├── Demand Prediction (LineChart — filtered: orders, all: $)
     │   └── Feature Importance (horizontal BarChart — top 10)
     │
     ├── PipelinePage ───────── 5-step self-healing pipeline UI
     │   (embedded in App.jsx)
     │   ├── Step 1: Predict
     │   ├── Step 2: Upload
     │   ├── Step 3: Drift
     │   ├── Step 4: Update
     │   └── Step 5: Next cycle
     │
     ├── Analytics.jsx ──────── Real-time model performance
     │   ├── Current Model State
     │   ├── Performance Metrics (MAE, RMSE, MAPE)
     │   ├── Feature Importance (all 27, horizontal BarChart)
     │   ├── Feature Details Table
     │   └── Model Insights + Error Segments
     │
     ├── FeatureExtractionSlide.jsx ── How 27 features are built
     │   ├── Summary KPIs
     │   ├── Type Distribution (PieChart)
     │   ├── Real-time Feature Importance (BarChart)
     │   ├── Expandable feature cards (27)
     │   └── Pipeline Flow diagram
     │
     ├── XAISlide.jsx ───────── Explainable AI
     │   ├── Why This Prediction (top 5 features BarChart)
     │   ├── Drift Analysis (KS + PSI + JS, dynamic thresholds)
     │   │   ├── Composite score + threshold method
     │   │   ├── Per-feature: KS, PSI, JS, composite, severity
     │   │   └── Threshold explanation (static vs dynamic)
     │   ├── Full Feature Importance (all 27)
     │   └── Current Model Performance
     │
     └── Logbook.jsx ────────── Audit trail
         ├── Summary KPIs (cycles, actions)
         ├── MAE Over Time (LineChart)
         ├── Drift Score Over Time (LineChart)
         ├── Action Timeline (BarChart)
         └── Expandable log entries with drift details
```

---

## API Endpoints

```
    GET  /api/health              → { status, model }
    GET  /api/status              → { dataset, prediction, product_cache, features }
    GET  /api/metrics             → { mae, rmse, mape, top_error_skus }
    GET  /api/feature-importance  → { features: [{feature, importance, type}] }
    GET  /api/logbook             → { entries: [...] }
    GET  /api/system-log          → { log, current_action }
    GET  /api/predict/download    → CSV file (StreamingResponse)

    POST /api/predict             → Full prediction for next month
    POST /api/upload              → Upload actual data + evaluate + update
    POST /api/drift               → Multi-test drift detection (KS+PSI+JS)
    POST /api/retrain/finetune    → Fine-tune on recent 60% data
    POST /api/retrain/sliding     → Full retrain on all data
    POST /api/xai/store-explanation → Store XAI explanation
```

---

## File Structure

```
    forecasting/
    │
    ├── start_light.py              # Launcher (backend + frontend threads)
    ├── backend_minimal.py          # FastAPI server + ML pipeline + all logic
    ├── generate_monthly_uploads.py # Generate 12 monthly test CSVs
    ├── requirements.txt            # Python deps
    ├── ARCHITECTURE.md             # This file
    │
    ├── data/
    │   ├── raw/train.csv           # Superstore dataset (9,800 orders)
    │   └── uploads/                # Monthly upload files (Jan-Dec 2019)
    │
    ├── models/                     # Trained model storage
    │
    └── frontend/
        ├── package.json            # React 18, Recharts, Axios
        ├── vite.config.js          # Dev server :5173, proxy /api → :8000
        └── src/
            ├── App.jsx             # Router + PipelinePage
            ├── api.js              # Axios API client (12 endpoints)
            └── components/
                ├── Navbar.jsx              # Navigation bar
                ├── Dashboard.jsx           # Main dashboard + product slicer
                ├── Analytics.jsx           # Model analytics
                ├── FeatureExtractionSlide.jsx # Feature documentation
                ├── XAISlide.jsx            # Explainable AI + drift
                └── Logbook.jsx             # Audit trail
```

---

## Technology Stack

```
    ┌─────────────┬──────────────────────────────────────┐
    │ Layer       │ Technology                           │
    ├─────────────┼──────────────────────────────────────┤
    │ Frontend    │ React 18 + Vite 4 + Recharts 3.8    │
    │ HTTP Client │ Axios                                │
    │ Backend     │ FastAPI + Uvicorn                    │
    │ ML Model    │ LightGBM (gradient boosting)         │
    │ Stats       │ SciPy (KS test, JS divergence)       │
    │ Data        │ Pandas + NumPy                       │
    │ Metrics     │ Scikit-learn (MAE, RMSE)             │
    │ Dataset     │ Superstore Sales CSV                 │
    │ Runtime     │ Python 3.x + Node.js                 │
    └─────────────┴──────────────────────────────────────┘
```

---

## Key Design Decisions

1. **Category×Region granularity**: Model trains at Category×Region level (3×4=12 combos), not per-product — avoids sparse data for 1,861 products
2. **Product predictions via share distribution**: Per-product sales derived by multiplying Category×Region prediction by product's historical sales share
3. **Product orders via historical average**: Uses actual avg_monthly_orders, not distributed order counts (avoids rounding to 0)
4. **Dynamic drift thresholds**: First run uses static cutoffs; subsequent runs adapt using μ±σ from drift history
5. **Composite drift score**: Combines KS (shape), PSI (stability), JS (divergence) — more robust than any single test
6. **Precomputed product cache**: All 1,861 products precomputed at startup and on upload — keeps /api/status fast
7. **In-memory state**: All data (TRAIN_DF, MODEL, METRICS, PRODUCT_CACHE, DRIFT_HISTORY) lives in memory — no database needed for demo
