# SH-DFS — Self-Healing Product Demand Forecasting System

ML platform that predicts **product demand (units)** using self-healing capabilities with dynamic feature engineering.

## Dataset

**Retail Sales Forecasting Dataset** (`retail_sales.csv`)
- **4,565,000 rows** of daily sales data — 5 years (2019-01-01 to 2023-12-31)
- **50 stores** (`store_1` … `store_50`) × **50 products** (`item_1` … `item_50`) = **2,500 unique store-product combinations**
- Each combination has exactly **1,826 daily rows** (365 days × 5 years)
- **No missing values** across all 8 columns

| Column | Type | Range / Values | Description |
|--------|------|----------------|-------------|
| `date` | str | 2019-01-01 → 2023-12-31 | Daily date (YYYY-MM-DD) |
| `store_id` | str | `store_1` … `store_50` | Store identifier |
| `item_id` | str | `item_1` … `item_50` | Product identifier |
| `sales` | int | 0 – 139 (mean: 29.3) | Units sold per day |
| `price` | float | 8.02 – 99.99 (mean: 54.0) | Item price |
| `promo` | int | 0 or 1 | Promotion flag (10% of rows are promo=1) |
| `weekday` | int | 0 (Mon) – 6 (Sun) | Day of week |
| `month` | int | 1 – 12 | Month number |

### Key Dataset Insights

| Insight | Value |
|---------|-------|
| Promo effect | Avg sales **41.9** (promo=1) vs **27.9** (promo=0) — **+50% uplift** |
| Peak weekday | Tuesday & Wednesday (avg ~35 units) |
| Lowest weekday | Saturday (avg ~24 units) |
| Peak month | March–April (avg ~37 units) |
| Lowest month | September–October (avg ~21 units) |
| Promo rate | 10% of all rows have active promotion |

The system auto-renames: `sales`→Demand, `item_id`→Product, `store_id`→Store, `date`→Date.

Raw daily data is aggregated to **weekly product demand** via `generate_data.py` before entering the pipeline.

## System Flow

```
┌─────────────────────────────────────────────────────────────────┐
│  YEAR 1 (12 months) → TRAINING                                  │
│  Train ML model on historical demand data                       │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│  YEAR 2 (12 months) → TESTING + SELF-HEALING                    │
│  Detect drift → Auto fine-tune model                            │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│  ONGOING → MONTHLY PREDICTION CYCLE                             │
│  Predict Month N+1 → User uploads actuals → Compare → Repeat    │
└─────────────────────────────────────────────────────────────────┘
```

## Quick Start

```bash
# 1. Place retail_sales.csv into backend/
cd backend

# 2. Convert retail_sales.csv → pipeline format
python generate_data.py retail_sales.csv

# 3. Run the ML pipeline
pip install -r requirements.txt
python main.py

# 4. Start backend API
uvicorn api:app --reload --port 8000

# 5. Start frontend (new terminal)
cd frontend
npm install
npm run dev

# 6. Open http://localhost:5173 → Dashboard ready
```

## Data Format

### Required Columns (3)

| Column | Type | Description |
|--------|------|-------------|
| `Date` | str | Week date (DD-MM-YYYY) |
| `Product` | str/int | Product identifier (`item_1` … `item_50`) |
| `Demand` | int | **Target: units demanded per product per week** |

### Optional Columns (auto-detected as features)

| Column | Type | Description |
|--------|------|-------------|
| `Store` | str/int | Store identifier (`store_1` … `store_50`) |
| `Price` | float | Item price (8.02–99.99) |
| `Promo` | int | 1 if promotion active, 0 otherwise |
| `Weekday` | int | Day of week (0–6) |
| `Month` | int | Month number (1–12) |
| *Any other columns* | numeric/text | Auto-detected as features |

## Dynamic Feature Engineering

The system auto-generates **40–87+ features** from any dataset:

| Feature Group | Count | Source |
|---------------|-------|--------|
| Temporal | 18 | Always (from Date) |
| Lag (sliding window) | 9 | Always (from Demand history) |
| Rolling stats | 18 | Always (mean/std/max/min windows) |
| Product stats | 8 | If Product column exists |
| Store stats | 8 | If Store column exists |
| Interactions | 10+ | Dynamic pairwise from numeric columns (Price × Promo, etc.) |
| Momentum/Volatility | 4 | Always |

**Minimum input:** Date + Product + Demand → 40+ features generated

## What the Model Predicts

**Input:** Product, Date, Price, Promo, historical demand patterns, engineered features

**Output:** `Predicted_Demand` — number of units expected to be demanded for each Product in the next month

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/seq/status` | GET | Current prediction cycle status |
| `/api/seq/predict-next` | POST | Predict next month's demand |
| `/api/seq/upload-actuals` | POST | Upload actual demand → compare → predict next |
| `/api/predictions/{month}` | GET | Get predictions for a month |
| `/api/detected-columns` | GET | What columns the system detected |
| `/api/product-names` | GET | Product IDs from uploaded data |

## Project Structure

```
backend/
├── retail_sales.csv          # Source dataset (4.56M rows, 50 stores × 50 items, 5 years)
├── generate_data.py          # retail_sales.csv converter → weekly pipeline format
├── data_loader.py            # Dynamic CSV loader (Date+Product+Demand required)
├── pipeline.py               # 8-step ML pipeline
├── feature_engineering.py    # Dynamic feature engine (40-87+ features)
├── model_trainer.py          # RF/GB/XGB ensemble
├── drift_detector.py         # Detect data drift (KS, PSI, Wasserstein, JS, Error Trend)
├── fine_tuner.py             # Self-healing logic
├── sequential_predictor.py   # Monthly prediction cycle
├── api.py                    # FastAPI endpoints
└── data/uploaded_data.csv    # Input data

frontend/
├── src/App.jsx               # Main app with 10 dashboard pages
├── src/api.js                # API client with caching
├── src/pages/                # Overview, Drift, Performance, Features, etc.
└── package.json              # React + Recharts + Vite
```
