# SH-DFS Backend

FastAPI backend for the Self-Healing Demand Forecasting System.

## Dataset

**Retail Sales Forecasting Dataset** (`retail_sales.csv`)
- **4,565,000 rows** — 5 years daily (2019-01-01 to 2023-12-31)
- **50 stores** (`store_1`…`store_50`) × **50 products** (`item_1`…`item_50`) = 2,500 combinations
- Columns: `date`, `store_id`, `item_id`, `sales` (0–139), `price` (8.02–99.99), `promo` (0/1), `weekday` (0–6), `month` (1–12)
- No missing values; each store-product pair has exactly 1,826 daily rows
- Run `python generate_data.py retail_sales.csv` to convert to weekly pipeline format

## Structure

```
backend/
  api.py            ← FastAPI app (all endpoints)
  requirements.txt  ← minimal deps
  Dockerfile        ← production container
  .env.example      ← env vars template
```

The backend reads data from the **parent directory** (`../logs`, `../data`, `../processed`, `../uploads`).  
When deploying separately, mount those directories as volumes.

## Run Locally

```bash
cd backend

# 1. Create virtual environment
python -m venv venv
venv\Scripts\activate          # Windows
# source venv/bin/activate     # Mac/Linux

# 2. Install dependencies
pip install -r requirements.txt

# 3. Copy env file
copy .env.example .env

# 4. Start server
uvicorn api:app --reload --port 8000
```

API docs: http://localhost:8000/docs  
Health:   http://localhost:8000/api/health

## Run with Docker

```bash
cd backend

# Build
docker build -t shdfs-backend .

# Run — mount data directories from parent
docker run -p 8000:8000 \
  -v $(pwd)/../logs:/app/logs \
  -v $(pwd)/../data:/app/data \
  -v $(pwd)/../processed:/app/processed \
  -v $(pwd)/../uploads:/app/uploads \
  -v $(pwd)/../models:/app/models \
  shdfs-backend
```

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/health` | System health check |
| GET | `/api/summary` | Phase 1 summary + metrics |
| GET | `/api/baseline` | Baseline model metrics |
| GET | `/api/drift` | Drift history (deduped by month) |
| GET | `/api/batches` | Prediction batches |
| GET | `/api/training-log` | Training log |
| GET | `/api/data-split` | Train/test split info |
| GET | `/api/data-inspection` | Data inspection report |
| GET | `/api/processed-months` | List of processed months |
| GET | `/api/predictions/{month}` | Predictions for a month |
| GET | `/api/store-stats` | Per-store MAE aggregation |
| GET | `/api/monthly-sales` | Actual vs predicted per month |
| POST | `/api/upload-predict` | Upload CSV → run pipeline |

## Deploy to Railway / Render / Fly.io

Set environment variable:
```
CORS_ORIGINS=https://your-frontend.vercel.app
```

Start command:
```
uvicorn api:app --host 0.0.0.0 --port $PORT
```
