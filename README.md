# Sales Forecasting System

Explainable Self-Healing Demand Forecasting Pipeline using LightGBM.

## Dataset
- **Source**: Superstore Sales (train.csv)
- **Records**: 9,800 orders
- **Period**: 2015-01-03 to 2018-12-30
- **Categories**: Furniture, Office Supplies, Technology
- **Regions**: South, West, Central, East

## Features (19 total)

| Type | Count | Features |
|------|-------|----------|
| Raw | 5 | dayofweek, month, year, order_count, avg_order_value |
| Aggregated | 7 | lag_1, lag_7, lag_28, rmean_7, rmean_14, rmean_28, rstd_7 |
| Engineered | 7 | sales_momentum, sales_volatility, region_strength, category_popularity, relative_demand, weekly_pattern, trend_slope |

## Run

```bash
cd forecasting
venv\Scripts\python start_light.py
```

Or separately:
```bash
# Terminal 1 - Backend
venv\Scripts\python backend_minimal.py

# Terminal 2 - Frontend
cd frontend
npm run dev
```

## Access
- Frontend: http://localhost:5173
- Backend API: http://localhost:8000
- API Docs: http://localhost:8000/docs

## Project Structure
```
forecasting/
├── backend_minimal.py          # FastAPI backend + ML pipeline
├── start_light.py              # Start script
├── generate_monthly_uploads.py # Generate 12 monthly test files
├── requirements.txt            # Python dependencies
├── data/
│   ├── raw/train.csv           # Superstore dataset
│   └── uploads/                # 12 monthly upload files
├── frontend/
│   ├── src/
│   │   ├── App.jsx             # Main app + pipeline UI
│   │   ├── api.js              # API client
│   │   └── components/
│   │       ├── Dashboard.jsx           # Overview dashboard
│   │       ├── Analytics.jsx           # Model analytics
│   │       ├── FeatureImportance.jsx   # Feature analysis
│   │       ├── FeatureExtractionSlide.jsx # How features work
│   │       ├── XAISlide.jsx            # Explainable drift analysis
│   │       ├── Logbook.jsx             # Action history
│   │       ├── SystemLog.jsx           # Real-time logs
│   │       └── Navbar.jsx              # Navigation
│   └── vite.config.js
└── models/                     # Trained model storage
```

## Pipeline
```
train.csv → Feature Engineering (19 features) → LightGBM (200 trees)
                    ↓                                    ↓
              Drift Detection (KS Test)           Predict Next Month
                    ↓
              Decision Engine
              ├─ Low  → Monitor
              ├─ Med  → Fine-Tune
              └─ High → Retrain
                    ↓
              XAI Explanation → Logbook
```
