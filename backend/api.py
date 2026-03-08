import json, shutil, subprocess, sys, time
from pathlib import Path
from contextlib import asynccontextmanager
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
import pandas as pd
from demand_analyzer import DemandAnalyzer

BASE      = Path(__file__).parent.resolve()
LOGS      = BASE / "logs"
UPLOAD    = BASE / "uploads"
DATA      = BASE / "data"
PROCESSED = BASE / "processed"

# ── Cache ─────────────────────────────────────────────────────────────────────
_cache: dict = {}

def _cached(key: str, ttl: int, fn):
    now = time.time()
    if key in _cache and now - _cache[key]["ts"] < ttl:
        return _cache[key]["val"]
    val = fn()
    _cache[key] = {"ts": now, "val": val}
    return val

def _bust(): _cache.clear()

# ── Helpers ───────────────────────────────────────────────────────────────────
def rj(fname: str):
    p = LOGS / fname
    if not p.exists(): return None
    with open(p, encoding="utf-8") as f: return json.load(f)

def dedup(records: list, key="month"):
    seen, out = set(), []
    for d in reversed(records):
        if d.get(key) not in seen:
            seen.add(d[key]); out.insert(0, d)
    return sorted(out, key=lambda x: x[key])

# ── Extracted build functions (called at startup + on demand) ─────────────────
def _build_store_stats():
    frames = []
    for f in list(LOGS.glob("predictions_*.csv")) + list(PROCESSED.glob("predictions_*.csv")):
        try:
            df = pd.read_csv(f)
            df.columns = [c.lower() for c in df.columns]
            if "weekly_sales" in df.columns: df = df.rename(columns={"weekly_sales": "actual"})
            if "predicted"    in df.columns: df = df.rename(columns={"predicted": "prediction"})
            if {"store", "actual", "prediction"}.issubset(df.columns):
                frames.append(df[["store", "actual", "prediction"]])
        except Exception: pass
    if frames:
        df = pd.concat(frames, ignore_index=True)
        df = df.dropna(subset=["store", "actual", "prediction"])
        df["store"] = pd.to_numeric(df["store"], errors="coerce")
        df = df.dropna(subset=["store"]).copy()
        df["store"] = df["store"].astype(int)
        df["abs_err"] = (df["actual"] - df["prediction"]).abs()
        agg = df.groupby("store").agg(
            mae=("abs_err", "mean"), avg_sales=("actual", "mean"), count=("actual", "count"),
        ).reset_index().rename(columns={"store": "Store"})
        return agg.round(2).to_dict(orient="records")
    data_file = DATA / "uploaded_data.csv"
    if not data_file.exists(): return []
    raw = pd.read_csv(data_file)
    raw.columns = [c.lower() for c in raw.columns]
    if "store" not in raw.columns or "weekly_sales" not in raw.columns: return []
    batches = rj("prediction_batches.json") or []
    global_mae = 0.0
    if batches:
        vals = [abs((b.get("mean_actual") or 0) - (b.get("mean_pred") or 0)) for b in dedup(batches)]
        global_mae = sum(vals) / len(vals) if vals else 0.0
    agg = raw.groupby("store")["weekly_sales"].agg(avg_sales="mean", count="count").reset_index().rename(columns={"store": "Store"})
    agg["mae"] = global_mae
    return agg.round(2).to_dict(orient="records")

def _get_analyzer():
    a = DemandAnalyzer()
    a.load_data(str(DATA / "uploaded_data.csv"))
    return a

def _build_demand_metrics():
    return _get_analyzer().calculate_demand_metrics()

def _build_demand_trend():
    return _get_analyzer().get_demand_trend_data()

def _build_monthly_demand():
    return _get_analyzer().get_monthly_demand_data()

def _build_store_demand():
    return _get_analyzer().get_store_demand_data()

# ── Startup: warm all slow caches before first request ───────────────────────
@asynccontextmanager
async def lifespan(app):
    for key, fn in [
        ("store_stats",    _build_store_stats),
        ("demand_metrics", _build_demand_metrics),
        ("demand_trend",   _build_demand_trend),
        ("monthly_demand", _build_monthly_demand),
        ("store_demand",   _build_store_demand),
    ]:
        try: _cached(key, 300, fn)
        except Exception: pass
    yield

app = FastAPI(title="SH-DFS API", version="2.0.0", lifespan=lifespan)
app.add_middleware(GZipMiddleware, minimum_size=500)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

# ── Endpoints ─────────────────────────────────────────────────────────────────
@app.get("/api/health")
def health():
    return {"status": "ok", "version": "2.0.0",
            "logs_exist": LOGS.exists(),
            "model_exists": (BASE / "models" / "active_model.pkl").exists(),
            "ts": time.time()}

@app.get("/api/summary")
def summary():
    return _cached("summary", 60, lambda: rj("phase1_summary.json") or {})

@app.get("/api/baseline")
def baseline():
    return _cached("baseline", 60, lambda: rj("baseline_metrics.json") or {})

@app.get("/api/drift")
def drift():
    return _cached("drift", 30, lambda: dedup(rj("drift_history.json") or []))

@app.get("/api/batches")
def batches():
    return _cached("batches", 30, lambda: dedup(rj("prediction_batches.json") or []))

@app.get("/api/monthly-sales")
def monthly_sales():
    def _build():
        b = dedup(rj("prediction_batches.json") or [])
        return [{"month": x["month"], "actual": x.get("mean_actual"),
                 "predicted": x.get("mean_pred"),
                 "mae": abs((x.get("mean_actual") or 0) - (x.get("mean_pred") or 0))} for x in b]
    return _cached("monthly_sales", 60, _build)

@app.get("/api/store-stats")
def store_stats():
    return _cached("store_stats", 120, _build_store_stats)

@app.get("/api/training-log")
def training_log():
    return _cached("training_log", 60, lambda: rj("training_log.json") or {})

@app.get("/api/data-split")
def data_split():
    return _cached("data_split", 60, lambda: rj("data_split.json") or {})

@app.get("/api/processed-months")
def processed_months():
    return _cached("processed_months", 30, lambda: sorted(
        {f.name.split("_")[1] for f in (BASE / "processed").glob("summary_*.json")}
    ))

@app.get("/api/predictions-meta")
def predictions_meta():
    result = {}
    for f in PROCESSED.glob("predictions_*.csv"):
        parts = f.stem.split("_")
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
    if not files: raise HTTPException(404, "No predictions for this month")
    df = pd.read_csv(files[-1])
    for col in ["CI_Lower", "CI_Upper", "Abs_Error", "Error_Pct"]:
        if col not in df.columns:
            if col == "Abs_Error" and "Weekly_Sales" in df.columns and "Predicted" in df.columns:
                df[col] = (df["Weekly_Sales"] - df["Predicted"]).abs().round(2)
            elif col == "Error_Pct" and "Weekly_Sales" in df.columns and "Predicted" in df.columns:
                df[col] = (df["Abs_Error"] / (df["Weekly_Sales"].abs() + 1e-9) * 100).round(2)
            else:
                df[col] = None
    return df.head(500).to_dict(orient="records")

@app.get("/api/alerts")
def alerts():
    d = dedup(rj("drift_history.json") or [])
    result = []
    for i, x in enumerate(reversed(d)):
        sev = x.get("severity", "none")
        if sev not in ("severe", "mild"): continue
        result.append({"id": f"ALT-{len(d)-i:03d}", "severity": sev, "month": x["month"],
                        "severe_features": x["severe_features"], "mild_features": x["mild_features"],
                        "mae": x["error_trend"]["current_error"],
                        "error_ratio": x["error_trend"]["error_increase"]})
    return result[:20]

@app.get("/api/datasets")
def datasets():
    def _build():
        split = rj("data_split.json") or {}
        insp  = rj("data_inspection.json") or {}
        d     = dedup(rj("drift_history.json") or [])
        bats  = dedup(rj("prediction_batches.json") or [])
        dbm   = {x["month"]: x for x in d}
        rows  = []
        for b in bats:
            x = dbm.get(b["month"], {})
            rows.append({"month": b["month"], "records": b.get("count", 0),
                         "mean_actual": b.get("mean_actual"), "mean_pred": b.get("mean_pred"),
                         "mae": abs(b.get("mean_actual", 0) - b.get("mean_pred", 0)) if "mean_actual" in b else None,
                         "error_ratio": x.get("error_trend", {}).get("error_increase"),
                         "severity": x.get("severity", "N/A")})
        return {"split": split, "inspection": insp, "batches": rows}
    return _cached("datasets", 60, _build)

@app.get("/api/demand-metrics")
def demand_metrics():
    try: return _cached("demand_metrics", 300, _build_demand_metrics)
    except Exception as e: raise HTTPException(404, f"No data available: {e}")

@app.get("/api/demand-trend")
def demand_trend():
    try: return _cached("demand_trend", 300, _build_demand_trend)
    except Exception as e: raise HTTPException(404, f"No data available: {e}")

@app.get("/api/monthly-demand")
def monthly_demand():
    try: return _cached("monthly_demand", 300, _build_monthly_demand)
    except Exception as e: raise HTTPException(404, f"No data available: {e}")

@app.get("/api/store-demand")
def store_demand():
    try: return _cached("store_demand", 300, _build_store_demand)
    except Exception as e: raise HTTPException(404, f"No data available: {e}")

@app.post("/api/upload-predict")
async def upload_predict(file: UploadFile = File(...)):
    if not file.filename or not file.filename.lower().endswith(".csv"):
        raise HTTPException(400, "Only .csv files are accepted")
    safe_name = Path(file.filename).name
    if ".." in safe_name or "/" in safe_name or "\\" in safe_name:
        raise HTTPException(400, "Invalid filename")
    UPLOAD.mkdir(exist_ok=True)
    content = await file.read()
    if len(content) > 50 * 1024 * 1024:
        raise HTTPException(413, "File too large (max 50 MB)")
    dest = UPLOAD / safe_name
    with open(dest, "wb") as f: f.write(content)
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
    _bust()
    return {"status": "ok", "stdout": result.stdout[-1000:]}
