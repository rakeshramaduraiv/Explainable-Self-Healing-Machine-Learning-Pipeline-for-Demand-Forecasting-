@echo off
title Sales Forecasting - Deploy

echo.
echo ============================================================
echo   SALES FORECASTING - DEPLOY
echo ============================================================
echo.

:: Kill anything on port 8000 and 5173
echo [1/4] Clearing ports...
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":8000" 2^>nul') do taskkill /PID %%a /F >nul 2>&1
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":5173" 2^>nul') do taskkill /PID %%a /F >nul 2>&1
timeout /t 2 /nobreak >nul

:: Start backend
echo [2/4] Starting Backend...
start "Backend" /MIN cmd /c "venv\Scripts\python.exe backend_minimal.py > backend.log 2>&1"
timeout /t 8 /nobreak >nul

:: Start frontend
echo [3/4] Starting Frontend...
if not exist "frontend\node_modules" (
    echo Installing frontend dependencies...
    cd frontend && npm install && cd ..
)
start "Frontend" /MIN cmd /c "cd frontend && npm run dev > ..\frontend.log 2>&1"
timeout /t 6 /nobreak >nul

:: Start ngrok
echo [4/4] Starting ngrok tunnel...
start "Ngrok" /MIN cmd /c "ngrok.exe http 5173 > ngrok.log 2>&1"
timeout /t 5 /nobreak >nul

:: Get public URL
echo.
echo ============================================================
echo   FETCHING YOUR PUBLIC URL...
echo ============================================================
powershell -Command "$r = (Invoke-WebRequest -Uri 'http://localhost:4040/api/tunnels' -UseBasicParsing).Content | ConvertFrom-Json; $url = $r.tunnels[0].public_url; Write-Host ''; Write-Host '  YOUR PUBLIC URL:' -ForegroundColor Green; Write-Host '  '$url -ForegroundColor Cyan; Write-Host ''; Write-Host '  Share this link with anyone!' -ForegroundColor Yellow; Write-Host ''" 2>&1

echo ============================================================
echo   Backend  : http://localhost:8000
echo   Frontend : http://localhost:5173
echo   Logs     : backend.log / frontend.log
echo ============================================================
echo.
echo Press any key to open ngrok dashboard (to see your URL anytime)
pause >nul
start http://localhost:4040
