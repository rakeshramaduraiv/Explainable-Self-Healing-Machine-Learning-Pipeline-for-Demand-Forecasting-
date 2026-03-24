# 🔧 API Connection Fix

## Problem
Frontend is calling `localhost:5173` instead of backend at `localhost:8000`

## Solution

### 1. Environment File Created
✅ Created `frontend/.env` with:
```
VITE_API_URL=http://localhost:8000
```

### 2. API Client Fixed
✅ Updated `frontend/src/api.js` to use `http://localhost:8000` as default

### 3. Restart Required
**IMPORTANT**: Restart the frontend development server to pick up the new environment variable:

```bash
# Stop the frontend (Ctrl+C)
cd frontend
npm run dev
```

### 4. Verify Backend is Running
Make sure the backend is running on port 8000:

```bash
cd backend
uvicorn api:app --reload --port 8000
```

### 5. Test Connection
After restarting frontend, check browser console - API calls should now go to `localhost:8000` instead of `localhost:5173`

## Quick Test
1. Open browser dev tools (F12)
2. Go to Network tab
3. Try uploading a file in the Predict page
4. Verify API calls go to `http://localhost:8000/api/seq/upload-actuals`

The drift analysis should now work correctly in the prediction cycle!