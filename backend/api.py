import json, shutil, subprocess, sys, time, os
from pathlib import Path
from contextlib import asynccontextmanager
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
import pandas as pd
import joblib
import io
import numpy as np

BASE      = Path(__file__).parent.resolve()
LOGS      = BASE / "logs"
UPLOAD    = BASE / "uploads"
DATA      = BASE / "data"
PROCESSED = BASE / "processed"

def _get_product_names():
    """Detect product names/IDs from data dynamically."""
    data_file = DATA / "uploaded_data.csv"
    if not data_file.exists():
        return {}
    try:
        df = pd.read_csv(data_file, encoding="utf-8-sig")
        df.columns = df.columns.str.strip()
        if "Product" not in df.columns:
            return {}
        products = sorted(df["Product"].dropna().unique())
        result = {}
        for p in products:
            # Keep original string IDs (item_1…item_50) or format numeric ones
            key = str(p)
            label = str(p) if isinstance(p, str) and not str(p).isdigit() else f"Product {int(float(str(p)))}"
            result[key] = label
        return result
    except Exception:
        return {}

for d in [LOGS, UPLOAD, DATA, PROCESSED]:
    d.mkdir(exist_ok=True)

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
    seen = set()
    out  = {}
    for d in records:
        k = d.get(key)
        if k not in seen:
            seen.add(k); out[k] = d
    return sorted(out.values(), key=lambda x: x[key])

# ── Extracted build functions (called at startup + on demand) ─────────────────
def _latest_processed_files():
    """Return only the latest file per month (deduplicate multiple runs)."""
    best = {}
    for f in PROCESSED.glob("predictions_*.csv"):
        parts = f.stem.split("_")
        if len(parts) >= 2:
            month = parts[1]
            if month not in best or f.stat().st_mtime > best[month].stat().st_mtime:
                best[month] = f
    return sorted(best.values())

def _build_store_stats():
    frames = []
    for f in _latest_processed_files():
        try:
            df = pd.read_csv(f)
            df.columns = [c.lower() for c in df.columns]
            if "weekly_sales" in df.columns: df = df.rename(columns={"weekly_sales": "actual"})
            if "demand" in df.columns: df = df.rename(columns={"demand": "actual"})
            if "predicted" in df.columns: df = df.rename(columns={"predicted": "prediction"})
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
    if "store" not in raw.columns or "demand" not in raw.columns: return []
    batches = rj("prediction_batches.json") or []
    global_mae = 0.0
    if batches:
        vals = [abs((b.get("mean_actual") or 0) - (b.get("mean_pred") or 0)) for b in dedup(batches)]
        global_mae = sum(vals) / len(vals) if vals else 0.0
    agg = raw.groupby("store")["demand"].agg(avg_sales="mean", count="count").reset_index().rename(columns={"store": "Store"})
    agg["mae"] = global_mae
    return agg.round(2).to_dict(orient="records")

def _get_analyzer():
    from demand_analyzer import DemandAnalyzer
    data_file = str(DATA / "uploaded_data.csv")
    # Fix quoted-row CSVs
    import csv
    try:
        df_test = pd.read_csv(data_file)
        if len(df_test.columns) == 1 and ',' in df_test.columns[0]:
            df_test = pd.read_csv(data_file, quoting=csv.QUOTE_ALL)
            df_test.to_csv(data_file, index=False)
    except Exception:
        pass
    a = DemandAnalyzer()
    a.load_data(data_file)
    return a

def _build_demand_metrics():
    a = _get_analyzer()
    return a.calculate_demand_metrics()

def _build_demand_trend():
    a = _get_analyzer()
    df = a.get_demand_trend_data()
    return {"dates": df["Date"].astype(str).tolist(), "demand": df["Demand"].tolist()}

def _build_monthly_demand():
    a = _get_analyzer()
    df = a.get_monthly_demand_data()
    return {"months": df["Date"].tolist(), "demand": df["Demand"].tolist()}

def _build_store_demand():
    a = _get_analyzer()
    df = a.get_store_demand_data()
    if df is None or df.empty: return {"stores": [], "demand": []}
    return {"stores": df["Store"].tolist(), "demand": df["Demand"].tolist()}

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

CORS_ORIGINS = os.environ.get("CORS_ORIGINS", "*").split(",")

app = FastAPI(title="SH-DFS API", version="2.0.0", lifespan=lifespan)
app.add_middleware(GZipMiddleware, minimum_size=500)
app.add_middleware(CORSMiddleware, allow_origins=CORS_ORIGINS, allow_credentials=True, allow_methods=["GET", "POST"], allow_headers=["*"])

# ── Cache-Control header on all GET responses ─────────────────────────────────
@app.middleware("http")
async def cache_headers(request, call_next):
    response = await call_next(request)
    if request.method == "GET" and response.status_code == 200:
        response.headers["Cache-Control"] = "public, max-age=5, stale-while-revalidate=10"
    return response

# ── Endpoints ─────────────────────────────────────────────────────────────────
@app.get("/api/health")
def health():
    return {"status": "ok", "version": "2.0.0",
            "logs_exist": LOGS.exists(),
            "model_exists": (BASE / "models" / "active_model.pkl").exists(),
            "ts": time.time()}

@app.get("/api/summary")
def summary():
    return _cached("summary", 10, lambda: rj("phase1_summary.json") or {})

@app.get("/api/baseline")
def baseline():
    return _cached("baseline", 10, lambda: rj("baseline_metrics.json") or {})

@app.get("/api/drift")
def drift():
    return _cached("drift", 10, lambda: dedup(rj("drift_history.json") or []))

@app.get("/api/batches")
def batches():
    return _cached("batches", 10, lambda: dedup(rj("prediction_batches.json") or []))

@app.get("/api/monthly-sales")
def monthly_sales():
    def _build():
        b = dedup(rj("prediction_batches.json") or [])
        return [{"month": x["month"], "actual": x.get("mean_actual"),
                 "predicted": x.get("mean_pred"),
                 "mae": abs((x.get("mean_actual") or 0) - (x.get("mean_pred") or 0))} for x in b]
    return _cached("monthly_sales", 10, _build)

@app.get("/api/store-stats")
def store_stats():
    return _cached("store_stats", 120, _build_store_stats)

@app.get("/api/training-log")
def training_log():
    return _cached("training_log", 60, lambda: rj("training_log.json") or {})

@app.get("/api/feature-importances")
def feature_importances():
    def _build():
        summary_fn = (rj("phase1_summary.json") or {}).get("feature_names", [])
        model_path = BASE / "models" / "active_model.pkl"
        if not model_path.exists():
            raise HTTPException(404, "Model not found")
        model = joblib.load(str(model_path))
        fi = getattr(model, "feature_importances_", None)
        if fi is None:
            # unwrap stacking — try base estimators
            for attr in ["estimators_", "named_estimators_"]:
                est = getattr(model, attr, None)
                if est is not None:
                    candidates = list(est.values()) if isinstance(est, dict) else [e for _, e in est]
                    for e in candidates:
                        fi = getattr(e, "feature_importances_", None)
                        if fi is not None: break
                if fi is not None: break
        if fi is None:
            raise HTTPException(404, "Model has no feature_importances_")
        fi = [float(v) for v in fi]
        raw_fn = getattr(model, "feature_names_in_", None) or getattr(model, "_feature_names_in", None)
        # Cast to list to satisfy the linter's indexing requirements
        s_fn = list(summary_fn)
        fn = list(raw_fn) if raw_fn is not None else s_fn[:len(fi)]
        result = {str(n): np.round(float(v), 6) for n, v in zip(fn, fi)}
        return {"importances": result, "feature_names": [str(n) for n in fn]}
    return _cached("feature_importances", 600, _build)

@app.get("/api/data-split")
def data_split():
    return _cached("data_split", 60, lambda: rj("data_split.json") or {})

@app.get("/api/data-inspection")
def data_inspection():
    return _cached("data_inspection", 60, lambda: rj("data_inspection.json") or {})

@app.get("/api/processed-months")
def processed_months():
    def _build():
        months = set()
        for f in (BASE / "processed").glob("predictions_*.csv"):
            parts = f.stem.split("_")
            if len(parts) >= 2:
                months.add(parts[1])
        return sorted(months)
    return _cached("processed_months", 30, _build)

@app.get("/api/predictions-meta")
def predictions_meta():
    result = {}
    for f in PROCESSED.glob("predictions_*.csv"):
        parts = f.stem.split("_")
        if len(parts) >= 2:
            month = parts[1]
            mtime = f.stat().st_mtime
            if month not in result or mtime > result[month]:
                result[month] = np.round(float(mtime), 3)
    return result

@app.get("/api/predictions/{month}")
def predictions(month: str):
    if not month.replace("-", "").isalnum():
        raise HTTPException(400, "Invalid month format")
    files = sorted(PROCESSED.glob(f"predictions_{month}_*.csv"), key=lambda f: f.stat().st_mtime)
    if not files: raise HTTPException(404, "No predictions for this month")
    df = pd.read_csv(files[-1])
    for col in ["CI_Lower", "CI_Upper", "Abs_Error", "Error_Pct"]:
        if col not in df.columns:
            if col == "Abs_Error" and "Demand" in df.columns and "Predicted" in df.columns:
                df[col] = (df["Demand"] - df["Predicted"]).abs().round(2)
            elif col == "Error_Pct" and "Demand" in df.columns and "Predicted" in df.columns:
                df[col] = (df["Abs_Error"] / (df["Demand"].abs() + 1e-9) * 100).round(2)
            else:
                df[col] = None
    return df.to_dict(orient="records")

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
    # Slicing the list directly
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
    return _cached("datasets", 10, _build)

@app.get("/api/demand-metrics")
def demand_metrics():
    try: return _cached("demand_metrics", 600, _build_demand_metrics)
    except Exception as e: raise HTTPException(404, f"No data available: {e}")

@app.get("/api/demand-trend")
def demand_trend():
    try: return _cached("demand_trend", 600, _build_demand_trend)
    except Exception as e: raise HTTPException(404, f"No data available: {e}")

@app.get("/api/monthly-demand")
def monthly_demand():
    try: return _cached("monthly_demand", 600, _build_monthly_demand)
    except Exception as e: raise HTTPException(404, f"No data available: {e}")

@app.get("/api/store-demand")
def store_demand():
    try: return _cached("store_demand", 600, _build_store_demand)
    except Exception as e: raise HTTPException(404, f"No data available: {e}")

@app.get("/api/product-demand")
def product_demand():
    def _build():
        a = _get_analyzer()
        df = a.get_product_demand_data()
        if df is None or df.empty: return {"products": [], "demand": []}
        return {"products": df["Product"].tolist(), "demand": df["Demand"].tolist()}
    try: return _cached("product_demand", 600, _build)
    except Exception as e: raise HTTPException(404, f"No data available: {e}")

@app.get("/api/product-forecast")
def product_forecast():
    """Per-product forecast accuracy across all test months."""
    def _build():
        frames = []
        for f in _latest_processed_files():
            try:
                df = pd.read_csv(f)
                if {"Product", "Demand", "Predicted"}.issubset(df.columns):
                    frames.append(df[[c for c in ["Product","Demand","Predicted"] if c in df.columns]])
            except Exception: pass
        if not frames: return []
        df = pd.concat(frames, ignore_index=True)
        df["abs_err"] = (df["Demand"] - df["Predicted"]).abs()
        df["err_pct"] = df["abs_err"] / (df["Demand"].abs() + 1e-9) * 100
        agg = df.groupby("Product").agg(
            avg_demand=("Demand", "mean"), avg_predicted=("Predicted", "mean"),
            mae=("abs_err", "mean"), mape=("err_pct", "mean"),
            total_demand=("Demand", "sum"), count=("Demand", "count"),
        ).reset_index()
        pnames = _get_product_names()
        def _safe_name(pid):
            try: return f"Product {int(float(str(pid)))}"
            except: return f"Product {str(pid)}"
        agg["name"] = agg["Product"].map(pnames).fillna(agg["Product"].apply(_safe_name))
        agg["accuracy"] = np.clip(100 - agg["mape"].astype(float), 0, 100)
        return agg.round(2).to_dict(orient="records")
    return _cached("product_forecast", 300, _build)

@app.get("/api/product-monthly")
def product_monthly():
    """Monthly forecast vs actual per product."""
    def _build():
        frames = []
        for f in _latest_processed_files():
            try:
                df = pd.read_csv(f)
                if {"Product", "Demand", "Predicted", "Date"}.issubset(df.columns):
                    df["month"] = pd.to_datetime(df["Date"]).dt.to_period("M").astype(str)
                    frames.append(df[["Product", "Demand", "Predicted", "month"]])
            except Exception: pass
        if not frames: return []
        df = pd.concat(frames, ignore_index=True)
        agg = df.groupby(["month", "Product"]).agg(
            demand=("Demand", "mean"), predicted=("Predicted", "mean"),
        ).reset_index()
        pnames = _get_product_names()
        agg["name"] = agg["Product"].map(pnames).fillna(agg["Product"].apply(lambda x: f"Product {int(x)}"))
        return agg.round(2).to_dict(orient="records")
    return _cached("product_monthly", 300, _build)

@app.get("/api/product-names")
def product_names():
    return _cached("product_names", 300, _get_product_names)

@app.get("/api/store-names")
def store_names():
    def _build():
        data_file = DATA / "uploaded_data.csv"
        if not data_file.exists():
            return {}
        try:
            df = pd.read_csv(data_file, encoding="utf-8-sig", usecols=["Store"])
            stores = sorted(df["Store"].dropna().unique())
            return {str(int(float(s))): f"Store {int(float(s))}" for s in stores}
        except Exception:
            return {}
    return _cached("store_names", 300, _build)

@app.get("/api/store-forecast")
def store_forecast():
    """Per-store, per-product forecast accuracy across all test months."""
    def _build():
        frames = []
        for f in _latest_processed_files():
            try:
                df = pd.read_csv(f)
                if {"Store", "Product", "Demand", "Predicted"}.issubset(df.columns):
                    frames.append(df[["Store", "Product", "Demand", "Predicted"]])
            except Exception:
                pass
        if not frames:
            return []
        df = pd.concat(frames, ignore_index=True)
        df["abs_err"] = (df["Demand"] - df["Predicted"]).abs()
        df["err_pct"] = df["abs_err"] / (df["Demand"].abs() + 1e-9) * 100
        agg = df.groupby(["Store", "Product"]).agg(
            avg_demand=("Demand", "mean"),
            avg_predicted=("Predicted", "mean"),
            mae=("abs_err", "mean"),
            mape=("err_pct", "mean"),
            count=("Demand", "count"),
        ).reset_index()
        pnames = _get_product_names()
        agg["name"] = agg["Product"].map(pnames).fillna(agg["Product"].apply(lambda x: f"Product {int(x)}"))
        agg["accuracy"] = (100 - agg["mape"]).clip(0, 100)
        return agg.round(2).to_dict(orient="records")
    return _cached("store_forecast", 300, _build)

@app.get("/api/store-monthly")
def store_monthly():
    """Monthly forecast vs actual per store (aggregated across products)."""
    def _build():
        frames = []
        for f in _latest_processed_files():
            try:
                df = pd.read_csv(f)
                if {"Store", "Demand", "Predicted", "Date"}.issubset(df.columns):
                    df["month"] = pd.to_datetime(df["Date"]).dt.to_period("M").astype(str)
                    frames.append(df[["Store", "Demand", "Predicted", "month"]])
            except Exception:
                pass
        if not frames:
            return []
        df = pd.concat(frames, ignore_index=True)
        agg = df.groupby(["month", "Store"]).agg(
            demand=("Demand", "mean"),
            predicted=("Predicted", "mean"),
        ).reset_index()
        return agg.round(2).to_dict(orient="records")
    return _cached("store_monthly", 300, _build)

@app.get("/api/store-drift")
def store_drift():
    """Per-store MAE per test month from processed prediction CSVs."""
    def _build():
        frames = []
        for f in _latest_processed_files():
            try:
                df = pd.read_csv(f)
                if {"Store", "Demand", "Predicted", "Date"}.issubset(df.columns):
                    df["month"] = pd.to_datetime(df["Date"]).dt.to_period("M").astype(str)
                    df["abs_err"] = (df["Demand"] - df["Predicted"]).abs()
                    frames.append(df[["Store", "month", "abs_err", "Demand", "Predicted"]])
            except Exception:
                pass
        if not frames:
            return []
        df = pd.concat(frames, ignore_index=True)
        agg = df.groupby(["Store", "month"]).agg(
            mae=("abs_err", "mean"),
            avg_demand=("Demand", "mean"),
            avg_predicted=("Predicted", "mean"),
            count=("Demand", "count"),
        ).reset_index()
        agg["error_pct"] = (agg["mae"] / (agg["avg_demand"].abs() + 1e-9) * 100).round(2)
        return agg.round(2).to_dict(orient="records")
    return _cached("store_drift", 300, _build)

@app.get("/api/detected-columns")
def detected_columns():
    """Return what columns the system detected in the uploaded data."""
    insp = rj("data_inspection.json") or {}
    return {
        "columns": insp.get("columns", []),
        "detected": insp.get("detected_columns", {}),
        "user_features": insp.get("user_features", []),
    }

@app.get("/api/dataset-summary")
def dataset_summary():
    """Aggregated stats from the pipeline training data for comparison."""
    def _build():
        insp = rj("data_inspection.json") or {}
        split = rj("data_split.json") or {}
        batches = dedup(rj("prediction_batches.json") or [])
        stats = insp.get("demand_stats") or insp.get("weekly_sales_stats") or {}
        monthly_avg = []
        for b in batches:
            monthly_avg.append({"month": b["month"], "mean_actual": b.get("mean_actual"), "mean_pred": b.get("mean_pred")})
        return {
            "rows": insp.get("rows", 0),
            "stores": insp.get("stores", 0),
            "date_range": insp.get("date_range", []),
            "demand_mean": stats.get("mean", 0),
            "demand_min": stats.get("min", 0),
            "demand_max": stats.get("max", 0),
            "train_rows": split.get("train_rows", 0),
            "test_rows": split.get("test_rows", 0),
            "monthly_avg": monthly_avg,
        }
    return _cached("dataset_summary", 120, _build)

@app.post("/api/upload-monitor")
async def upload_monitor(file: UploadFile = File(...)):
    """Upload CSV → score against existing model → full drift analysis + healing actions. No retraining."""
    if not file.filename or not file.filename.lower().endswith(".csv"):
        raise HTTPException(400, "Only .csv files are accepted")
    if not (BASE / "models" / "active_model.pkl").exists():
        raise HTTPException(422, "No trained model found. Run the full pipeline first via main.py.")
    content = await file.read()
    if len(content) > 50 * 1024 * 1024:
        raise HTTPException(413, "File too large (max 50 MB)")
    safe_name = Path(file.filename).name
    dest = UPLOAD / safe_name
    UPLOAD.mkdir(exist_ok=True)
    if isinstance(content, str): content = content.encode("utf-8")
    with open(dest, "wb") as f: f.write(content)
    try:
        import io
        clean_df = pd.read_csv(io.BytesIO(content), encoding="utf-8-sig")
        clean_df.columns = clean_df.columns.str.strip()
        clean_df.to_csv(dest, index=False)
    except Exception:
        pass
    import asyncio
    loop = asyncio.get_event_loop()
    try:
        from main import run_monitor_pipeline
        def _run(): return run_monitor_pipeline(str(dest))
        summary = await loop.run_in_executor(None, _run)
    except Exception as e:
        raise HTTPException(422, str(e))
    _bust()
    return {"status": "ok", "summary": summary}


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
    try:
        clean_df = pd.read_csv(dest, encoding="utf-8-sig")
        clean_df.columns = clean_df.columns.str.strip()
        clean_df.to_csv(dest, index=False)
    except Exception:
        pass
    shutil.copy(dest, DATA / "uploaded_data.csv")
    import asyncio
    loop = asyncio.get_event_loop()
    try:
        def _run_sub():
            return subprocess.run(
                [sys.executable, str(BASE / "main.py")],
                capture_output=True, text=True, timeout=1200, cwd=str(BASE)
            )
        result = await asyncio.wait_for(
            loop.run_in_executor(None, _run_sub),
            timeout=1220
        )
    except asyncio.TimeoutError:
        raise HTTPException(504, "Pipeline timed out after 20 minutes.")
    if result.returncode != 0:
        stdout_val = result.stdout or ""
        stderr_val = result.stderr or ""
        combined = (str(stdout_val) + "\n" + str(stderr_val))[-3000:]
        error_line = ""
        for line in reversed(combined.splitlines()):
            line = line.strip()
            if not line: continue
            if any(x in line for x in ["ValueError", "FileNotFoundError", "KeyError",
                                        "Missing required", "too small", "Error:", "error:"]):
                error_line = line; break
        if not error_line:
            for line in reversed(combined.splitlines()):
                if line.strip(): error_line = line.strip(); break
        raise HTTPException(422, error_line or "Pipeline failed — check backend terminal")
    _bust()
    stdout_val = result.stdout or ""
    return {"status": "ok", "stdout": stdout_val[-1000:]}



@app.get("/api/test-metrics")
def test_metrics():
    """Compute real test set metrics from all processed prediction CSVs."""
    def _build():
        frames = []
        for f in sorted(PROCESSED.glob("predictions_*.csv")):
            try:
                df = pd.read_csv(f)
                if {"Demand", "Predicted"}.issubset(df.columns):
                    frames.append(df[["Demand", "Predicted"]])
            except Exception:
                pass
        if not frames:
            return {}
        df = pd.concat(frames, ignore_index=True).dropna()
        y, p = df["Demand"].values, df["Predicted"].values
        mae  = float(abs(y - p).mean())
        rmse = float(((y - p) ** 2).mean() ** 0.5)
        mape = float((abs(y - p) / (abs(y) + 1e-9) * 100).mean())
        wmape= float(abs(y - p).sum() / (abs(y).sum() + 1e-9) * 100)
        mean_y = float(y.mean())
        ss_tot = float(((y - mean_y) ** 2).sum())
        ss_res = float(((y - p) ** 2).sum())
        r2   = float((1 - ss_res / ss_tot) * 100) if ss_tot > 0 else 100.0
        split = rj("data_split.json") or {}
        return {
            "accuracy": np.round(max(0.0, 100.0 - float(mape)), 1),
            "n_rows": int(len(df)),
            "test_year": split.get("test_year"),
            "train_years": split.get("train_years", []),
        }
    return _cached("test_metrics", 10, _build)


@app.get("/api/healing-actions")
def healing_actions():
    def _build():
        summary = rj("phase1_summary.json") or {}
        hs = dict(summary.get("healing_stats", {}))
        return {
            "total_actions": hs.get("total_actions", 0),
            "monitor_only": hs.get("monitor_only", 0),
            "fine_tuned": hs.get("fine_tuned", 0),
            "retrained": hs.get("retrained", 0),
            "rollbacks": hs.get("rollbacks", 0),
            "avg_improvement": summary.get("avg_improvement", 0.0),
            "recommendation": summary.get("recommendation", "No data"),
        }
    return _cached("healing_actions", 120, _build)

@app.get("/api/healing-history")
def healing_history():
    return _cached("healing_history", 60, lambda: dedup(rj("healing_history.json") or []))

@app.get("/api/healing-status")
def healing_status():
    def _build():
        from healing_status import HealingStatusIndicator
        indicator = HealingStatusIndicator()
        return indicator.get_current_status()
    return _cached("healing_status", 30, _build)


# ── Sequential Prediction Endpoints ───────────────────────────────────────────

@app.get("/api/seq/status")
def seq_status():
    """Get the current sequential prediction cycle status."""
    try:
        from sequential_predictor import SequentialPredictor
        sp = SequentialPredictor()
        return sp.get_status()
    except Exception as e:
        raise HTTPException(500, f"Status error: {e}")


@app.post("/api/seq/predict-next")
def seq_predict_next():
    """Predict the next month based on all available data."""
    try:
        from sequential_predictor import SequentialPredictor
        sp = SequentialPredictor()
        result = sp.predict_next_month()
        _bust()
        return result
    except Exception as e:
        raise HTTPException(422, f"Prediction failed: {e}")


@app.post("/api/seq/upload-actuals")
async def seq_upload_actuals(file: UploadFile = File(...)):
    """
    Upload ACTUAL data for a completed month (with Demand).
    Compares with predictions, then auto-predicts next month.
    Only requires: Date + Demand (or Sales/Weekly_Sales). Other columns auto-filled.
    """
    if not file.filename or not file.filename.lower().endswith(".csv"):
        raise HTTPException(400, "Only .csv files are accepted")
    content = await file.read()
    if len(content) > 50 * 1024 * 1024:
        raise HTTPException(413, "File too large (max 50 MB)")
    if isinstance(content, str): content = content.encode("utf-8")
    try:
        df = pd.read_csv(io.BytesIO(content), encoding="utf-8-sig")
        df.columns = df.columns.str.strip()
    except Exception as e:
        raise HTTPException(400, f"Failed to parse CSV: {e}")
    # Require Date + Product + Demand
    col_lower = [c.lower().replace(" ", "_") for c in df.columns]
    has_date    = any(c in ("date","week","order_date") for c in col_lower)
    has_product = any(c in ("product","item","product_id","item_id","sku","category","store","store_id") for c in col_lower)
    has_demand  = any(c in ("demand","sales","weekly_sales","units","quantity") for c in col_lower)
    missing = []
    if not has_date:   missing.append("Date")
    if not has_demand: missing.append("Demand")
    if missing:
        raise HTTPException(400, f"Missing required columns: {missing}. Need at least Date + Demand. Got: {list(df.columns)}")
    try:
        from sequential_predictor import SequentialPredictor
        import math
        sp = SequentialPredictor()
        result = sp.process_actuals_upload(df)
        _bust()
        # Sanitize NaN/Inf floats so JSON serialization never fails
        def _clean(obj):
            if isinstance(obj, float):
                return None if (math.isnan(obj) or math.isinf(obj)) else obj
            if isinstance(obj, dict):
                return {k: _clean(v) for k, v in obj.items()}
            if isinstance(obj, list):
                return [_clean(v) for v in obj]
            return obj
        return _clean(result)
    except Exception as e:
        raise HTTPException(422, f"Upload failed: {e}")


@app.get("/api/seq/drift-analysis")
def seq_drift_analysis():
    """Get comprehensive drift analysis from uploaded data."""
    try:
        from sequential_predictor import SequentialPredictor
        sp = SequentialPredictor()
        return sp.get_drift_analysis()
    except Exception as e:
        raise HTTPException(500, f"Drift analysis failed: {e}")


@app.get("/api/seq/prediction/{month}")
def seq_get_prediction(month: str):
    """Get saved predictions for a specific month."""
    if not month.replace("-", "").isalnum():
        raise HTTPException(400, "Invalid month format")
    try:
        from sequential_predictor import SequentialPredictor
        sp = SequentialPredictor()
        result = sp.get_prediction(month)
        if result is None:
            raise HTTPException(404, f"No predictions for {month}")
        # Sanitize NaN values for JSON serialization
        import math
        for p in result.get("predictions", []):
            for k, v in p.items():
                if isinstance(v, float) and math.isnan(v):
                    p[k] = None
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, str(e))


@app.get("/api/seq/comparison/{month}")
def seq_get_comparison(month: str):
    """Get predicted vs actual comparison for a specific month."""
    if not month.replace("-", "").isalnum():
        raise HTTPException(400, "Invalid month format")
    try:
        from sequential_predictor import SequentialPredictor
        sp = SequentialPredictor()
        result = sp.get_comparison(month)
        if result is None:
            raise HTTPException(404, f"No comparison for {month}")
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, str(e))


@app.get("/api/forecast-status")
def forecast_status():
    """Get the current state: last known month, next predictable month."""
    try:
        from sequential_predictor import SequentialPredictor
        sp = SequentialPredictor()
        return sp.get_status()
    except Exception as e:
        data_file = DATA / "uploaded_data.csv"
        if not data_file.exists():
            return {"status": "no_data", "message": "No data uploaded yet"}
        return {"status": "error", "message": str(e)}
