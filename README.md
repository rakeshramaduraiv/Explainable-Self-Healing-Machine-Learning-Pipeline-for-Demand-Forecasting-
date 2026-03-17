# SH-DFS — Self-Healing Product Demand Forecasting System

ML platform that predicts **product demand (units)** using self-healing capabilities with dynamic feature engineering.

## Dataset

**Store Item Demand Forecasting Dataset** (Kaggle)
- **URL:** https://www.kaggle.com/datasets/dhrubangtalukdar/store-item-demand-forecasting-dataset
- 5 years of daily sales data (2013–2017), 50 items, 10 stores
- Columns: `date`, `store`, `item`, `sales`
- ~913,000 rows → converted to weekly product demand (~1,560 rows for 2 years, 15 products)

The system auto-renames: `sales`→Demand, `item`→Product, `store`→Store, `date`→Date.

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
# 1. Download train.csv from Kaggle (link above) into backend/
cd backend

# 2. Convert Kaggle data → pipeline format
python generate_data.py train.csv

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
| `Product` | int | Product identifier (1, 2, 3...) |
| `Demand` | int | **Target: units demanded per product** |

### Optional Columns (auto-detected as features)

| Column | Type | Description |
|--------|------|-------------|
| `Store` | int | Store identifier |
| `Holiday_Flag` | int | 1 if holiday week, 0 otherwise |
| `Temperature` | float | Regional temperature |
| `Fuel_Price` | float | Regional fuel price |
| `CPI` | float | Consumer Price Index |
| `Unemployment` | float | Regional unemployment rate |
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
| Interactions | 10+ | Dynamic pairwise from numeric columns |
| Momentum/Volatility | 4 | Always |

**Minimum input:** Date + Product + Demand → 40+ features generated

## What the Model Predicts

**Input:** Product, Date, historical demand patterns, engineered features

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
├── generate_data.py          # Kaggle dataset converter (or synthetic fallback)
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
