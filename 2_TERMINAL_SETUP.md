# 2-Terminal Setup - Backend (Python) + Frontend (React)

## 🎯 Goal: Run Everything in 2 Terminals

```
Terminal 1: Backend (Python FastAPI)
Terminal 2: Frontend (React Vite)
```

---

## ✅ Prerequisites

### Check Python
```bash
python --version
# Should be 3.8+
```

### Check Node.js
```bash
node --version
npm --version
# Should be 14+ and 6+
```

---

## 🚀 Terminal 1: Backend (Python)

### Step 1: Setup (First time only)
```bash
cd c:\Users\balan\OneDrive\Desktop\caps\backend
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

### Step 2: Run Pipeline (First time only)
```bash
python main.py
```

**Expected Output:**
```
[INFO] PHASE 1: SELF-HEALING DEMAND FORECASTING SYSTEM
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

### Step 3: Start API Server (Keep running)
```bash
venv\Scripts\activate
uvicorn api:app --reload --port 8000
```

**Expected Output:**
```
INFO:     Uvicorn running on http://127.0.0.1:8000
INFO:     Application startup complete
```

**Keep this terminal open!**

---

## 🎨 Terminal 2: Frontend (React)

### Step 1: Setup (First time only)
```bash
cd c:\Users\balan\OneDrive\Desktop\caps\frontend
npm install
```

### Step 2: Run Development Server (Keep running)
```bash
npm run dev
```

**Expected Output:**
```
  VITE v4.x.x  ready in xxx ms

  ➜  Local:   http://localhost:5173/
  ➜  press h to show help
```

**Keep this terminal open!**

---

## 🌐 Access the Application

### Backend API
```
http://localhost:8000
```

### API Documentation
```
http://localhost:8000/docs
```

### Frontend Dashboard
```
http://localhost:5173
```

---

## 📊 Test the System

### In a 3rd Terminal (Optional)

#### Check Health
```bash
curl http://localhost:8000/api/health
```

#### Check Healing Actions
```bash
curl http://localhost:8000/api/healing-actions
```

#### Check Summary
```bash
curl http://localhost:8000/api/summary
```

#### Check Drift
```bash
curl http://localhost:8000/api/drift
```

---

## 🔄 Workflow

### First Time Setup (10 minutes)
```bash
# Terminal 1
cd c:\Users\balan\OneDrive\Desktop\caps\backend
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
python main.py
# Wait for pipeline to complete
uvicorn api:app --reload --port 8000
# Keep running

# Terminal 2
cd c:\Users\balan\OneDrive\Desktop\caps\frontend
npm install
npm run dev
# Keep running
```

### Subsequent Times (2 minutes)
```bash
# Terminal 1
cd c:\Users\balan\OneDrive\Desktop\caps\backend
venv\Scripts\activate
uvicorn api:app --reload --port 8000
# Keep running

# Terminal 2
cd c:\Users\balan\OneDrive\Desktop\caps\frontend
npm run dev
# Keep running
```

---

## 📋 Quick Reference

### Terminal 1: Backend
```bash
cd c:\Users\balan\OneDrive\Desktop\caps\backend
venv\Scripts\activate
uvicorn api:app --reload --port 8000
```

### Terminal 2: Frontend
```bash
cd c:\Users\balan\OneDrive\Desktop\caps\frontend
npm run dev
```

### Access
- Backend: http://localhost:8000
- Frontend: http://localhost:5173
- Docs: http://localhost:8000/docs

---

## 🎯 What Each Terminal Does

### Terminal 1: Backend (Python)
- Runs FastAPI server on port 8000
- Serves API endpoints
- Handles drift detection
- Manages fine-tuning
- Stores data in SQLite
- Logs all actions

### Terminal 2: Frontend (React)
- Runs Vite dev server on port 5173
- Serves React dashboard
- Displays 7 pages with charts
- Calls backend API
- Shows healing statistics
- Real-time updates

---

## 🔗 How They Communicate

```
Frontend (React)
    ↓
http://localhost:5173
    ↓
Calls API endpoints
    ↓
http://localhost:8000/api/*
    ↓
Backend (Python)
    ↓
Returns JSON data
    ↓
Frontend displays charts
```

---

## 📊 Dashboard Pages

1. **Overview** - Error trend, drifted features, monthly sales
2. **Drift Analysis** - Error increase, feature count, history
3. **Model Performance** - MAE trend, error percentage
4. **Feature Importance** - Top-20 features, group cards
5. **Store Analytics** - MAE by store, scatter plot, tables
6. **Predictions** - Actual vs predicted, error bar, data table
7. **Upload & Monitor** - Upload form, drift results, MAE trend

---

## 🛠️ Troubleshooting

### Backend Issues

#### Port 8000 already in use
```bash
# Use different port
uvicorn api:app --reload --port 8001
```

#### Module not found
```bash
# Reinstall dependencies
pip install -r requirements.txt --force-reinstall
```

#### Model not found
```bash
# Run pipeline first
python main.py
```

### Frontend Issues

#### Port 5173 already in use
```bash
# Vite will automatically use next available port
npm run dev
```

#### Dependencies not installed
```bash
# Reinstall
npm install
```

#### API not responding
```bash
# Check if backend is running
curl http://localhost:8000/api/health
```

---

## 📁 File Structure

```
caps/
├── backend/
│   ├── venv/                    ← Virtual environment
│   ├── fine_tuner.py            ← Fine-tuning logic
│   ├── pipeline.py              ← Main pipeline
│   ├── api.py                   ← FastAPI server
│   ├── requirements.txt          ← Python dependencies
│   ├── logs/                    ← Log files
│   ├── models/                  ← Trained models
│   ├── processed/               ← Predictions
│   └── data/                    ← Input data
├── frontend/
│   ├── node_modules/            ← Node dependencies
│   ├── src/
│   │   ├── pages/               ← React pages
│   │   ├── api.js               ← API client
│   │   ├── App.jsx              ← Main app
│   │   └── main.jsx             ← Entry point
│   ├── package.json             ← Node dependencies
│   ├── vite.config.js           ← Vite config
│   └── index.html               ← HTML template
└── README.md
```

---

## 🚀 Start Now!

### Copy & Paste Commands

#### Terminal 1: Backend
```bash
cd c:\Users\balan\OneDrive\Desktop\caps\backend
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
python main.py
# Wait for completion, then:
uvicorn api:app --reload --port 8000
```

#### Terminal 2: Frontend
```bash
cd c:\Users\balan\OneDrive\Desktop\caps\frontend
npm install
npm run dev
```

#### Then Open Browser
```
http://localhost:5173
```

---

## ✅ Success Indicators

### Backend Running
```
INFO:     Uvicorn running on http://127.0.0.1:8000
INFO:     Application startup complete
```

### Frontend Running
```
  ➜  Local:   http://localhost:5173/
```

### Both Connected
- Dashboard loads
- Charts display data
- No console errors
- API calls work

---

## 📊 Example Output

### Terminal 1 (Backend)
```
INFO:     Uvicorn running on http://127.0.0.1:8000
INFO:     Application startup complete
INFO:     127.0.0.1:54321 - "GET /api/health HTTP/1.1" 200 OK
INFO:     127.0.0.1:54322 - "GET /api/healing-actions HTTP/1.1" 200 OK
INFO:     127.0.0.1:54323 - "GET /api/summary HTTP/1.1" 200 OK
```

### Terminal 2 (Frontend)
```
  VITE v4.3.9  ready in 234 ms

  ➜  Local:   http://localhost:5173/
  ➜  press h to show help
```

### Browser
```
Dashboard loads with:
- Overview page
- 7 navigation tabs
- Real-time charts
- Healing statistics
- Drift analysis
```

---

## 🎉 You're Ready!

Just open 2 terminals and run:

**Terminal 1:**
```bash
cd c:\Users\balan\OneDrive\Desktop\caps\backend
venv\Scripts\activate
uvicorn api:app --reload --port 8000
```

**Terminal 2:**
```bash
cd c:\Users\balan\OneDrive\Desktop\caps\frontend
npm run dev
```

**Then open:** http://localhost:5173

---

## 📞 Quick Help

| Issue | Solution |
|-------|----------|
| Backend won't start | Check if port 8000 is free |
| Frontend won't start | Check if Node.js is installed |
| API not responding | Check if backend is running |
| Dashboard blank | Check browser console for errors |
| Port already in use | Use different port number |

---

## 🎯 Next Steps

1. ✅ Open Terminal 1
2. ✅ Run backend commands
3. ✅ Open Terminal 2
4. ✅ Run frontend commands
5. ✅ Open browser to http://localhost:5173
6. ✅ Explore dashboard

**That's it! 🚀**
