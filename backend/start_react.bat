@echo off
echo Starting SH-DFS React Dashboard...
echo.
echo [1/2] Starting FastAPI backend on http://localhost:8000
start "FastAPI" cmd /k "uvicorn api:app --reload --port 8000"
timeout /t 2 /nobreak >nul
echo [2/2] Starting React frontend on http://localhost:5173
cd frontend
start "React" cmd /k "npm run dev"
echo.
echo Dashboard: http://localhost:5173
echo API docs:  http://localhost:8000/docs
