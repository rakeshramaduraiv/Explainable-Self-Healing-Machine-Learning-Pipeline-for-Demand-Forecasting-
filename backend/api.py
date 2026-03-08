import json, os, glob, shutil, subprocess, sys, time
from pathlib import Path
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import pandas as pd
from demand_analyzer import DemandAnalyzer

app = FastAPI(title="SH-DFS API", version="2.0.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

BASE      = Path(__file__).parent.resolve()
LOGS      = BASE / "logs"
UPLOAD    = BASE / "uploads"
DATA      = BASE / "data"
PROCESSED = BASE / "processed"

# ── Simple in-process cache (ttl=30s) ────────────────────────────────────────
_cache: dict = {}
def _cached(key: str, ttl: int, fn):
    now = time.time()
    if key in _cache and now - _cache[key]["ts"] < ttl:
        return _cache[key]["val"]
    val = fn()
    _cache[key] = {"ts": now, "val": val}
    return val

def _bust():
    _cache.clear()
# ─────────────────────────────────────────────────────────────────────────────

def safe_path(base: Path, filename: str) -> Path:
    p = (base / Path(filename).name).resolve()
    if not str(p).startswith(str(base)):
        raise HTTPException(400, "Invalid path")
    return p

def rj(fname: str):
    p = LOGS / fname
    if not p.exists():
        return None
    with open(p, encoding="utf-8") as f:
        return json.load(f)

def dedup(records: list, key="month"):
    seen, out = set(), []
    for d in reversed(records):
        if d.get(key) not in seen:
            seen.add(d[key]); out.insert(0, d)
    return sorted(out, key=lambda x: x[key])

@app.get("/api/health")
def health():
    return {
        "status": "ok",
        "version": "2.0.0",
        "logs_exist": LOGS.exists(),
        "model_exists": (BASE / "models" / "active_model.pkl").exists(),
        "ts": time.time(),
    }

@app.get("/api/summary")
def summary():
    return _cached("summary", 30, lambda: rj("phase1_summary.json") or {})

@app.get("/api/baseline")
def baseline():
    return _cached("baseline", 30, lambda: rj("baseline_metrics.json") or {})

@app.get("/api/drift")
def drift():
    return _cached("drift", 15, lambda: dedup(rj("drift_history.json") or []))

@app.get("/api/batches")
def batches():
    return _cached("batches", 15, lambda: dedup(rj("prediction_batches.json") or []))

@app.get("/api/monthly-sales")
def monthly_sales():
    def _build():
        b = dedup(rj("prediction_batches.json") or [])
        return [{"month": x["month"], "actual": x.get("mean_actual"),
                 "predicted": x.get("mean_pred"),
                 "mae": abs((x.get("mean_actual") or 0) - (x.get("mean_pred") or 0))} for x in b]
    return _cached("monthly_sales", 30, _build)

@app.get("/api/store-stats")
def store_stats():
    def _build():
        # 1. Try any CSV (logs/ or processed/) that has a store column
        frames = []
        for f in list(LOGS.glob("predictions_*.csv")) + list(PROCESSED.glob("predictions_*.csv")):
            try:
                df = pd.read_csv(f)
                df.columns = [c.lower() for c in df.columns]
                # normalise column names
                if "weekly_sales" in df.columns: df = df.rename(columns={"weekly_sales": "actual"})
                if "predicted"    in df.columns: df = df.rename(columns={"predicted": "prediction"})
                if {"store", "actual", "prediction"}.issubset(df.columns):
                    frames.append(df[["store", "actual", "prediction"]])
            except Exception:
                pass
        if frames:
            df = pd.concat(frames, ignore_index=True)
            df = df.dropna(subset=["store", "actual", "prediction"])
            df["store"] = pd.to_numeric(df["store"], errors="coerce")
            df = df.dropna(subset=["store"])
            df["store"] = df["store"].astype(int)
            df["abs_err"] = (df["actual"] - df["prediction"]).abs()
            agg = df.groupby("store").agg(
                mae=("abs_err", "mean"),
                avg_sales=("actual", "mean"),
                count=("actual", "count"),
            ).reset_index().rename(columns={"store": "Store"})
            return agg.round(2).to_dict(orient="records")
        # 2. No store column anywhere — compute from uploaded_data.csv + global MAE proxy
        data_file = DATA / "uploaded_data.csv"
        if not data_file.exists():
            return []
        raw = pd.read_csv(data_file)
        raw.columns = [c.lower() for c in raw.columns]
        if "store" not in raw.columns or "weekly_sales" not in raw.columns:
            return []
        batches = rj("prediction_batches.json") or []
        global_mae = 0.0
        if batches:
            vals = [abs((b.get("mean_actual") or 0) - (b.get("mean_pred") or 0)) for b in dedup(batches)]
            global_mae = sum(vals) / len(vals) if vals else 0.0
        agg = raw.groupby("store")["weekly_sales"].agg(
            avg_sales="mean", count="count"
        ).reset_index().rename(columns={"store": "Store"})
        agg["mae"] = global_mae
        return agg.round(2).to_dict(orient="records")
    return _cached("store_stats", 60, _build)

@app.get("/api/training-log")
def training_log():
    return rj("training_log.json") or {}

@app.get("/api/data-split")
def data_split():
    return rj("data_split.json") or {}

@app.get("/api/processed-months")
def processed_months():
    files = list((BASE / "processed").glob("summary_*.json"))
    months = sorted({f.name.split("_")[1] for f in files})
    return months

@app.get("/api/predictions-meta")
def predictions_meta():
    """Returns {month: last_modified_ts} for change detection polling."""
    result = {}
    for f in sorted(PROCESSED.glob("predictions_*.csv")):
        parts = f.stem.split("_")  # predictions_YYYY-MM_...
        if len(parts) >= 2:
            month = parts[1]
            mtime = f.stat().st_mtime
            if month not in result or mtime > result[month]:
                result[month] = round(mtime, 3)
    return result

@app.get("/api/predictions/{month}")
def predictions(month: str):
    if not month.replace("-", "").isalnum():
        raise HTTPException(400, "Invalid month format")
    files = sorted(PROCESSED.glob(f"predictions_{month}_*.csv"))
    if not files:
        raise HTTPException(404, "No predictions for this month")
    latest = files[-1]
    df = pd.read_csv(latest)
    # Ensure CI columns exist (backward compat with old CSVs)
    for col in ["CI_Lower", "CI_Upper", "Abs_Error", "Error_Pct"]:
        if col not in df.columns:
            if col == "Abs_Error" and "Weekly_Sales" in df.columns and "Predicted" in df.columns:
                df[col] = (df["Weekly_Sales"] - df["Predicted"]).abs().round(2)
            elif col == "Error_Pct" and "Weekly_Sales" in df.columns and "Predicted" in df.columns:
                df[col] = (df["Abs_Error"] / (df["Weekly_Sales"].abs() + 1e-9) * 100).round(2)
            else:
                df[col] = None
    return df.head(500).to_dict(orient="records")

@app.get("/api/demand-metrics")
def demand_metrics():
    """Get demand analysis metrics"""
    try:
        analyzer = DemandAnalyzer()
        analyzer.load_data(str(DATA / "uploaded_data.csv"))
        return analyzer.calculate_demand_metrics()
    except Exception as e:
        raise HTTPException(404, f"No data available: {str(e)}")

@app.get("/api/demand-trend")
def demand_trend():
    """Get demand trend data for visualization"""
    try:
        analyzer = DemandAnalyzer()
        analyzer.load_data(str(DATA / "uploaded_data.csv"))
        return analyzer.get_demand_trend_data()
    except Exception as e:
        raise HTTPException(404, f"No data available: {str(e)}")

@app.get("/api/monthly-demand")
def monthly_demand():
    """Get monthly aggregated demand data"""
    try:
        analyzer = DemandAnalyzer()
        analyzer.load_data(str(DATA / "uploaded_data.csv"))
        return analyzer.get_monthly_demand_data()
    except Exception as e:
        raise HTTPException(404, f"No data available: {str(e)}")

@app.get("/api/store-demand")
def store_demand():
    """Get store-level demand data"""
    try:
        analyzer = DemandAnalyzer()
        analyzer.load_data(str(DATA / "uploaded_data.csv"))
        return analyzer.get_store_demand_data()
    except Exception as e:
        raise HTTPException(404, f"No data available: {str(e)}")

@app.post("/api/upload-predict")
async def upload_predict(file: UploadFile = File(...)):
    if not file.filename or not file.filename.lower().endswith(".csv"):
        raise HTTPException(400, "Only .csv files are accepted")
    safe_name = Path(file.filename).name
    if ".." in safe_name or "/" in safe_name or "\\" in safe_name:
        raise HTTPException(400, "Invalid filename")
    UPLOAD.mkdir(exist_ok=True)
    dest = UPLOAD / safe_name
    content = await file.read()
    if len(content) > 50 * 1024 * 1024:
        raise HTTPException(413, "File too large (max 50 MB)")
    with open(dest, "wb") as f:
        f.write(content)
    shutil.copy(dest, DATA / "uploaded_data.csv")
    result = subprocess.run(
        [sys.executable, str(BASE / "main.py")],
        capture_output=True, text=True, timeout=300, cwd=str(BASE)
    )
    if result.returncode != 0:
        stderr = result.stderr[-2000:]
        for line in reversed(stderr.splitlines()):
            if "Error" in line or "error" in line:
                raise HTTPException(422, line.strip())
        raise HTTPException(500, stderr)
    _bust()  # invalidate all caches after successful pipeline run
    return {"status": "ok", "stdout": result.stdout[-1000:]}
