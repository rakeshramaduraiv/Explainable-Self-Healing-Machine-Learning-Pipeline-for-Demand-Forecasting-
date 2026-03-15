# 2-Terminal Setup - Visual Guide

## 🎯 The Setup

```
┌──────────────────────────────────────────────────────────────────┐
│                                                                  │
│                    YOUR DEVELOPMENT SETUP                       │
│                                                                  │
├──────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌─────────────────────────┐      ┌─────────────────────────┐  │
│  │   TERMINAL 1            │      │   TERMINAL 2            │  │
│  │   Backend (Python)      │      │   Frontend (React)      │  │
│  ├─────────────────────────┤      ├─────────────────────────┤  │
│  │                         │      │                         │  │
│  │  $ cd backend           │      │  $ cd frontend          │  │
│  │  $ venv\Scripts\activate│      │  $ npm run dev          │  │
│  │  $ uvicorn api:app      │      │                         │  │
│  │                         │      │  ➜ http://localhost:5173│  │
│  │  ➜ http://localhost:8000       │                         │  │
│  │                         │      │  Keep running!          │  │
│  │  Keep running!          │      │                         │  │
│  │                         │      │                         │  │
│  └─────────────────────────┘      └─────────────────────────┘  │
│           ↓                                ↓                    │
│      FastAPI Server                  React Dashboard            │
│      Port 8000                        Port 5173                 │
│      API Endpoints                    7 Pages                   │
│      Drift Detection                  Real-time Charts          │
│      Fine-tuning                      Healing Stats             │
│                                                                  │
└──────────────────────────────────────────────────────────────────┘
                              ↓
                    ┌─────────────────────┐
                    │   Browser           │
                    │ localhost:5173      │
                    │                     │
                    │  Dashboard loads    │
                    │  Charts display     │
                    │  Data updates       │
                    └─────────────────────┘
```

---

## 📋 Step-by-Step Instructions

### Step 1: Open Terminal 1 (Backend)

```
┌─────────────────────────────────────────────────────────────┐
│ Command Prompt / PowerShell                                 │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│ $ cd c:\Users\balan\OneDrive\Desktop\caps\backend          │
│                                                             │
│ $ python -m venv venv                                       │
│ Creating virtual environment...                             │
│                                                             │
│ $ venv\Scripts\activate                                     │
│ (venv) $                                                    │
│                                                             │
│ $ pip install -r requirements.txt                           │
│ Installing dependencies...                                  │
│                                                             │
│ $ python main.py                                            │
│ [INFO] PHASE 1: SELF-HEALING DEMAND FORECASTING SYSTEM     │
│ [INFO] [1/7] Loading data                                  │
│ [INFO] [2/7] Splitting data                                │
│ [INFO] [3/7] Feature engineering                           │
│ [INFO] [4/7] Training model                                │
│ [INFO] [5/7] Simulating months                             │
│ [INFO] 2012-02: SEVERE drift detected                      │
│ [INFO] Tier 3 (Retrain): Full model retraining            │
│ [INFO] Retrain successful: MAE $67,394 → $58,200          │
│ [INFO] 2012-03: MILD drift detected                        │
│ [INFO] Tier 2 (Fine-tune): Warm start with trees          │
│ [INFO] Fine-tune successful: MAE $58,200 → $55,100        │
│ [INFO] PHASE 1 COMPLETE in 69s | Severity: SEVERE         │
│                                                             │
│ $ uvicorn api:app --reload --port 8000                     │
│ INFO:     Uvicorn running on http://127.0.0.1:8000        │
│ INFO:     Application startup complete                     │
│                                                             │
│ ✓ KEEP THIS TERMINAL OPEN!                                 │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

---

### Step 2: Open Terminal 2 (Frontend)

```
┌─────────────────────────────────────────────────────────────┐
│ Command Prompt / PowerShell (New Window)                    │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│ $ cd c:\Users\balan\OneDrive\Desktop\caps\frontend         │
│                                                             │
│ $ npm install                                               │
│ Installing dependencies...                                  │
│ added 500+ packages                                         │
│                                                             │
│ $ npm run dev                                               │
│                                                             │
│   VITE v4.3.9  ready in 234 ms                             │
│                                                             │
│   ➜  Local:   http://localhost:5173/                       │
│   ➜  press h to show help                                  │
│                                                             │
│ ✓ KEEP THIS TERMINAL OPEN!                                 │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

---

### Step 3: Open Browser

```
┌─────────────────────────────────────────────────────────────┐
│ Browser Address Bar                                         │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│ http://localhost:5173                                       │
│                                                             │
│ ↓ Press Enter ↓                                             │
│                                                             │
│ ┌─────────────────────────────────────────────────────────┐ │
│ │ SH-DFS Monitor - Self-Healing Demand Forecasting System │ │
│ ├─────────────────────────────────────────────────────────┤ │
│ │                                                         │ │
│ │ [Overview] [Drift] [Performance] [Features] [Stores]   │ │
│ │ [Predictions] [Upload]                                 │ │
│ │                                                         │ │
│ │ ┌─────────────────────────────────────────────────────┐ │
│ │ │ Overview                                            │ │
│ │ ├─────────────────────────────────────────────────────┤ │
│ │ │                                                     │ │
│ │ │  Error Trend                                        │ │
│ │ │  ┌─────────────────────────────────────────────┐   │ │
│ │ │  │ ╱╲                                          │   │ │
│ │ │  │╱  ╲╱╲                                       │   │ │
│ │ │  │      ╲╱╲                                    │   │ │
│ │ │  └─────────────────────────────────────────────┘   │ │
│ │ │                                                     │ │
│ │ │  Drifted Features                                   │ │
│ │ │  ┌─────────────────────────────────────────────┐   │ │
│ │ │  │ ████████ 12 features                        │   │ │
│ │ │  │ ██████ 8 features                           │   │ │
│ │ │  │ ████ 5 features                             │   │ │
│ │ │  └─────────────────────────────────────────────┘   │ │
│ │ │                                                     │ │
│ │ │  Monthly Sales                                      │ │
│ │ │  ┌─────────────────────────────────────────────┐   │ │
│ │ │  │ ▁▂▃▄▅▆▇█▇▆▅▄▃▂▁                             │   │ │
│ │ │  └─────────────────────────────────────────────┘   │ │
│ │ │                                                     │ │
│ │ └─────────────────────────────────────────────────────┘ │
│ │                                                         │ │
│ └─────────────────────────────────────────────────────────┘ │
│                                                             │
│ ✓ Dashboard loaded!                                         │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

---

## 🔄 Data Flow

```
┌──────────────────────────────────────────────────────────────┐
│                    DATA FLOW DIAGRAM                         │
└──────────────────────────────────────────────────────────────┘

Browser (http://localhost:5173)
    │
    ├─ User clicks on page
    │
    ▼
React Component
    │
    ├─ Calls API endpoint
    │
    ▼
HTTP Request
    │
    ├─ GET http://localhost:8000/api/healing-actions
    │
    ▼
FastAPI Server (http://localhost:8000)
    │
    ├─ Processes request
    ├─ Reads data from SQLite
    ├─ Calculates statistics
    │
    ▼
JSON Response
    │
    ├─ {
    │    "total_actions": 12,
    │    "fine_tuned": 7,
    │    "avg_improvement": 0.0648
    │  }
    │
    ▼
React Component
    │
    ├─ Receives data
    ├─ Updates state
    ├─ Re-renders chart
    │
    ▼
Browser Display
    │
    ├─ Chart updates
    ├─ Statistics show
    ├─ User sees results
    │
    ▼
✓ Done!
```

---

## 📊 What Each Terminal Shows

### Terminal 1: Backend Logs

```
INFO:     Uvicorn running on http://127.0.0.1:8000
INFO:     Application startup complete
INFO:     127.0.0.1:54321 - "GET /api/health HTTP/1.1" 200 OK
INFO:     127.0.0.1:54322 - "GET /api/healing-actions HTTP/1.1" 200 OK
INFO:     127.0.0.1:54323 - "GET /api/summary HTTP/1.1" 200 OK
INFO:     127.0.0.1:54324 - "GET /api/drift HTTP/1.1" 200 OK
INFO:     127.0.0.1:54325 - "GET /api/feature-importances HTTP/1.1" 200 OK
```

### Terminal 2: Frontend Logs

```
  VITE v4.3.9  ready in 234 ms

  ➜  Local:   http://localhost:5173/
  ➜  press h to show help

[HMR] connected
```

---

## 🎯 Quick Reference

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

### Browser
```
http://localhost:5173
```

---

## ✅ Success Checklist

```
Terminal 1: Backend
├─ ✓ Virtual environment activated
├─ ✓ Dependencies installed
├─ ✓ Pipeline completed
├─ ✓ API server running on port 8000
└─ ✓ Logs showing requests

Terminal 2: Frontend
├─ ✓ Dependencies installed
├─ ✓ Dev server running on port 5173
├─ ✓ Hot reload enabled
└─ ✓ No console errors

Browser
├─ ✓ Dashboard loads
├─ ✓ Charts display data
├─ ✓ Pages are interactive
├─ ✓ API calls work
└─ ✓ Real-time updates

Overall
├─ ✓ Backend and frontend connected
├─ ✓ Data flows correctly
├─ ✓ System is working
└─ ✓ Ready to use!
```

---

## 🚀 Start Now!

### Copy & Paste

**Terminal 1:**
```bash
cd c:\Users\balan\OneDrive\Desktop\caps\backend
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
python main.py
uvicorn api:app --reload --port 8000
```

**Terminal 2:**
```bash
cd c:\Users\balan\OneDrive\Desktop\caps\frontend
npm install
npm run dev
```

**Browser:**
```
http://localhost:5173
```

---

## 🎉 That's It!

You now have:
- ✅ Backend running on port 8000
- ✅ Frontend running on port 5173
- ✅ Dashboard displaying data
- ✅ Real-time updates
- ✅ Drift detection working
- ✅ Fine-tuning active

**Enjoy! 🚀**
