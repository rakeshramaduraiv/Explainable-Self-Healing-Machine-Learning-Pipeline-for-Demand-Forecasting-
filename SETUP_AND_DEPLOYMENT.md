# Setup & Deployment Guide

## Step 1: Git Push

### Initialize Git (if not already done)
```bash
cd c:\Users\balan\OneDrive\Desktop\caps
git init
git add .
git commit -m "Add fine-tuning system implementation"
git remote add origin <your-repo-url>
git push -u origin main
```

### Or if already initialized
```bash
cd c:\Users\balan\OneDrive\Desktop\caps
git add .
git commit -m "Add fine-tuning system implementation"
git push
```

---

## Step 2: Setup Backend

### 2.1 Create Virtual Environment
```bash
cd backend
python -m venv venv
venv\Scripts\activate
```

### 2.2 Install Dependencies
```bash
pip install -r requirements.txt
```

### 2.3 Verify Installation
```bash
python -c "import pandas; import sklearn; import fastapi; print('All dependencies installed!')"
```

---

## Step 3: Run Pipeline

### 3.1 Prepare Data
Place your CSV file in `backend/data/uploaded_data.csv` or use the existing Walmart data.

### 3.2 Run Pipeline
```bash
cd backend
python main.py
```

**Expected Output:**
```
[INFO] ============================================================
[INFO] PHASE 1: SELF-HEALING DEMAND FORECASTING SYSTEM
[INFO] ============================================================
[INFO] [1/7] Loading data
[INFO] [1/7] Loading data done in 2s
[INFO] [2/7] Splitting data
[INFO] [2/7] Splitting data done in 1s
[INFO] [3/7] Feature engineering
[INFO] [3/7] Feature engineering done in 3s
[INFO] [4/7] Training model
[INFO] [4/7] Training model done in 15s
[INFO] [5/7] Simulating months
[INFO] 2012-02: SEVERE drift detected → Applying healing action
[INFO] Tier 3 (Retrain): Full model retraining on rolling window
[INFO] Retrain successful: MAE $67,394 → $58,200 (13.78% improvement)
[INFO] Healing action: RETRAIN | Improvement: 13.78%
[INFO] 2012-03: MILD drift detected → Applying healing action
[INFO] Tier 2 (Fine-tune): Warm start with additional trees
[INFO] Fine-tune successful: MAE $58,200 → $55,100 (5.32% improvement)
[INFO] Healing action: FINE_TUNE | Improvement: 5.32%
[INFO] [5/7] Simulating months done in 45s
[INFO] [6/7] Generating summary
[INFO] Final Severity: SEVERE | Severe drift detected: Healing actions applied
[INFO] Healing Summary: {'total_actions': 12, 'monitor_only': 3, 'fine_tuned': 7, 'retrained': 1, 'rollbacks': 1}
[INFO] [6/7] Generating summary done in 2s
[INFO] [7/7] Saving results
[INFO] [7/7] Saving results done in 1s
[INFO] PHASE 1 COMPLETE in 69s | Severity: SEVERE
```

---

## Step 4: Start Backend API

### 4.1 Run FastAPI Server
```bash
cd backend
uvicorn api:app --reload --port 8000
```

**Expected Output:**
```
INFO:     Uvicorn running on http://127.0.0.1:8000
INFO:     Application startup complete
```

### 4.2 Verify API is Running
```bash
curl http://localhost:8000/api/health
```

**Expected Response:**
```json
{
  "status": "ok",
  "version": "2.0.0",
  "logs_exist": true,
  "model_exists": true,
  "ts": 1710345600.123
}
```

---

## Step 5: Test Fine-Tuning System

### 5.1 Check Healing Actions
```bash
curl http://localhost:8000/api/healing-actions
```

**Expected Response:**
```json
{
  "total_actions": 12,
  "monitor_only": 3,
  "fine_tuned": 7,
  "retrained": 1,
  "rollbacks": 1,
  "avg_improvement": 0.0648,
  "recommendation": "Severe drift detected: Healing actions applied"
}
```

### 5.2 Check Summary
```bash
curl http://localhost:8000/api/summary
```

**Expected Response:**
```json
{
  "timestamp": "2024-03-13T10:45:23.123456",
  "final_severity": "severe",
  "recommendation": "Severe drift detected: Healing actions applied",
  "months_monitored": 21,
  "severity_counts": {
    "severe": 8,
    "mild": 10,
    "none": 3
  },
  "healing_stats": {
    "total_actions": 12,
    "monitor_only": 3,
    "fine_tuned": 7,
    "retrained": 1,
    "rollbacks": 1
  },
  "avg_improvement": 0.0648,
  "train_metrics": {
    "train": {
      "RMSE": 35901,
      "MAE": 24363,
      "R2": 0.9957,
      "MAPE": 2.81,
      "WMAPE": 2.37,
      "model": "RF"
    }
  }
}
```

### 5.3 Check Drift History
```bash
curl http://localhost:8000/api/drift
```

### 5.4 Check Feature Importances
```bash
curl http://localhost:8000/api/feature-importances
```

---

## Step 6: Start Frontend (Optional)

### 6.1 Install Dependencies
```bash
cd frontend
npm install
```

### 6.2 Run Development Server
```bash
npm run dev
```

**Expected Output:**
```
  VITE v4.x.x  ready in xxx ms

  ➜  Local:   http://localhost:5173/
  ➜  press h to show help
```

### 6.3 Access Dashboard
Open browser: http://localhost:5173

---

## Complete Workflow

### Terminal 1: Backend API
```bash
cd backend
venv\Scripts\activate
uvicorn api:app --reload --port 8000
```

### Terminal 2: Frontend (Optional)
```bash
cd frontend
npm run dev
```

### Terminal 3: Run Pipeline
```bash
cd backend
venv\Scripts\activate
python main.py
```

---

## Upload New Data

### Via API
```bash
curl -X POST -F "file=@your_data.csv" http://localhost:8000/api/upload-predict
```

### Expected Response
```json
{
  "status": "ok",
  "stdout": "[INFO] PHASE 1 COMPLETE in 69s | Severity: SEVERE"
}
```

---

## View Logs

### Real-time Logs
```bash
tail -f backend/logs/system_*.log
```

### View Specific Log
```bash
type backend\logs\system_20240313.log
```

---

## API Endpoints

### Health Check
```bash
curl http://localhost:8000/api/health
```

### Healing Actions (NEW)
```bash
curl http://localhost:8000/api/healing-actions
```

### Summary
```bash
curl http://localhost:8000/api/summary
```

### Drift History
```bash
curl http://localhost:8000/api/drift
```

### Feature Importances
```bash
curl http://localhost:8000/api/feature-importances
```

### Monthly Sales
```bash
curl http://localhost:8000/api/monthly-sales
```

### Store Stats
```bash
curl http://localhost:8000/api/store-stats
```

### Predictions for Month
```bash
curl http://localhost:8000/api/predictions/2012-03
```

### Upload & Predict
```bash
curl -X POST -F "file=@data.csv" http://localhost:8000/api/upload-predict
```

---

## Troubleshooting

### Issue: Module not found
**Solution:**
```bash
pip install -r requirements.txt
```

### Issue: Port 8000 already in use
**Solution:**
```bash
uvicorn api:app --reload --port 8001
```

### Issue: Data file not found
**Solution:**
```bash
# Place CSV in backend/data/uploaded_data.csv
# Or upload via API
curl -X POST -F "file=@data.csv" http://localhost:8000/api/upload-predict
```

### Issue: Model not found
**Solution:**
```bash
# Run pipeline first
python main.py
```

### Issue: Fine-tuning not working
**Solution:**
```bash
# Check logs
tail -f backend/logs/system_*.log

# Verify drift was detected
curl http://localhost:8000/api/drift

# Check healing actions
curl http://localhost:8000/api/healing-actions
```

---

## Performance Tips

### 1. Use Caching
All GET endpoints are cached (20-60 seconds)

### 2. Batch Uploads
Upload data once, then query results multiple times

### 3. Monitor Logs
```bash
tail -f backend/logs/system_*.log
```

### 4. Check API Docs
```
http://localhost:8000/docs
```

---

## Production Deployment

### Docker
```bash
cd backend
docker build -t shdfs-backend .
docker run -p 8000:8000 \
  -v $(pwd)/../logs:/app/logs \
  -v $(pwd)/../data:/app/data \
  -v $(pwd)/../processed:/app/processed \
  -v $(pwd)/../uploads:/app/uploads \
  shdfs-backend
```

### Railway/Render/Fly.io
```bash
# Set environment variable
CORS_ORIGINS=https://your-frontend.vercel.app

# Start command
uvicorn api:app --host 0.0.0.0 --port $PORT
```

---

## Summary

### Quick Start (5 minutes)
```bash
# 1. Activate venv
cd backend
venv\Scripts\activate

# 2. Run pipeline
python main.py

# 3. Start API
uvicorn api:app --reload --port 8000

# 4. Test in another terminal
curl http://localhost:8000/api/healing-actions
```

### Full Setup (15 minutes)
```bash
# 1. Backend
cd backend
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
python main.py
uvicorn api:app --reload --port 8000

# 2. Frontend (in another terminal)
cd frontend
npm install
npm run dev

# 3. Access dashboard
# http://localhost:5173
```

---

## Next Steps

1. ✅ Git push
2. ✅ Setup backend
3. ✅ Run pipeline
4. ✅ Start API
5. ✅ Test endpoints
6. ✅ Start frontend (optional)
7. ✅ Access dashboard

**System is ready to use! 🎉**
