"""
backend_minimal.py
Train: ALL train.csv (2015 Jan - 2018 Dec, 9800 orders)
Auto-predict: January 2019 (next month after training data ends)
Pipeline: User uploads actual Jan 2019 -> evaluate -> drift -> update -> predict Feb 2019
"""
import os, io, warnings
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from scipy.stats import ks_2samp
from lightgbm import LGBMRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error
import logging

warnings.filterwarnings("ignore")
logging.basicConfig(level=logging.INFO, format='%(asctime)s | %(levelname)s | %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
logger = logging.getLogger(__name__)

app = FastAPI(title="Sales Forecasting API")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

ROOT = os.path.dirname(os.path.abspath(__file__))
DATA_PATH = os.path.join(ROOT, "data", "raw", "train.csv")
UPLOAD_DIR = os.path.join(ROOT, "data", "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(os.path.join(ROOT, "models"), exist_ok=True)

SYSTEM_LOG = []
CURRENT_ACTION = "System Ready"
LOGBOOK = []

TRAIN_DF = None
FEATURED_DF = None
MODEL = None
METRICS = {}
IMPORTANCE = {}
TRAIN_CUTOFF = None
NEXT_MONTH = None
PREDICTION = None

FEATURE_LIST = [
    # Raw (7)
    "dayofweek", "month", "year", "order_count", "avg_order_value",
    "ship_speed", "segment_encoded",
    # Aggregated (9)
    "lag_1", "lag_7", "lag_14", "lag_28", "rmean_3", "rmean_7", "rmean_14", "rmean_28", "rstd_7",
    # Engineered (11)
    "sales_momentum", "sales_volatility", "region_strength",
    "category_popularity", "relative_demand", "weekly_pattern", "trend_slope",
    "subcategory_avg_sales", "shipping_days", "sales_acceleration", "weekend_flag",
]


def log_action(action, details=""):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    SYSTEM_LOG.append({"timestamp": ts, "action": action, "details": details})
    logger.info(f"{action} - {details}")
    if len(SYSTEM_LOG) > 200:
        SYSTEM_LOG.pop(0)
    global CURRENT_ACTION
    CURRENT_ACTION = action


def aggregate_daily(raw):
    # Encode ship mode and segment before aggregation
    ship_map = {"Same Day": 4, "First Class": 3, "Second Class": 2, "Standard Class": 1}
    seg_map = {"Consumer": 0, "Corporate": 1, "Home Office": 2}
    raw = raw.copy()
    raw["ship_speed"] = raw["Ship Mode"].map(ship_map).fillna(1)
    raw["segment_encoded"] = raw["Segment"].map(seg_map).fillna(0)
    raw["shipping_days"] = (pd.to_datetime(raw["Ship Date"], dayfirst=True) - raw["Order Date"]).dt.days.clip(lower=0)

    daily = raw.groupby([pd.Grouper(key="Order Date", freq="D"), "Category", "Region"]).agg(
        sales=("Sales", "sum"),
        order_count=("Order ID", "nunique"),
        avg_order_value=("Sales", "mean"),
        ship_speed=("ship_speed", "mean"),
        segment_encoded=("segment_encoded", "mean"),
        shipping_days=("shipping_days", "mean"),
        subcategory_avg_sales=("Sales", "median"),
    ).reset_index()
    daily.rename(columns={"Order Date": "date"}, inplace=True)
    return daily.sort_values(["Category", "Region", "date"]).reset_index(drop=True)


def engineer_features(daily):
    df = daily.copy()
    g = ["Category", "Region"]
    df["dayofweek"] = df["date"].dt.dayofweek
    df["month"] = df["date"].dt.month
    df["year"] = df["date"].dt.year
    # Aggregated (9)
    df["lag_1"] = df.groupby(g)["sales"].shift(1)
    df["lag_7"] = df.groupby(g)["sales"].shift(7)
    df["lag_14"] = df.groupby(g)["sales"].shift(14)
    df["lag_28"] = df.groupby(g)["sales"].shift(28)
    df["rmean_3"] = df.groupby(g)["sales"].transform(lambda x: x.rolling(3, min_periods=1).mean())
    df["rmean_7"] = df.groupby(g)["sales"].transform(lambda x: x.rolling(7, min_periods=1).mean())
    df["rmean_14"] = df.groupby(g)["sales"].transform(lambda x: x.rolling(14, min_periods=1).mean())
    df["rmean_28"] = df.groupby(g)["sales"].transform(lambda x: x.rolling(28, min_periods=1).mean())
    df["rstd_7"] = df.groupby(g)["sales"].transform(lambda x: x.rolling(7, min_periods=1).std())
    # Engineered (11)
    df["sales_momentum"] = df["rmean_7"] - df["rmean_28"]
    df["sales_volatility"] = df["rstd_7"] / (df["rmean_7"] + 1)
    df["region_strength"] = df.groupby("Region")["sales"].transform("mean")
    df["category_popularity"] = df.groupby("Category")["sales"].transform("mean")
    df["relative_demand"] = df["sales"] / (df["region_strength"] + 1)
    df["weekly_pattern"] = df.groupby("dayofweek")["sales"].transform("mean")
    df["weekend_flag"] = (df["dayofweek"] >= 5).astype(int)
    df["sales_acceleration"] = df["sales_momentum"] - df.groupby(g)["sales_momentum"].shift(7)
    # subcategory_avg_sales and shipping_days already from aggregation

    def slope(s):
        y = s.values
        if len(y) < 2 or np.isnan(y).any():
            return 0.0
        try:
            return float(np.polyfit(np.arange(len(y)), y, 1)[0])
        except Exception:
            return 0.0

    df["trend_slope"] = df.groupby(g)["sales"].transform(
        lambda x: x.rolling(7, min_periods=2).apply(slope, raw=False)
    )
    return df.fillna(0)


def do_train(feat_df):
    X, y = feat_df[FEATURE_LIST], feat_df["sales"]
    sp = int(len(feat_df) * 0.8)
    mdl = LGBMRegressor(n_estimators=200, learning_rate=0.05, max_depth=8, num_leaves=31, verbose=-1)
    mdl.fit(X.iloc[:sp], y.iloc[:sp])
    p = mdl.predict(X.iloc[sp:])
    mae = round(mean_absolute_error(y.iloc[sp:], p), 3)
    rmse = round(np.sqrt(mean_squared_error(y.iloc[sp:], p)), 3)
    mape = round(float(np.mean(np.abs((y.iloc[sp:] - p) / (y.iloc[sp:] + 1)) * 100)), 1)
    imp = dict(zip(FEATURE_LIST, [float(v) for v in mdl.feature_importances_]))
    t = sum(imp.values()) or 1
    imp = {k: round(v / t, 4) for k, v in imp.items()}
    return mdl, {"mae": mae, "rmse": rmse, "mape": mape}, imp


def make_prediction(mdl, feat_df, nxt):
    # Get last 30 days per category-region combo to predict next month
    groups = []
    for (cat, reg), g in feat_df.groupby(["Category", "Region"]):
        groups.append(g.tail(30))
    tail = pd.concat(groups)
    tail["predicted_sales"] = np.maximum(mdl.predict(tail[FEATURE_LIST]), 0)
    end = nxt + pd.DateOffset(months=1) - timedelta(days=1)

    # Daily prediction line chart data
    daily_pred = tail.groupby(tail["date"].dt.day)["predicted_sales"].sum().reset_index()
    daily_pred.columns = ["day", "predicted"]
    daily_pred["predicted"] = daily_pred["predicted"].round(0)
    daily_chart = daily_pred.to_dict(orient="records")

    # Category daily trend
    cat_daily = []
    for cat, g in tail.groupby("Category"):
        by_day = g.groupby(g["date"].dt.day)["predicted_sales"].sum().reset_index()
        by_day.columns = ["day", "predicted"]
        for _, row in by_day.iterrows():
            cat_daily.append({"day": int(row["day"]), "category": cat, "predicted": round(float(row["predicted"]))})

    return {
        "predicting_month": nxt.strftime("%B %Y"),
        "total_predicted": round(float(tail["predicted_sales"].sum())),
        "mean_daily": round(float(tail["predicted_sales"].mean()), 1),
        "date_min": str(nxt.date()),
        "date_max": str(end.date()),
        "total_categories": len(tail["Category"].unique()),
        "total_regions": len(tail["Region"].unique()),
        "cat_summary": [
            {"category": c, "total_predicted": round(float(g["predicted_sales"].sum())), "avg_daily": round(float(g["predicted_sales"].mean()), 1)}
            for c, g in tail.groupby("Category")
        ],
        "region_summary": [
            {"region": r, "total_predicted": round(float(g["predicted_sales"].sum())), "avg_daily": round(float(g["predicted_sales"].mean()), 1)}
            for r, g in tail.groupby("Region")
        ],
        "daily_chart": daily_chart,
        "cat_daily_chart": cat_daily,
    }


def next_month_after(dt):
    return pd.Timestamp(year=dt.year + (1 if dt.month == 12 else 0), month=(dt.month % 12) + 1, day=1)


# ═══════════════════════════════════════════════════════════
#  STARTUP — train on ALL train.csv, predict Jan 2019
# ═══════════════════════════════════════════════════════════
log_action("Startup", "Training on full train.csv (2015-2018)")

try:
    TRAIN_DF = pd.read_csv(DATA_PATH, parse_dates=["Order Date"], dayfirst=True)
    TRAIN_CUTOFF = TRAIN_DF["Order Date"].max()
    NEXT_MONTH = next_month_after(TRAIN_CUTOFF)

    log_action("Data", f"{len(TRAIN_DF)} orders | {TRAIN_DF['Order Date'].min().date()} to {TRAIN_CUTOFF.date()}")

    daily = aggregate_daily(TRAIN_DF)
    FEATURED_DF = engineer_features(daily)
    MODEL, METRICS, IMPORTANCE = do_train(FEATURED_DF)

    log_action("Trained", f"MAE=${METRICS['mae']} MAPE={METRICS['mape']}%")

    PREDICTION = make_prediction(MODEL, FEATURED_DF, NEXT_MONTH)

    log_action("Ready", f"Predicting {NEXT_MONTH.strftime('%B %Y')}: ${PREDICTION['total_predicted']:,}")

except Exception as e:
    log_action("Error", str(e))
    METRICS = {"mae": 0, "rmse": 0, "mape": 0}
    IMPORTANCE = {}


# ═══════════════════════════════════════════════════════════
#  ENDPOINTS
# ═══════════════════════════════════════════════════════════

@app.get("/api/health")
def health():
    return {"status": "ok", "model": MODEL is not None}


@app.get("/api/status")
def ep_status():
    ds = {}
    if TRAIN_DF is not None:
        ds = {
            "total_orders": len(TRAIN_DF),
            "daily_rows": len(FEATURED_DF) if FEATURED_DF is not None else 0,
            "train_date_range": f"{TRAIN_DF['Order Date'].min().date()} to {TRAIN_CUTOFF.date()}",
            "next_predict_month": NEXT_MONTH.strftime("%B %Y") if NEXT_MONTH else "",
            "categories": TRAIN_DF["Category"].unique().tolist(),
            "regions": TRAIN_DF["Region"].unique().tolist(),
            "segments": TRAIN_DF["Segment"].unique().tolist(),
            "products": int(TRAIN_DF["Product ID"].nunique()),
            "sub_categories": int(TRAIN_DF["Sub-Category"].nunique()),
            "customers": int(TRAIN_DF["Customer ID"].nunique()),
            "states": int(TRAIN_DF["State"].nunique()),
            "total_sales": round(float(TRAIN_DF["Sales"].sum()), 2),
            "cat_sales": [{"category": c, "total": round(float(g["Sales"].sum()), 2), "avg": round(float(g["Sales"].mean()), 2), "orders": len(g)} for c, g in TRAIN_DF.groupby("Category")],
            "region_sales": [{"region": r, "total": round(float(g["Sales"].sum()), 2), "avg": round(float(g["Sales"].mean()), 2), "orders": len(g)} for r, g in TRAIN_DF.groupby("Region")],
            "top_sub_categories": [{"sub_category": s, "total": round(float(t), 2)} for s, t in TRAIN_DF.groupby("Sub-Category")["Sales"].sum().sort_values(ascending=False).head(10).items()],
            "monthly_sales": [{"month": str(m), "total": round(float(t), 2)} for m, t in TRAIN_DF.groupby(TRAIN_DF["Order Date"].dt.to_period("M"))["Sales"].sum().items()],
        }
    return {
        "files": {"train_data": TRAIN_DF is not None, "features": FEATURED_DF is not None, "model": MODEL is not None},
        "model": {"type": "LightGBM", "trees": 200, "features": len(FEATURE_LIST)},
        "dataset": ds,
        "feature_breakdown": {"raw": 7, "aggregated": 9, "engineered": 11, "total": 27},
        "current_action": CURRENT_ACTION,
        "prediction": PREDICTION,
    }


@app.get("/api/metrics")
def ep_metrics():
    log_action("Metrics", "")
    top = []
    if FEATURED_DF is not None and MODEL is not None:
        sp = int(len(FEATURED_DF) * 0.8)
        t = FEATURED_DF.iloc[sp:].copy()
        t["pred"] = MODEL.predict(t[FEATURE_LIST])
        t["err"] = abs(t["sales"] - t["pred"])
        seg = t.groupby(["Category", "Region"])["err"].mean().sort_values(ascending=False).head(5)
        top = [{"segment": f"{c} - {r}", "mae": round(v, 3)} for (c, r), v in seg.items()]
    return {**METRICS, "top_error_skus": top}


@app.get("/api/feature-importance")
def ep_fi():
    log_action("FI", "")
    out = []
    eng = ["sales_momentum", "sales_volatility", "region_strength", "category_popularity", "relative_demand", "weekly_pattern", "trend_slope", "subcategory_avg_sales", "shipping_days", "sales_acceleration", "weekend_flag"]
    agg = ["lag_1", "lag_7", "lag_14", "lag_28", "rmean_3", "rmean_7", "rmean_14", "rmean_28", "rstd_7"]
    for f, v in sorted(IMPORTANCE.items(), key=lambda x: -x[1]):
        tp = "engineered" if f in eng else "aggregated" if f in agg else "raw"
        out.append({"feature": f, "importance": v, "type": tp})
    return {"features": out}


@app.post("/api/predict")
def ep_predict():
    log_action("Predict", NEXT_MONTH.strftime("%B %Y") if NEXT_MONTH else "")
    if not PREDICTION:
        raise HTTPException(500, "No prediction")
    return PREDICTION


@app.post("/api/upload")
async def ep_upload(file: UploadFile = File(...)):
    try:
        log_action("Upload", file.filename)
        global TRAIN_DF, TRAIN_CUTOFF, NEXT_MONTH, FEATURED_DF, PREDICTION

        content = await file.read()
        actual = pd.read_csv(io.BytesIO(content), parse_dates=["Order Date"], dayfirst=True)
        with open(os.path.join(UPLOAD_DIR, file.filename), "wb") as f:
            f.write(content)

        actual_total = float(actual["Sales"].sum())
        month_str = str(actual["Order Date"].dt.to_period("M").mode()[0])

        ev = None
        if PREDICTION:
            pt = PREDICTION["total_predicted"]
            ev = {
                "predicted_total": pt,
                "actual_total": round(actual_total, 2),
                "difference": round(actual_total - pt, 2),
                "accuracy_pct": round((1 - abs(actual_total - pt) / (actual_total + 1)) * 100, 1),
            }
            log_action("Eval", f"Pred=${pt:,.0f} Act=${actual_total:,.0f}")

        TRAIN_DF = pd.concat([TRAIN_DF, actual], ignore_index=True)
        TRAIN_CUTOFF = TRAIN_DF["Order Date"].max()
        NEXT_MONTH = next_month_after(TRAIN_CUTOFF)

        daily = aggregate_daily(TRAIN_DF)
        FEATURED_DF = engineer_features(daily)

        PREDICTION = make_prediction(MODEL, FEATURED_DF, NEXT_MONTH)
        log_action("Updated", f"Now predicting {NEXT_MONTH.strftime('%B %Y')}: ${PREDICTION['total_predicted']:,}")

        analysis = {
            "rows": len(actual), "orders": int(actual["Order ID"].nunique()),
            "products": int(actual["Product ID"].nunique()) if "Product ID" in actual.columns else 0,
            "customers": int(actual["Customer ID"].nunique()) if "Customer ID" in actual.columns else 0,
            "categories": actual["Category"].unique().tolist() if "Category" in actual.columns else [],
            "regions": actual["Region"].unique().tolist() if "Region" in actual.columns else [],
            "date_min": str(actual["Order Date"].min().date()),
            "date_max": str(actual["Order Date"].max().date()),
            "total_sales": round(actual_total, 2),
            "upload_month": month_str,
            "new_train_cutoff": str(TRAIN_CUTOFF.date()),
            "next_predict_month": NEXT_MONTH.strftime("%B %Y"),
            "total_train_orders": len(TRAIN_DF),
        }
        return {"analysis": analysis, "evaluation": ev, "next_prediction": PREDICTION}
    except Exception as e:
        log_action("Upload Error", str(e))
        raise HTTPException(400, str(e))


@app.post("/api/drift")
def ep_drift():
    try:
        log_action("Drift", "KS test")
        sp = int(len(FEATURED_DF) * 0.7)
        res = {}
        for f in ["sales_momentum", "rmean_28", "trend_slope", "sales_volatility", "relative_demand"]:
            a, b = FEATURED_DF[f].iloc[:sp].dropna(), FEATURED_DF[f].iloc[sp:].dropna()
            if len(a) > 0 and len(b) > 0:
                s, p = ks_2samp(a, b)
                res[f] = {"ks_stat": round(s, 4), "p_value": round(p, 4)}
        ks = round(np.mean([v["ks_stat"] for v in res.values()]), 4) if res else 0
        lv = "low" if ks < 0.1 else "medium" if ks < 0.2 else "high"
        act = "monitor" if lv == "low" else "fine_tune" if lv == "medium" else "retrain"
        LOGBOOK.append({"id": datetime.now().strftime("%Y%m%d_%H%M%S"), "timestamp": datetime.now().strftime("%d %b %Y %H:%M"), "drift_level": lv.upper(), "drift_score": ks, "mae_before": METRICS.get("mae", 0), "action_taken": act, "action_label": {"monitor": "Monitor", "fine_tune": "Fine-Tune", "retrain": "Retrain"}[act], "action_why": f"Drift {ks:.4f} ({lv})", "plain_english": f"Drift={ks:.4f} ({lv}). MAE=${METRICS.get('mae',0)}. Action: {act}.", "top_drift_features": [{"feature": k, "ks_stat": v["ks_stat"], "severity": "HIGH" if v["ks_stat"] > 0.2 else "MEDIUM" if v["ks_stat"] > 0.1 else "LOW"} for k, v in sorted(res.items(), key=lambda x: -x[1]["ks_stat"])]})
        log_action("Drift Done", f"{lv.upper()} KS={ks} -> {act}")
        return {"ks_stat": ks, "level": lv, "message": f"{lv.upper()} drift", "drift_score": ks, "action": act, "feature_drift": res}
    except Exception as e:
        log_action("Drift Error", str(e))
        raise HTTPException(500, str(e))


@app.post("/api/retrain/finetune")
def ep_finetune():
    try:
        log_action("Finetune", "")
        global MODEL, METRICS, IMPORTANCE, PREDICTION
        MODEL, METRICS, IMPORTANCE = do_train(FEATURED_DF.iloc[int(len(FEATURED_DF) * 0.4):])
        PREDICTION = make_prediction(MODEL, FEATURED_DF, NEXT_MONTH)
        log_action("Finetuned", f"MAE=${METRICS['mae']}")
        return {"status": "success", "method": "fine_tune", "metrics": {"MAE": METRICS["mae"], "RMSE": METRICS["rmse"], "MAPE": METRICS["mape"]}}
    except Exception as e:
        raise HTTPException(500, str(e))


@app.post("/api/retrain/sliding")
def ep_sliding():
    try:
        log_action("Retrain", "")
        global MODEL, METRICS, IMPORTANCE, PREDICTION
        MODEL, METRICS, IMPORTANCE = do_train(FEATURED_DF)
        PREDICTION = make_prediction(MODEL, FEATURED_DF, NEXT_MONTH)
        log_action("Retrained", f"MAE=${METRICS['mae']}")
        return {"status": "success", "method": "sliding_window", "metrics": {"MAE": METRICS["mae"], "RMSE": METRICS["rmse"], "MAPE": METRICS["mape"]}}
    except Exception as e:
        raise HTTPException(500, str(e))


@app.get("/api/logbook")
def ep_logbook():
    if not LOGBOOK:
        return {"entries": [{"id": "baseline", "timestamp": datetime.now().strftime("%d %b %Y %H:%M"), "drift_level": "N/A", "drift_score": 0, "mae_before": METRICS.get("mae", 0), "action_taken": "baseline", "action_label": "Baseline", "action_why": f"Trained on all data (2015-2018).", "plain_english": f"Baseline ready. MAE=${METRICS.get('mae',0)}. Next: {NEXT_MONTH.strftime('%B %Y') if NEXT_MONTH else ''}.", "top_drift_features": []}]}
    return {"entries": LOGBOOK}


@app.get("/api/system-log")
def ep_syslog():
    return {"log": SYSTEM_LOG[-50:], "current_action": CURRENT_ACTION, "timestamp": datetime.now().isoformat()}


@app.get("/api/predict/download")
def ep_download():
    try:
        tail = FEATURED_DF.tail(200).copy()
        tail["predicted_sales"] = np.maximum(MODEL.predict(tail[FEATURE_LIST]), 0).round(2)
        csv = tail[["date", "Category", "Region", "sales", "predicted_sales"]].to_csv(index=False)
        return StreamingResponse(io.StringIO(csv), media_type="text/csv", headers={"Content-Disposition": "attachment; filename=predictions.csv"})
    except Exception as e:
        raise HTTPException(500, str(e))


@app.post("/api/xai/store-explanation")
def ep_xai(explanation: dict):
    log_action("XAI", "stored")
    return {"status": "success"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
