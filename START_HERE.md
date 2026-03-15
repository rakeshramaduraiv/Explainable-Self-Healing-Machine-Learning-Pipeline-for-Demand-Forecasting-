# 🎯 2-Terminal Setup - Final Summary

## Simple: Backend + Frontend in 2 Terminals

```
┌─────────────────────────────────────────────────────────────┐
│                    YOUR SETUP                              │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  Terminal 1: Backend (Python FastAPI)                      │
│  ├─ Port: 8000                                             │
│  ├─ URL: http://localhost:8000                             │
│  └─ Docs: http://localhost:8000/docs                       │
│                                                             │
│  Terminal 2: Frontend (React Vite)                         │
│  ├─ Port: 5173                                             │
│  ├─ URL: http://localhost:5173                             │
│  └─ Dashboard: 7 pages with charts                         │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

---

## 🚀 Quick Start (Copy & Paste)

### First Time Setup (10 minutes)

#### Terminal 1: Backend Setup
```bash
cd c:\Users\balan\OneDrive\Desktop\caps\backend
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
python main.py
```

Wait for pipeline to complete, then:

```bash
uvicorn api:app --reload --port 8000
```

**Keep this terminal open!**

#### Terminal 2: Frontend Setup
```bash
cd c:\Users\balan\OneDrive\Desktop\caps\frontend
npm install
npm run dev
```

**Keep this terminal open!**

#### Open Browser
```
http://localhost:5173
```

---

## 🔄 Subsequent Times (2 minutes)

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

### Open Browser
```
http://localhost:5173
```

---

## 📊 What You'll See

### Terminal 1 Output
```
INFO:     Uvicorn running on http://127.0.0.1:8000
INFO:     Application startup complete
INFO:     127.0.0.1:54321 - "GET /api/health HTTP/1.1" 200 OK
INFO:     127.0.0.1:54322 - "GET /api/healing-actions HTTP/1.1" 200 OK
```

### Terminal 2 Output
```
  VITE v4.3.9  ready in 234 ms

  ➜  Local:   http://localhost:5173/
  ➜  press h to show help
```

### Browser Dashboard
```
✓ Overview page with charts
✓ Drift Analysis
✓ Model Performance
✓ Feature Importance
✓ Store Analytics
✓ Predictions
✓ Upload & Monitor
✓ Real-time data from API
```

---

## 🎯 How It Works

```
Browser (http://localhost:5173)
    ↓
React Frontend
    ↓
Calls API (http://localhost:8000/api/*)
    ↓
Python Backend (FastAPI)
    ↓
Returns JSON data
    ↓
Frontend displays charts
```

---

## 📋 Terminal 1: Backend (Python)

### What it does:
- Runs FastAPI server
- Serves API endpoints
- Handles drift detection
- Manages fine-tuning
- Stores data in SQLite
- Logs all actions

### Commands:
```bash
# First time
cd c:\Users\balan\OneDrive\Desktop\caps\backend
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
python main.py
uvicorn api:app --reload --port 8000

# Subsequent times
cd c:\Users\balan\OneDrive\Desktop\caps\backend
venv\Scripts\activate
uvicorn api:app --reload --port 8000
```

### Keep Running:
```
✓ Don't close this terminal
✓ Keep it running while using frontend
✓ Logs will show API calls
```

---

## 📋 Terminal 2: Frontend (React)

### What it does:
- Runs Vite dev server
- Serves React dashboard
- Displays 7 pages with charts
- Calls backend API
- Shows healing statistics
- Real-time updates

### Commands:
```bash
# First time
cd c:\Users\balan\OneDrive\Desktop\caps\frontend
npm install
npm run dev

# Subsequent times
cd c:\Users\balan\OneDrive\Desktop\caps\frontend
npm run dev
```

### Keep Running:
```
✓ Don't close this terminal
✓ Keep it running while using dashboard
✓ Hot reload enabled (auto-refresh on code changes)
```

---

## 🌐 Access Points

| Service | URL | Purpose |
|---------|-----|---------|
| Frontend | http://localhost:5173 | Dashboard |
| Backend | http://localhost:8000 | API |
| API Docs | http://localhost:8000/docs | Swagger UI |
| Health | http://localhost:8000/api/health | Check status |

---

## 🧪 Test Commands (Optional 3rd Terminal)

```bash
# Check backend health
curl http://localhost:8000/api/health

# Check healing actions
curl http://localhost:8000/api/healing-actions

# Check summary
curl http://localhost:8000/api/summary

# Check drift
curl http://localhost:8000/api/drift

# Check feature importances
curl http://localhost:8000/api/feature-importances
```

---

## ✅ Checklist

- [ ] Terminal 1: Backend running on port 8000
- [ ] Terminal 2: Frontend running on port 5173
- [ ] Browser: Dashboard loads at http://localhost:5173
- [ ] Dashboard: Shows 7 pages with charts
- [ ] API: Responds to requests
- [ ] Healing: Statistics visible in dashboard

---

## 🎨 Dashboard Pages

1. **Overview**
   - Error trend line
   - Drifted features bar
   - Monthly sales area

2. **Drift Analysis**
   - Error increase bar
   - Feature count stacked bar
   - Drift history table

3. **Model Performance**
   - MAE trend line
   - Error percentage line
   - Reference line

4. **Feature Importance**
   - Top-20 horizontal bar
   - 6 group comparison cards

5. **Store Analytics**
   - MAE by store bar
   - Sales vs MAE scatter
   - Best/worst tables

6. **Predictions**
   - Actual vs predicted area
   - Absolute error bar
   - Monthly area chart
   - Data table

7. **Upload & Monitor**
   - Upload form
   - Drift results
   - MAE trend
   - Feature count

---

## 🔧 Troubleshooting

### Backend Issues

**Port 8000 already in use:**
```bash
uvicorn api:app --reload --port 8001
```

**Module not found:**
```bash
pip install -r requirements.txt --force-reinstall
```

**Model not found:**
```bash
python main.py
```

### Frontend Issues

**Port 5173 already in use:**
```bash
# Vite will use next available port automatically
npm run dev
```

**Dependencies not installed:**
```bash
npm install
```

**API not responding:**
```bash
# Check if backend is running
curl http://localhost:8000/api/health
```

---

## 📊 Performance

| Metric | Value |
|--------|-------|
| Backend startup | 2-3 seconds |
| Frontend startup | 3-5 seconds |
| API response | < 100ms |
| Dashboard load | < 2 seconds |
| Chart rendering | < 1 second |

---

## 🎯 Workflow

### Day 1: Setup (10 minutes)
```bash
# Terminal 1
cd c:\Users\balan\OneDrive\Desktop\caps\backend
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
python main.py
uvicorn api:app --reload --port 8000

# Terminal 2
cd c:\Users\balan\OneDrive\Desktop\caps\frontend
npm install
npm run dev

# Browser
http://localhost:5173
```

### Day 2+: Quick Start (2 minutes)
```bash
# Terminal 1
cd c:\Users\balan\OneDrive\Desktop\caps\backend
venv\Scripts\activate
uvicorn api:app --reload --port 8000

# Terminal 2
cd c:\Users\balan\OneDrive\Desktop\caps\frontend
npm run dev

# Browser
http://localhost:5173
```

---

## 🚀 Ready to Go!

### Copy These Commands

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

## ✨ Features

✅ Automatic drift detection
✅ Automatic fine-tuning
✅ Automatic retraining
✅ Real-time dashboard
✅ 7 pages with charts
✅ Healing statistics
✅ API documentation
✅ Hot reload (frontend)
✅ Auto-restart (backend)

---

## 🎉 That's It!

Just 2 terminals and you have:
- ✅ Backend API running
- ✅ Frontend dashboard running
- ✅ Real-time data updates
- ✅ Drift detection working
- ✅ Fine-tuning active
- ✅ Beautiful charts

**Let's go! 🚀**

---

## 📚 Documentation

For more details, see:
- [2_TERMINAL_SETUP.md](2_TERMINAL_SETUP.md) - Detailed setup guide
- [QUICK_COMMANDS.md](QUICK_COMMANDS.md) - All commands
- [SETUP_AND_DEPLOYMENT.md](SETUP_AND_DEPLOYMENT.md) - Full guide

---

**Happy coding! 🎉**
