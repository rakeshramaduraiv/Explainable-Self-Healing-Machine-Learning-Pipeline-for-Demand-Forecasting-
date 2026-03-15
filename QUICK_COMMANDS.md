# Quick Command Reference

## Git Push

```bash
cd c:\Users\balan\OneDrive\Desktop\caps
git add .
git commit -m "Add fine-tuning system implementation"
git push
```

---

## Backend Setup

### Terminal 1: Setup & Run Pipeline
```bash
cd c:\Users\balan\OneDrive\Desktop\caps\backend
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
python main.py
```

### Terminal 2: Start API Server
```bash
cd c:\Users\balan\OneDrive\Desktop\caps\backend
venv\Scripts\activate
uvicorn api:app --reload --port 8000
```

### Terminal 3: Frontend (Optional)
```bash
cd c:\Users\balan\OneDrive\Desktop\caps\frontend
npm install
npm run dev
```

---

## Test Commands

### Check Health
```bash
curl http://localhost:8000/api/health
```

### Check Healing Actions (NEW)
```bash
curl http://localhost:8000/api/healing-actions
```

### Check Summary
```bash
curl http://localhost:8000/api/summary
```

### Check Drift History
```bash
curl http://localhost:8000/api/drift
```

### Check Feature Importances
```bash
curl http://localhost:8000/api/feature-importances
```

### Check Monthly Sales
```bash
curl http://localhost:8000/api/monthly-sales
```

### Check Store Stats
```bash
curl http://localhost:8000/api/store-stats
```

### Get Predictions for Month
```bash
curl http://localhost:8000/api/predictions/2012-03
```

### Upload New Data
```bash
curl -X POST -F "file=@data.csv" http://localhost:8000/api/upload-predict
```

---

## View Logs

### Real-time Logs
```bash
tail -f c:\Users\balan\OneDrive\Desktop\caps\backend\logs\system_*.log
```

### View Specific Log
```bash
type c:\Users\balan\OneDrive\Desktop\caps\backend\logs\system_20240313.log
```

---

## Access Dashboard

### Frontend
```
http://localhost:5173
```

### API Docs
```
http://localhost:8000/docs
```

### Health Check
```
http://localhost:8000/api/health
```

---

## One-Liner Quick Start

### Run Everything
```bash
cd c:\Users\balan\OneDrive\Desktop\caps\backend && python -m venv venv && venv\Scripts\activate && pip install -r requirements.txt && python main.py && uvicorn api:app --reload --port 8000
```

### Just Run Pipeline
```bash
cd c:\Users\balan\OneDrive\Desktop\caps\backend && venv\Scripts\activate && python main.py
```

### Just Start API
```bash
cd c:\Users\balan\OneDrive\Desktop\caps\backend && venv\Scripts\activate && uvicorn api:app --reload --port 8000
```

---

## Expected Output

### Pipeline Run
```
[INFO] ============================================================
[INFO] PHASE 1: SELF-HEALING DEMAND FORECASTING SYSTEM
[INFO] ============================================================
[INFO] [1/7] Loading data
[INFO] [2/7] Splitting data
[INFO] [3/7] Feature engineering
[INFO] [4/7] Training model
[INFO] [5/7] Simulating months
[INFO] 2012-02: SEVERE drift detected → Applying healing action
[INFO] Tier 3 (Retrain): Full model retraining on rolling window
[INFO] Retrain successful: MAE $67,394 → $58,200 (13.78% improvement)
[INFO] 2012-03: MILD drift detected → Applying healing action
[INFO] Tier 2 (Fine-tune): Warm start with additional trees
[INFO] Fine-tune successful: MAE $58,200 → $55,100 (5.32% improvement)
[INFO] [6/7] Generating summary
[INFO] Final Severity: SEVERE
[INFO] Healing Summary: {'total_actions': 12, 'monitor_only': 3, 'fine_tuned': 7, 'retrained': 1, 'rollbacks': 1}
[INFO] [7/7] Saving results
[INFO] PHASE 1 COMPLETE in 69s | Severity: SEVERE
```

### API Health Check
```json
{
  "status": "ok",
  "version": "2.0.0",
  "logs_exist": true,
  "model_exists": true,
  "ts": 1710345600.123
}
```

### Healing Actions
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

---

## Troubleshooting

### Port Already in Use
```bash
uvicorn api:app --reload --port 8001
```

### Module Not Found
```bash
pip install -r requirements.txt
```

### Data Not Found
```bash
# Place CSV in backend/data/uploaded_data.csv
# Or upload via API
curl -X POST -F "file=@data.csv" http://localhost:8000/api/upload-predict
```

### Model Not Found
```bash
# Run pipeline first
python main.py
```

---

## File Locations

```
c:\Users\balan\OneDrive\Desktop\caps\
├── backend/
│   ├── fine_tuner.py                    ← Fine-tuning logic
│   ├── pipeline.py                      ← Main pipeline
│   ├── api.py                           ← API server
│   ├── logs/                            ← Log files
│   ├── models/                          ← Trained models
│   ├── processed/                       ← Predictions
│   └── data/                            ← Input data
├── frontend/
│   ├── src/
│   └── package.json
└── SETUP_AND_DEPLOYMENT.md              ← This guide
```

---

## Summary

### Step 1: Git Push
```bash
git add .
git commit -m "Add fine-tuning system"
git push
```

### Step 2: Setup Backend
```bash
cd backend
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

### Step 3: Run Pipeline
```bash
python main.py
```

### Step 4: Start API
```bash
uvicorn api:app --reload --port 8000
```

### Step 5: Test
```bash
curl http://localhost:8000/api/healing-actions
```

### Step 6: Frontend (Optional)
```bash
cd frontend
npm install
npm run dev
```

**Done! System is running! 🎉**
