"""
FastAPI Backend - Demand Forecasting
SHAP explainability, logbook, next-month upload prompt.
"""
import os, sys, io, base64, calendar
import joblib
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pipelines.utils import PROCESSED_DIR, MODEL_DIR
from pipelines._drift import run_drift_check
from pipelines._06_retrain import fine_tune, sliding_window_retrain, predict_next_month
from pipelines._03_features import create_features_for_new_data
from pipelines._explain import (
    get_shap_explanation, save_to_logbook,
    load_logbook, build_logbook_entry
)

REPORT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "reports")

app = FastAPI(title="Demand Forecasting API")
app.add_middleware(CORSMiddleware, allow_origins=["*"],
                   allow_methods=["*"], allow_headers=["*"])

# ── Helpers ──────────────────────────────────────────────
def fig_to_b64(fig):
    buf = io.BytesIO()
    fig.savefig(buf, format="png", bbox_inches="tight", dpi=110)
    buf.seek(0)
    enc = base64.b64encode(buf.read()).decode()
    plt.close(fig)
    return enc

def dark(fig, axes):
    fig.patch.set_facecolor("#1e1e2e")
    for ax in (axes if hasattr(axes, "__iter__") else [axes]):
        ax.set_facecolor("#1e1e2e")
        ax.tick_params(colors="#cdd6f4")
        for sp in ax.spines.values():
            sp.set_edgecolor("#45475a")

def load_last_drift():
    drift_log = os.path.join(REPORT_DIR, "drift_history.csv")
    if os.path.exists(drift_log):
        try:
            df  = pd.read_csv(drift_log)
            if not df.empty:
                row = df.iloc[-1].to_dict()
                fd  = {k.replace("psi_",""):v for k,v in row.items() if k.startswith("psi_")}
                return {"ks_stat": row.get("ks_stat"), "psi": row.get("psi"),
                        "mae": row.get("mae"), "drift_score": row.get("drift_score"),
                        "level": row.get("level","unknown"), "feature_drift": fd}
        except Exception:
            pass
    return {"ks_stat":None,"psi":None,"mae":None,
            "drift_score":None,"level":"unknown","feature_drift":{}}

def get_current_metrics():
    try:
        pp = f"{PROCESSED_DIR}/predictions.parquet"
        fp = f"{PROCESSED_DIR}/features.parquet"
        if not os.path.exists(pp) or not os.path.exists(fp):
            return None
        preds = pd.read_parquet(pp)
        hist  = pd.read_parquet(fp)[["id","date","sales"]]
        perf  = hist.merge(preds, on=["id","date"], how="inner")
        perf["ae"] = (perf["sales"] - perf["yhat"]).abs()
        perf["se"] = (perf["sales"] - perf["yhat"]) ** 2
        return {"MAE": round(float(perf["ae"].mean()),4),
                "RMSE": round(float(np.sqrt(perf["se"].mean())),4)}
    except Exception:
        return None

# ── Health ────────────────────────────────────────────────
@app.get("/api/health")
def health():
    return {"status": "ok"}

# ── Pipeline Status ───────────────────────────────────────
@app.get("/api/status")
def status():
    files = {
        "raw_merged" : f"{PROCESSED_DIR}/raw_merged.parquet",
        "features"   : f"{PROCESSED_DIR}/features.parquet",
        "predictions": f"{PROCESSED_DIR}/predictions.parquet",
        "model"      : f"{MODEL_DIR}/model.pkl",
    }
    ok = {k: os.path.exists(v) for k,v in files.items()}
    model_info = {}
    if ok["model"]:
        m = joblib.load(f"{MODEL_DIR}/model.pkl")
        model_info = {"type":"LightGBM","trees":int(m.n_estimators_),
                      "features":int(m.n_features_in_)}
    return {"files": ok, "model": model_info}

# ── Model Metrics ─────────────────────────────────────────
@app.get("/api/metrics")
def metrics():
    pp = f"{PROCESSED_DIR}/predictions.parquet"
    fp = f"{PROCESSED_DIR}/features.parquet"
    if not os.path.exists(pp) or not os.path.exists(fp):
        raise HTTPException(404, "Run pipeline first")
    preds = pd.read_parquet(pp)
    hist  = pd.read_parquet(fp)[["id","date","sales"]]
    perf  = hist.merge(preds, on=["id","date"], how="inner")
    perf["ae"] = (perf["sales"] - perf["yhat"]).abs()
    perf["se"] = (perf["sales"] - perf["yhat"]) ** 2
    mae  = float(perf["ae"].mean())
    rmse = float(np.sqrt(perf["se"].mean()))
    mape = float((perf["ae"] / perf["sales"].where(perf["sales"]>0,1)).mean()*100)
    agg  = perf.groupby("date")[["sales","yhat"]].sum()
    fig, ax = plt.subplots(figsize=(10,4))
    dark(fig, ax)
    ax.plot(agg.index, agg["sales"], label="Actual",    color="#89b4fa", lw=2)
    ax.plot(agg.index, agg["yhat"],  label="Predicted", color="#fab387", lw=2, ls="--")
    ax.set_title("Actual vs Predicted", color="#cba6f7")
    ax.legend(facecolor="#313244", labelcolor="#cdd6f4")
    plt.tight_layout()
    chart   = fig_to_b64(fig)
    top_err = perf.groupby("id")["ae"].mean().sort_values(ascending=False).head(10).reset_index()
    top_err.columns = ["sku","mae"]
    return {"mae":round(mae,4),"rmse":round(rmse,4),"mape":round(mape,2),
            "chart":chart,"top_error_skus":top_err.to_dict(orient="records")}

# ── Feature Importance ────────────────────────────────────
@app.get("/api/feature-importance")
def feature_importance():
    mp = f"{MODEL_DIR}/model.pkl"
    if not os.path.exists(mp):
        raise HTTPException(404, "Model not found")
    m  = joblib.load(mp)
    fi = pd.DataFrame({"feature":m.feature_name_,"importance":m.feature_importances_})
    fi = fi.sort_values("importance", ascending=False).head(15)
    fig, ax = plt.subplots(figsize=(10,6))
    dark(fig, ax)
    ax.barh(fi["feature"][::-1], fi["importance"][::-1], color="#89b4fa")
    ax.set_title("Top 15 Feature Importances", color="#cba6f7")
    plt.tight_layout()
    return {"features":fi.to_dict(orient="records"),"chart":fig_to_b64(fig)}

# ── Upload CSV ────────────────────────────────────────────
@app.post("/api/upload")
async def upload(file: UploadFile = File(...)):
    content = await file.read()
    try:
        df = pd.read_csv(io.BytesIO(content), parse_dates=["date"])
    except Exception as e:
        raise HTTPException(400, f"CSV error: {e}")
    cols14 = ["item_id","dept_id","cat_id","store_id","state_id","wm_yr_wk",
              "snap_CA","snap_TX","snap_WI","sell_price","dayofweek","weekofyear",
              "month","year","date","sales"]
    cols3  = ["id","date","sales"]
    if all(c in df.columns for c in cols14):
        df["id"] = df["item_id"] + "_" + df["store_id"] + "_validation"
        fmt = "14col"
    elif all(c in df.columns for c in cols3):
        fmt = "3col"
    else:
        raise HTTPException(400, f"Missing columns. Need: {cols3} or {cols14}")
    df.to_parquet(f"{PROCESSED_DIR}/actual_month.parquet", index=False)

    fig1, axes = plt.subplots(1,2, figsize=(12,4))
    dark(fig1, axes)
    axes[0].hist(df["sales"], bins=30, color="#89b4fa", edgecolor="#1e1e2e")
    axes[0].set_title("Sales Distribution", color="#cba6f7")
    daily = df.groupby("date")["sales"].sum()
    axes[1].plot(daily.index, daily.values, color="#a6e3a1", lw=2)
    axes[1].set_title("Daily Sales Trend", color="#cba6f7")
    plt.tight_layout()
    dist_chart = fig_to_b64(fig1)

    dow_map = {0:"Mon",1:"Tue",2:"Wed",3:"Thu",4:"Fri",5:"Sat",6:"Sun"}
    df["_dow"] = df["date"].dt.dayofweek if "dayofweek" not in df.columns else df["dayofweek"]
    dow = df.groupby("_dow")["sales"].mean()
    fig2, ax2 = plt.subplots(figsize=(8,4))
    dark(fig2, ax2)
    colors = ["#f38ba8" if v==dow.max() else "#89b4fa" for v in dow.values]
    ax2.bar([dow_map.get(i,i) for i in dow.index], dow.values, color=colors)
    ax2.set_title("Sales by Day of Week (red=peak)", color="#cba6f7")
    plt.tight_layout()
    dow_chart = fig_to_b64(fig2)

    cat_chart = None
    if "cat_id" in df.columns:
        cat = df.groupby("cat_id")["sales"].mean()
        fig3, ax3 = plt.subplots(figsize=(6,4))
        dark(fig3, ax3)
        ax3.bar(cat.index, cat.values, color=["#89b4fa","#fab387","#a6e3a1"][:len(cat)])
        ax3.set_title("Mean Sales by Category", color="#cba6f7")
        plt.tight_layout()
        cat_chart = fig_to_b64(fig3)

    price_chart = None
    if "sell_price" in df.columns:
        fig4, axes4 = plt.subplots(1,2, figsize=(12,4))
        dark(fig4, axes4)
        axes4[0].hist(df["sell_price"].dropna(), bins=30, color="#a6e3a1", edgecolor="#1e1e2e")
        axes4[0].set_title("Price Distribution", color="#cba6f7")
        s = df.sample(min(500,len(df)))
        axes4[1].scatter(s["sell_price"], s["sales"], alpha=0.3, color="#cba6f7")
        axes4[1].set_title("Price vs Sales", color="#cba6f7")
        plt.tight_layout()
        price_chart = fig_to_b64(fig4)

    snap_chart = None
    if "snap_CA" in df.columns:
        fig5, axes5 = plt.subplots(1,3, figsize=(12,4))
        dark(fig5, axes5)
        for ax, col, title in zip(axes5, ["snap_CA","snap_TX","snap_WI"], ["CA","TX","WI"]):
            s = df.groupby(col)["sales"].mean()
            ax.bar(["No SNAP","SNAP"], s.values, color=["#89b4fa","#f38ba8"])
            ax.set_title(f"SNAP {title}", color="#cba6f7")
        plt.tight_layout()
        snap_chart = fig_to_b64(fig5)

    return {
        "analysis": {
            "rows":int(len(df)),"skus":int(df["id"].nunique()),
            "date_min":str(df["date"].min().date()),"date_max":str(df["date"].max().date()),
            "total_days":int(df["date"].nunique()),"mean_sales":round(float(df["sales"].mean()),3),
            "max_sales":int(df["sales"].max()),"zero_pct":round(float((df["sales"]==0).mean()*100),1),
            "total_units":int(df["sales"].sum()),"format":fmt
        },
        "charts":{"distribution":dist_chart,"dow":dow_chart,
                  "category":cat_chart,"price":price_chart,"snap":snap_chart}
    }

# ── Drift Check + Auto SHAP Explain ──────────────────────
@app.post("/api/drift")
def drift(month: str = ""):
    if not os.path.exists(f"{PROCESSED_DIR}/actual_month.parquet"):
        raise HTTPException(400, "Upload data first")

    # Generate features BEFORE drift check so actual_month_features.parquet exists
    actual_df = pd.read_parquet(f"{PROCESSED_DIR}/actual_month.parquet")
    try:
        create_features_for_new_data(actual_df)
    except Exception as e:
        raise HTTPException(500, f"Feature generation failed: {e}")

    result = run_drift_check()
    ks, level = result["ks_stat"], result["level"]

    dist_chart = None
    if ks is not None:
        actual = pd.read_parquet(f"{PROCESSED_DIR}/actual_month.parquet")
        preds  = pd.read_parquet(f"{PROCESSED_DIR}/predictions.parquet")
        merged = actual.merge(preds, on=["id","date"], how="inner")
        if not merged.empty:
            fig, ax = plt.subplots(figsize=(10,4))
            dark(fig, ax)
            ax.hist(merged["sales"], bins=30, alpha=0.6, label="Actual",    color="#89b4fa")
            ax.hist(merged["yhat"],  bins=30, alpha=0.6, label="Predicted", color="#fab387")
            ax.set_title("Actual vs Predicted Distribution", color="#cba6f7")
            ax.legend(facecolor="#313244", labelcolor="#cdd6f4")
            dist_chart = fig_to_b64(fig)

    # Auto-generate SHAP explanation
    explanation = get_shap_explanation(result, month or "Current Month")

    # For LOW drift, auto-log as "monitor"
    if level == "low":
        entry = build_logbook_entry(
            month or "Current Month", result,
            "monitor", get_current_metrics(), None, explanation
        )
        save_to_logbook(entry)

    msgs = {"low"    : "LOW drift — model stable. No retraining needed.",
            "medium" : "MEDIUM drift — fine-tuning recommended.",
            "high"   : "HIGH drift — sliding window retrain required.",
            "unknown": "No overlapping rows. Check id and date match."}

    return {
        "ks_stat": ks, "level": level,
        "message": msgs.get(level, ""),
        "dist_chart": dist_chart,
        "psi": result.get("psi"),
        "drift_score": result.get("drift_score"),
        "feature_drift": result.get("feature_drift", {}),
        "explanation": explanation,
    }

# ── SHAP Explain (standalone) ────────────────────────────
@app.post("/api/explain")
def explain(month: str = ""):
    drift_result = load_last_drift()
    return get_shap_explanation(drift_result, month or "Current Month")

# ── Fine-Tune ─────────────────────────────────────────────
@app.post("/api/retrain/finetune")
def finetune(month: str = ""):
    if not os.path.exists(f"{PROCESSED_DIR}/actual_month.parquet"):
        raise HTTPException(400, "Upload data first")
    df = pd.read_parquet(f"{PROCESSED_DIR}/actual_month.parquet")
    create_features_for_new_data(df)
    drift_result   = load_last_drift()
    metrics_before = get_current_metrics()
    metrics        = fine_tune()
    explanation    = get_shap_explanation(drift_result, month or "Unknown Month")
    entry = build_logbook_entry(month or "Unknown Month", drift_result,
                                "fine_tune", metrics_before, metrics, explanation)
    save_to_logbook(entry)
    return {"status":"success","metrics":metrics,"method":"fine_tune",
            "explanation":explanation}

# ── Sliding Window Retrain ────────────────────────────────
@app.post("/api/retrain/sliding")
def sliding(month: str = ""):
    if not os.path.exists(f"{PROCESSED_DIR}/actual_month.parquet"):
        raise HTTPException(400, "Upload data first")
    df = pd.read_parquet(f"{PROCESSED_DIR}/actual_month.parquet")
    create_features_for_new_data(df)
    drift_result   = load_last_drift()
    metrics_before = get_current_metrics()
    metrics        = sliding_window_retrain()
    explanation    = get_shap_explanation(drift_result, month or "Unknown Month")
    entry = build_logbook_entry(month or "Unknown Month", drift_result,
                                "sliding_window", metrics_before, metrics, explanation)
    save_to_logbook(entry)
    return {"status":"success","metrics":metrics,"method":"sliding_window",
            "explanation":explanation}

# ── Predict Next Month ────────────────────────────────────
@app.post("/api/predict")
def predict():
    if not os.path.exists(f"{MODEL_DIR}/model.pkl"):
        raise HTTPException(404, "Model not found")
    out = predict_next_month()
    out["category"] = out["id"].str.split("_").str[0]
    out["item"]     = out["id"].str.split("_").str[:3].str.join("_")
    out["store"]    = out["id"].str.split("_").str[3] + "_" + out["id"].str.split("_").str[4]
    agg = out.groupby("date")["predicted_sales"].sum().reset_index()

    fig, ax = plt.subplots(figsize=(12,4))
    dark(fig, ax)
    ax.plot(agg["date"], agg["predicted_sales"], color="#a6e3a1", lw=2, marker="o", ms=4)
    ax.fill_between(agg["date"], agg["predicted_sales"], alpha=0.15, color="#a6e3a1")
    ax.set_title("Next Month — Total Daily Forecast", color="#cba6f7")
    ax.set_xlabel("Date", color="#cdd6f4"); ax.set_ylabel("Units", color="#cdd6f4")
    plt.xticks(rotation=45); plt.tight_layout()
    overall_chart = fig_to_b64(fig)

    cat_agg    = out.groupby(["date","category"])["predicted_sales"].sum().reset_index()
    cats       = cat_agg["category"].unique()
    cat_colors = ["#89b4fa","#fab387","#a6e3a1","#cba6f7"]
    fig2, ax2  = plt.subplots(figsize=(12,4))
    dark(fig2, ax2)
    for i, cat in enumerate(cats):
        d = cat_agg[cat_agg["category"]==cat]
        ax2.plot(d["date"], d["predicted_sales"], label=cat,
                 color=cat_colors[i%len(cat_colors)], lw=2)
    ax2.set_title("Forecast by Category", color="#cba6f7")
    ax2.legend(facecolor="#313244", labelcolor="#cdd6f4")
    plt.xticks(rotation=45); plt.tight_layout()
    cat_chart = fig_to_b64(fig2)

    store_agg  = out.groupby(["date","store"])["predicted_sales"].sum().reset_index()
    stores     = store_agg["store"].unique()
    fig3, ax3  = plt.subplots(figsize=(12,4))
    dark(fig3, ax3)
    for i, st in enumerate(stores):
        d = store_agg[store_agg["store"]==st]
        ax3.plot(d["date"], d["predicted_sales"], label=f"Store {st}",
                 color=cat_colors[i%len(cat_colors)], lw=2)
    ax3.set_title("Forecast by Store", color="#cba6f7")
    ax3.legend(facecolor="#313244", labelcolor="#cdd6f4")
    plt.xticks(rotation=45); plt.tight_layout()
    store_chart = fig_to_b64(fig3)

    cat_summary   = out.groupby("category")["predicted_sales"].agg(["sum","mean","max"]).round(2).reset_index()
    cat_summary.columns = ["category","total_units","avg_daily","peak_day_units"]
    store_summary = out.groupby("store")["predicted_sales"].agg(["sum","mean","max"]).round(2).reset_index()
    store_summary.columns = ["store","total_units","avg_daily","peak_day_units"]
    top = out.groupby(["item","category","store"])["predicted_sales"].sum().sort_values(ascending=False).head(10).reset_index()
    top.columns = ["product","category","store","total_predicted"]
    top["total_predicted"] = top["total_predicted"].round(2)

    return {
        "total_units" : round(float(out["predicted_sales"].sum()),2),
        "mean_daily"  : round(float(agg["predicted_sales"].mean()),2),
        "peak_day"    : str(agg.loc[agg["predicted_sales"].idxmax(),"date"].date()),
        "date_min"    : str(out["date"].min().date()),
        "date_max"    : str(out["date"].max().date()),
        "total_rows"  : int(len(out)),
        "total_skus"  : int(out["id"].nunique()),
        "total_stores": int(out["store"].nunique()),
        "total_cats"  : int(out["category"].nunique()),
        "charts"      : {"overall":overall_chart,"category":cat_chart,"store":store_chart},
        "cat_summary" : cat_summary.to_dict(orient="records"),
        "store_summary": store_summary.to_dict(orient="records"),
        "top_products": top.to_dict(orient="records"),
    }

# ── Next Month Upload Prompt ──────────────────────────────
@app.get("/api/next-month-prompt")
def next_month_prompt():
    pred_path = f"{PROCESSED_DIR}/next_month_predictions.parquet"
    if not os.path.exists(pred_path):
        return {"ready": False, "message": "Run forecast first"}
    df = pd.read_parquet(pred_path)
    df["date"] = pd.to_datetime(df["date"])
    next_min   = df["date"].min().date()
    next_max   = df["date"].max().date()
    month_name = calendar.month_name[next_min.month]
    return {
        "ready"      : True,
        "next_month" : f"{month_name} {next_min.year}",
        "date_from"  : str(next_min),
        "date_to"    : str(next_max),
        "message"    : (
            f"Forecast for {month_name} {next_min.year} is ready. "
            f"At the end of {month_name}, upload the actual sales data "
            f"({str(next_min)} to {str(next_max)}) to run drift detection "
            f"and update the model for the following month."
        ),
        "upload_instructions": {
            "format"    : "CSV with columns: id, date, sales (or 14-column format)",
            "id_format" : "HOBBIES_1_001_CA_1_validation",
            "date_range": f"{next_min} to {next_max}",
            "example"   : f"id,date,sales\nHOBBIES_1_001_CA_1_validation,{next_min},2"
        }
    }

# ── Logbook ───────────────────────────────────────────────
@app.get("/api/logbook")
def get_logbook():
    return {"entries": load_logbook()}

# ── Download CSV ──────────────────────────────────────────
@app.get("/api/predict/download")
def download():
    path = f"{PROCESSED_DIR}/next_month_predictions.parquet"
    if not os.path.exists(path):
        raise HTTPException(404, "No predictions. Run predict first.")
    df  = pd.read_parquet(path)
    csv = df.to_csv(index=False)
    return StreamingResponse(io.StringIO(csv), media_type="text/csv",
        headers={"Content-Disposition":"attachment; filename=next_month_predictions.csv"})

# ── Serve React build ─────────────────────────────────────
frontend_dist = os.path.join(os.path.dirname(__file__), "..", "frontend", "dist")
if os.path.exists(frontend_dist):
    app.mount("/", StaticFiles(directory=frontend_dist, html=True), name="static")
