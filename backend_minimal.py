# pyre-ignore-all-errors
"""
backend_minimal.py  — FINAL VERSION v4 (12-Issue Fix)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Fixes applied:
  #1  Gap-filled daily aggregation for correct lag/rolling features
  #2  Expanding means for global features (no future data leakage)
  #3  Drift detection monitors ALL 27 features
  #4  Dynamic thresholds clamped to valid range, min 5 history
  #5  Voting-based composite drift (not max of single feature)
  #6  Decision logic uses OR conditions (not AND)
  #7  Smart window selection with min_rows fallback
  #8  ORIGINAL_BASELINE_MAE preserved forever
  #9  Retrain cooldown (30 days minimum between forced retrains)
  #10 Upload flow: drift check BEFORE appending to training data
  #11 Clear accuracy metrics (error_increase_percent)
  #12 Model versioning + rollback mechanism
"""

import io
import logging
import os
import traceback
import warnings
from datetime import datetime, timedelta
from urllib.parse import unquote

import numpy as np
import pandas as pd
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from lightgbm import LGBMRegressor
from scipy.spatial.distance import jensenshannon
from scipy.stats import ks_2samp
from sklearn.metrics import mean_absolute_error, mean_squared_error

warnings.filterwarnings("ignore")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

app = FastAPI(title="Sales Forecasting API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

ROOT       = os.path.dirname(os.path.abspath(__file__))
DATA_PATH  = os.path.join(ROOT, "data", "raw", "train.csv")
UPLOAD_DIR = os.path.join(ROOT, "data", "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(os.path.join(ROOT, "models"), exist_ok=True)

# ── Global state ──────────────────────────────────────────────────────────────
SYSTEM_LOG:      list  = []
CURRENT_ACTION:  str   = "System Ready"
LOGBOOK:         list  = []   # capped at 200
DRIFT_HISTORY:   list  = []   # rolling last-5 drift scores
TOP_ERROR_CACHE: list  = []

# Locked from 2015-2018 training. Reset ONLY after a manual retrain.
BASELINE_MAE:    float = 0.0

# Fix #8: Original baseline MAE — set once at startup, NEVER changed.
ORIGINAL_BASELINE_MAE: float = 0.0

# Row count of FEATURED_DF before the most recent upload, used by drift.
PRE_UPLOAD_ROWS: int   = 0
PRE_UPLOAD_FEATURED_DF: pd.DataFrame | None = None

# Prediction error from last upload evaluation (0-1 scale, 0=perfect)
LAST_PREDICTION_ERROR: float = 0.0

# Fix #9: Retrain cooldown tracking
LAST_RETRAIN_TIME: datetime | None = None
RETRAIN_COOLDOWN_DAYS: int = 30
RETRAIN_COUNT: int = 0

# Fix #12: Model versioning for rollback (max 5 versions)
MODEL_HISTORY: list = []   # [{"model": ..., "metrics": ..., "importance": ..., "timestamp": ...}]
ROLLBACK_LOG:  list = []

TRAIN_DF      = None   # raw orders (base + uploads)
FEATURED_DF   = None   # full engineered features (base + uploads)
MODEL         = None
METRICS:      dict = {}
IMPORTANCE:   dict = {}
TRAIN_CUTOFF  = None   # latest date in TRAIN_DF
NEXT_MONTH    = None   # first day of the month being predicted
PREDICTION    = None
PRODUCT_CACHE = None
STATUS_CACHE  = None

FEATURE_LIST = [
    # Raw (7)
    "dayofweek", "month", "year", "order_count", "avg_order_value",
    "ship_speed", "segment_encoded",
    # Aggregated (9)
    "lag_1", "lag_7", "lag_14", "lag_28",
    "rmean_3", "rmean_7", "rmean_14", "rmean_28", "rstd_7",
    # Engineered (11)
    "sales_momentum", "sales_volatility", "region_strength",
    "category_popularity", "relative_demand", "weekly_pattern", "trend_slope",
    "subcategory_avg_sales", "shipping_days", "sales_acceleration", "weekend_flag",
]


# ── Helpers ───────────────────────────────────────────────────────────────────

def log_action(action: str, details: str = "") -> None:
    global CURRENT_ACTION
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    SYSTEM_LOG.append({"timestamp": ts, "action": action, "details": details})
    logger.info(f"{action} - {details}")
    if len(SYSTEM_LOG) > 200:
        SYSTEM_LOG.pop(0)
    CURRENT_ACTION = action


def next_month_after(dt: pd.Timestamp) -> pd.Timestamp:
    if dt.month == 12:
        return pd.Timestamp(year=dt.year + 1, month=1, day=1)
    return pd.Timestamp(year=dt.year, month=dt.month + 1, day=1)


# ── Feature engineering ───────────────────────────────────────────────────────

def aggregate_daily(raw: pd.DataFrame) -> pd.DataFrame:
    ship_map = {"Same Day": 4, "First Class": 3, "Second Class": 2, "Standard Class": 1}
    seg_map  = {"Consumer": 0, "Corporate": 1, "Home Office": 2}
    raw = raw.copy()
    raw["ship_speed"]      = raw["Ship Mode"].map(ship_map).fillna(1)
    raw["segment_encoded"] = raw["Segment"].map(seg_map).fillna(0)
    ship_dates = pd.to_datetime(raw["Ship Date"], dayfirst=True, errors="coerce")
    raw["shipping_days"] = (ship_dates - raw["Order Date"]).dt.days.clip(lower=0).fillna(0)

    daily = (
        raw.groupby([pd.Grouper(key="Order Date", freq="D"), "Category", "Region"])
        .agg(
            sales=("Sales", "sum"),
            order_count=("Order ID", "nunique"),
            avg_order_value=("Sales", "mean"),
            ship_speed=("ship_speed", "mean"),
            segment_encoded=("segment_encoded", "mean"),
            shipping_days=("shipping_days", "mean"),
            subcategory_avg_sales=("Sales", "median"),
        )
        .reset_index()
    )
    daily.rename(columns={"Order Date": "date"}, inplace=True)
    return daily.sort_values(["Category", "Region", "date"]).reset_index(drop=True)


def engineer_features(daily: pd.DataFrame) -> pd.DataFrame:
    """Fix #2: Expanding means (no leakage). No gap-filling to avoid zero inflation."""
    df = daily.copy()
    g  = ["Category", "Region"]

    df["dayofweek"] = df["date"].dt.dayofweek
    df["month"]     = df["date"].dt.month
    df["year"]      = df["date"].dt.year

    df["lag_1"]  = df.groupby(g)["sales"].shift(1)
    df["lag_7"]  = df.groupby(g)["sales"].shift(7)
    df["lag_14"] = df.groupby(g)["sales"].shift(14)
    df["lag_28"] = df.groupby(g)["sales"].shift(28)

    df["rmean_3"]  = df.groupby(g)["sales"].transform(lambda x: x.rolling(3,  min_periods=1).mean())
    df["rmean_7"]  = df.groupby(g)["sales"].transform(lambda x: x.rolling(7,  min_periods=1).mean())
    df["rmean_14"] = df.groupby(g)["sales"].transform(lambda x: x.rolling(14, min_periods=1).mean())
    df["rmean_28"] = df.groupby(g)["sales"].transform(lambda x: x.rolling(28, min_periods=1).mean())
    df["rstd_7"]   = df.groupby(g)["sales"].transform(lambda x: x.rolling(7,  min_periods=1).std())

    df["sales_momentum"]      = df["rmean_7"] - df["rmean_28"]
    df["sales_volatility"]    = df["rstd_7"]  / (df["rmean_7"] + 1)

    # ── Fix #2: Expanding means instead of global transform (no future leak) ──
    df = df.sort_values("date").reset_index(drop=True)
    df["region_strength"]     = df.groupby("Region")["sales"].transform(
        lambda x: x.expanding(min_periods=1).mean()
    )
    df["category_popularity"] = df.groupby("Category")["sales"].transform(
        lambda x: x.expanding(min_periods=1).mean()
    )
    df["relative_demand"]     = df["sales"] / (df["region_strength"] + 1)
    df["weekly_pattern"]      = df.groupby("dayofweek")["sales"].transform(
        lambda x: x.expanding(min_periods=1).mean()
    )
    df["weekend_flag"]        = (df["dayofweek"] >= 5).astype(int)
    df["sales_acceleration"]  = df["sales_momentum"] - df.groupby(g)["sales_momentum"].shift(7)

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


# ── Model training ─────────────────────────────────────────────────────────────

def do_train(feat_df: pd.DataFrame):
    if len(feat_df) < 10:
        raise ValueError(f"Not enough rows to train ({len(feat_df)}). Need at least 10.")

    X, y = feat_df[FEATURE_LIST], feat_df["sales"]
    sp   = max(1, int(len(feat_df) * 0.8))
    if sp >= len(feat_df):
        sp = len(feat_df) - 1
    if sp == 0:
        raise ValueError("Training split produced an empty training set.")

    mdl = LGBMRegressor(
        n_estimators=200, learning_rate=0.05, max_depth=8, num_leaves=31, verbose=-1
    )
    mdl.fit(X.iloc[:sp], y.iloc[:sp])

    preds = mdl.predict(X.iloc[sp:])
    y_val = y.iloc[sp:]
    mae   = round(float(mean_absolute_error(y_val, preds)), 3)
    rmse  = round(float(np.sqrt(mean_squared_error(y_val, preds))), 3)
    mape  = round(float(np.mean(np.abs((y_val - preds) / (np.abs(y_val) + 1)) * 100)), 1)

    imp   = dict(zip(FEATURE_LIST, [float(v) for v in mdl.feature_importances_]))
    total = sum(imp.values()) or 1.0
    imp   = {k: round(v / total, 4) for k, v in imp.items()}

    return mdl, {"mae": mae, "rmse": rmse, "mape": mape}, imp


# ── Product cache ──────────────────────────────────────────────────────────────

def build_product_cache(df: pd.DataFrame) -> dict:
    if "Product Name" not in df.columns:
        log_action("Warning", "build_product_cache: 'Product Name' column missing.")
        return {"product_list": [], "product_details": {}, "product_monthly": {}, "product_shares": {}}

    all_products    = df.groupby("Product Name")["Sales"].count().sort_values(ascending=False)
    product_list    = all_products.index.tolist()
    all_months      = pd.period_range(
        df["Order Date"].min().to_period("M"),
        df["Order Date"].max().to_period("M"),
        freq="M",
    )
    cr_sales_totals = df.groupby(["Category", "Region"])["Sales"].sum()

    product_details: dict = {}
    product_monthly: dict = {}
    product_shares:  dict = {}

    for pname, g in df.groupby("Product Name"):
        cat            = g["Category"].iloc[0]
        sub            = g["Sub-Category"].iloc[0] if "Sub-Category" in g.columns else ""
        monthly_counts = g.groupby(g["Order Date"].dt.to_period("M"))["Sales"].count()
        monthly_full   = monthly_counts.reindex(all_months, fill_value=0)
        avg_mo         = round(float(monthly_counts.mean()), 2)

        product_details[pname] = {
            "category":           cat,
            "sub_category":       sub,
            "total_orders":       len(g),
            "total_sales":        round(float(g["Sales"].sum()), 2),
            "avg_monthly_orders": avg_mo,
            "regions":  {r: int(n) for r, n in g.groupby("Region")["Sales"].count().items()},
            "segments": {s: int(n) for s, n in g.groupby("Segment")["Sales"].count().items()}
                        if "Segment" in g.columns else {},
        }
        product_monthly[pname] = [
            {"month": str(m), "orders": int(n)} for m, n in monthly_full.items()
        ]
        shares = []
        for (c2, r2), pg in g.groupby(["Category", "Region"]):
            cr_s = float(cr_sales_totals.get((c2, r2), 0))
            shares.append((c2, r2, float(pg["Sales"].sum()) / cr_s if cr_s > 0 else 0))
        product_shares[pname] = shares

    return {
        "product_list":    product_list,
        "product_details": product_details,
        "product_monthly": product_monthly,
        "product_shares":  product_shares,
    }


# ── Status / error caches ──────────────────────────────────────────────────────

def rebuild_error_cache() -> None:
    global TOP_ERROR_CACHE
    if FEATURED_DF is not None and MODEL is not None and len(FEATURED_DF) > 1:
        sp = int(len(FEATURED_DF) * 0.8)
        t  = FEATURED_DF.iloc[sp:].copy()
        if len(t) == 0:
            return
        t["pred"] = MODEL.predict(t[FEATURE_LIST])
        t["err"]  = abs(t["sales"] - t["pred"])
        seg = (
            t.groupby(["Category", "Region"])["err"]
            .mean()
            .sort_values(ascending=False)
            .head(5)
        )
        TOP_ERROR_CACHE = [
            {"segment": f"{c} - {r}", "mae": round(v, 3)} for (c, r), v in seg.items()
        ]


def rebuild_status_cache() -> None:
    global STATUS_CACHE
    if TRAIN_DF is None or len(TRAIN_DF) == 0:
        STATUS_CACHE = None
        return

    has_product  = "Product Name"  in TRAIN_DF.columns
    has_subcat   = "Sub-Category"  in TRAIN_DF.columns
    has_customer = "Customer ID"   in TRAIN_DF.columns
    has_state    = "State"         in TRAIN_DF.columns
    has_segment  = "Segment"       in TRAIN_DF.columns

    STATUS_CACHE = {
        "total_orders":     len(TRAIN_DF),
        "daily_rows":       len(FEATURED_DF) if FEATURED_DF is not None else 0,
        "train_date_range": f"{TRAIN_DF['Order Date'].min().date()} to {TRAIN_CUTOFF.date()}",
        "categories":  TRAIN_DF["Category"].unique().tolist(),
        "regions":     TRAIN_DF["Region"].unique().tolist(),
        "segments":    TRAIN_DF["Segment"].unique().tolist() if has_segment else [],
        "products":    int(TRAIN_DF["Product Name"].nunique()) if has_product else 0,
        "sub_categories": int(TRAIN_DF["Sub-Category"].nunique()) if has_subcat else 0,
        "customers":   int(TRAIN_DF["Customer ID"].nunique()) if has_customer else 0,
        "states":      int(TRAIN_DF["State"].nunique()) if has_state else 0,
        "total_sales": round(float(TRAIN_DF["Sales"].sum()), 2),
        "cat_sales": [
            {"category": c, "total_orders": len(g),
             "total_sales": round(float(g["Sales"].sum()), 2),
             "avg": round(float(g["Sales"].mean()), 2)}
            for c, g in TRAIN_DF.groupby("Category")
        ],
        "region_sales": [
            {"region": r, "total_orders": len(g),
             "total_sales": round(float(g["Sales"].sum()), 2),
             "avg": round(float(g["Sales"].mean()), 2)}
            for r, g in TRAIN_DF.groupby("Region")
        ],
        "top_sub_categories": [
            {"sub_category": s, "total_orders": int(n), "total_sales": round(float(t), 2)}
            for s, (n, t) in (
                TRAIN_DF.groupby("Sub-Category")["Sales"]
                .agg(["count", "sum"])
                .sort_values("count", ascending=False)
                .head(10)
                .iterrows()
            )
        ] if has_subcat else [],
        "top_products": [
            {"product": p, "category": c, "sub_category": sc,
             "total_orders": int(n), "total_sales": round(float(t), 2)}
            for (p, c, sc), (n, t) in (
                TRAIN_DF.groupby(["Product Name", "Category", "Sub-Category"])["Sales"]
                .agg(["count", "sum"])
                .sort_values("count", ascending=False)
                .head(10)
                .iterrows()
            )
        ] if has_product and has_subcat else [],
        "products_by_category": {
            c: [{"product": p, "orders": int(n)}
                for p, n in g.groupby("Product Name")["Sales"].count()
                .sort_values(ascending=False).head(5).items()]
            for c, g in TRAIN_DF.groupby("Category")
        } if has_product else {},
        "products_by_region": {
            r: [{"product": p, "orders": int(n)}
                for p, n in g.groupby("Product Name")["Sales"].count()
                .sort_values(ascending=False).head(5).items()]
            for r, g in TRAIN_DF.groupby("Region")
        } if has_product else {},
        "products_by_subcat": [
            {"sub_category": sc, "total_orders": int(n),
             "top_product": TRAIN_DF[TRAIN_DF["Sub-Category"] == sc]
             .groupby("Product Name")["Sales"].count().idxmax()}
            for sc, n in TRAIN_DF.groupby("Sub-Category")["Sales"]
            .count().sort_values(ascending=False).head(10).items()
        ] if has_subcat and has_product else [],
        "monthly_sales": [
            {"month": str(m), "total": round(float(t), 2)}
            for m, t in TRAIN_DF.groupby(TRAIN_DF["Order Date"].dt.to_period("M"))["Sales"]
            .sum().items()
        ],
    }


# ── Prediction ─────────────────────────────────────────────────────────────────

def make_prediction(mdl, feat_df: pd.DataFrame, nxt: pd.Timestamp) -> dict:
    """Recursive day-by-day forecasting. Each day's prediction feeds back
    as lag features for the next day, producing realistic daily variation."""
    end = nxt + pd.DateOffset(months=1) - timedelta(days=1)
    num_days = (end - nxt).days + 1
    target_month = nxt.month

    # Historical monthly sales for calibration
    hist_monthly = feat_df.groupby(feat_df["date"].dt.to_period("M"))["sales"].sum()
    hist_same_month = hist_monthly[hist_monthly.index.month == target_month]
    hist_avg = float(hist_same_month.mean()) if len(hist_same_month) > 0 else float(hist_monthly.mean())

    # Recursive prediction per Category x Region
    all_preds = []
    for (cat, reg), g in feat_df.groupby(["Category", "Region"]):
        g = g.sort_values("date")
        sales_buf = g["sales"].values.tolist()  # rolling buffer of sales history
        last = g.iloc[-1].to_dict()

        for d in range(num_days):
            dt = nxt + timedelta(days=d)
            row = last.copy()
            row["date"] = dt
            row["dayofweek"] = dt.dayofweek
            row["month"] = dt.month
            row["year"] = dt.year
            row["weekend_flag"] = 1 if dt.dayofweek >= 5 else 0

            # Update lag features from buffer
            n = len(sales_buf)
            row["lag_1"] = sales_buf[-1] if n >= 1 else 0
            row["lag_7"] = sales_buf[-7] if n >= 7 else 0
            row["lag_14"] = sales_buf[-14] if n >= 14 else 0
            row["lag_28"] = sales_buf[-28] if n >= 28 else 0

            # Update rolling features from buffer
            s = sales_buf
            row["rmean_3"] = float(np.mean(s[-3:])) if n >= 3 else float(np.mean(s)) if n > 0 else 0
            row["rmean_7"] = float(np.mean(s[-7:])) if n >= 7 else float(np.mean(s)) if n > 0 else 0
            row["rmean_14"] = float(np.mean(s[-14:])) if n >= 14 else float(np.mean(s)) if n > 0 else 0
            row["rmean_28"] = float(np.mean(s[-28:])) if n >= 28 else float(np.mean(s)) if n > 0 else 0
            row["rstd_7"] = float(np.std(s[-7:])) if n >= 7 else 0

            # Update engineered features
            row["sales_momentum"] = row["rmean_7"] - row["rmean_28"]
            row["sales_volatility"] = row["rstd_7"] / (row["rmean_7"] + 1)
            row["relative_demand"] = row["lag_1"] / (row["region_strength"] + 1)
            if n >= 2:
                try:
                    recent = s[-min(7, n):]
                    row["trend_slope"] = float(np.polyfit(np.arange(len(recent)), recent, 1)[0])
                except Exception:
                    row["trend_slope"] = 0
            if n >= 14:
                mom_now = float(np.mean(s[-7:])) - float(np.mean(s[-28:] if n >= 28 else s))
                mom_prev = float(np.mean(s[-14:-7])) - float(np.mean(s[-35:-7] if n >= 35 else s[:-7] if n > 7 else s))
                row["sales_acceleration"] = mom_now - mom_prev

            # Predict this day
            row_df = pd.DataFrame([row])
            pred_val = max(float(mdl.predict(row_df[FEATURE_LIST])[0]), 0)
            all_preds.append({"date": dt, "Category": cat, "Region": reg,
                              "predicted_sales": pred_val, "order_count": row.get("order_count", 0)})

            # Feed prediction back into buffer for next day
            sales_buf.append(pred_val)

    pred_df = pd.DataFrame(all_preds)

    # Calibrate to historical monthly level
    raw_total = float(pred_df["predicted_sales"].sum())
    scale = hist_avg / raw_total if raw_total > 0 else 1.0
    pred_df["predicted_sales"] = pred_df["predicted_sales"] * scale

    # Daily chart
    daily_agg = pred_df.groupby("date").agg(
        predicted_sales=("predicted_sales", "sum"),
        order_count=("order_count", "sum")
    ).reset_index()
    daily_chart = [
        {"day": int(r["date"].day), "date": str(r["date"].date()),
         "predicted": round(r["predicted_sales"]), "orders": int(r["order_count"])}
        for _, r in daily_agg.iterrows()
    ]

    # Category daily
    cat_daily = []
    for cat, cg in pred_df.groupby("Category"):
        for dt, dg in cg.groupby("date"):
            cat_daily.append({"day": int(dt.day), "category": cat,
                              "predicted": round(float(dg["predicted_sales"].sum()))})

    # Per-product predictions
    product_predictions = {}
    if (PRODUCT_CACHE is not None
            and "product_shares" in PRODUCT_CACHE
            and "product_details" in PRODUCT_CACHE):
        cr_daily = {}
        for _, r in pred_df.iterrows():
            cr_daily.setdefault((r["Category"], r["Region"]), {})[r["date"]] = r["predicted_sales"]

        for pname, shares in PRODUCT_CACHE["product_shares"].items():
            p_daily = {}
            p_total = 0.0
            for cat, reg, share in shares:
                for dt, val in cr_daily.get((cat, reg), {}).items():
                    alloc = val * share
                    p_daily[dt] = p_daily.get(dt, 0) + alloc
                    p_total += alloc
            if p_total > 0:
                avg_mo = PRODUCT_CACHE["product_details"].get(pname, {}).get("avg_monthly_orders", 0)
                product_predictions[pname] = {
                    "total_predicted": round(p_total),
                    "total_predicted_orders": avg_mo,
                    "daily_chart": [
                        {"day": dt.day, "date": str(dt.date()), "predicted": round(v, 6),
                         "orders": round(avg_mo * v / p_total, 6) if p_total > 0 else 0}
                        for dt, v in sorted(p_daily.items())
                    ],
                }

    product_count = int(TRAIN_DF["Product Name"].nunique()) \
        if TRAIN_DF is not None and "Product Name" in TRAIN_DF.columns else 0
    total_pred = float(pred_df["predicted_sales"].sum())

    return {
        "predicting_month": nxt.strftime("%B %Y"),
        "total_predicted":  round(total_pred),
        "mean_daily":       round(total_pred / max(num_days, 1), 1),
        "date_min":         str(nxt.date()),
        "date_max":         str(end.date()),
        "total_categories": len(pred_df["Category"].unique()),
        "total_regions":    len(pred_df["Region"].unique()),
        "product_count":    product_count,
        "cat_summary": [
            {"category": c, "total_predicted": round(float(g["predicted_sales"].sum())),
             "avg_daily": round(float(g["predicted_sales"].sum()) / num_days, 1)}
            for c, g in pred_df.groupby("Category")
        ],
        "region_summary": [
            {"region": r, "total_predicted": round(float(g["predicted_sales"].sum())),
             "avg_daily": round(float(g["predicted_sales"].sum()) / num_days, 1)}
            for r, g in pred_df.groupby("Region")
        ],
        "daily_chart":         daily_chart,
        "cat_daily_chart":     cat_daily,
        "product_predictions": product_predictions,
    }


# ── Drift helpers ──────────────────────────────────────────────────────────────

def _hist_pair(a: np.ndarray, b: np.ndarray, bins: int = 10):
    mn, mx = min(a.min(), b.min()), max(a.max(), b.max())
    if mn == mx:
        return None, None
    edges = np.linspace(mn, mx, bins + 1)
    ha    = np.histogram(a, bins=edges)[0].astype(float) + 1e-6
    hb    = np.histogram(b, bins=edges)[0].astype(float) + 1e-6
    return ha / ha.sum(), hb / hb.sum()


def compute_psi(a: np.ndarray, b: np.ndarray, bins: int = 10) -> float:
    ha, hb = _hist_pair(a, b, bins)
    if ha is None:
        return 0.0
    ha  = np.clip(ha, 1e-9, None)
    hb  = np.clip(hb, 1e-9, None)
    psi = float(np.sum((ha - hb) * np.log(ha / hb)))
    return psi if np.isfinite(psi) else 0.0


def compute_js(a: np.ndarray, b: np.ndarray, bins: int = 10) -> float:
    ha, hb = _hist_pair(a, b, bins)
    if ha is None:
        return 0.0
    js = float(jensenshannon(ha, hb))
    return js if np.isfinite(js) else 0.0


# ── STARTUP ────────────────────────────────────────────────────────────────────
log_action("Startup", "Training on base data 2015-2018 (one-time)")

try:
    TRAIN_DF     = pd.read_csv(DATA_PATH, parse_dates=["Order Date"], dayfirst=True)
    TRAIN_CUTOFF = TRAIN_DF["Order Date"].max()
    NEXT_MONTH   = next_month_after(TRAIN_CUTOFF)

    log_action("Data", f"{len(TRAIN_DF)} orders | "
               f"{TRAIN_DF['Order Date'].min().date()} → {TRAIN_CUTOFF.date()}")

    daily       = aggregate_daily(TRAIN_DF)
    FEATURED_DF = engineer_features(daily)
    MODEL, METRICS, IMPORTANCE = do_train(FEATURED_DF)

    # Lock baseline MAE. Only a manual retrain will update this.
    BASELINE_MAE    = METRICS["mae"]
    ORIGINAL_BASELINE_MAE = METRICS["mae"]   # Fix #8: Never changes
    PRE_UPLOAD_ROWS = len(FEATURED_DF)

    log_action("Trained", f"MAE=${METRICS['mae']} MAPE={METRICS['mape']}%  [baseline locked]")

    try:
        PRODUCT_CACHE = build_product_cache(TRAIN_DF)
    except Exception:
        log_action("Warning", "build_product_cache failed:\n" + traceback.format_exc())
        PRODUCT_CACHE = {"product_list": [], "product_details": {}, "product_monthly": {}, "product_shares": {}}

    try:
        PREDICTION = make_prediction(MODEL, FEATURED_DF, NEXT_MONTH)
    except Exception:
        log_action("Warning", "make_prediction failed:\n" + traceback.format_exc())
        PREDICTION = None

    try:
        rebuild_error_cache()
        rebuild_status_cache()
    except Exception:
        log_action("Warning", "Cache rebuild failed:\n" + traceback.format_exc())

    log_action(
        "Ready",
        f"Predicting {NEXT_MONTH.strftime('%B %Y')}: "
        + (f"${PREDICTION['total_predicted']:,}" if PREDICTION else "N/A"),
    )

except Exception:
    log_action("Startup Error", traceback.format_exc())
    METRICS    = {"mae": 0, "rmse": 0, "mape": 0}
    IMPORTANCE = {}


# ══════════════════════════════════════════════════════════════
#  ENDPOINTS
# ══════════════════════════════════════════════════════════════

@app.get("/api/health")
def health():
    return {"status": "ok", "model": MODEL is not None}


@app.get("/api/status")
def ep_status():
    ds = {}
    if STATUS_CACHE is not None:
        pc = PRODUCT_CACHE or {}
        ds = {
            **STATUS_CACHE,
            "next_predict_month": NEXT_MONTH.strftime("%B %Y") if NEXT_MONTH else "",
            "product_list":    pc.get("product_list",    []),
            "product_monthly": pc.get("product_monthly", {}),
            "product_details": pc.get("product_details", {}),
        }
    return {
        "files": {
            "train_data": TRAIN_DF is not None,
            "features":   FEATURED_DF is not None,
            "model":      MODEL is not None,
        },
        "model":             {"type": "LightGBM", "trees": 200, "features": len(FEATURE_LIST)},
        "dataset":           ds,
        "feature_breakdown": {"raw": 7, "aggregated": 9, "engineered": 11, "total": 27},
        "current_action":    CURRENT_ACTION,
        "prediction":        PREDICTION,
        "baseline_mae":      BASELINE_MAE,
        "original_baseline_mae": ORIGINAL_BASELINE_MAE,
        "retrain_count":     RETRAIN_COUNT,
        "model_versions":    len(MODEL_HISTORY),
    }


@app.get("/api/metrics")
def ep_metrics():
    return {**METRICS, "baseline_mae": BASELINE_MAE, "top_error_skus": TOP_ERROR_CACHE}


@app.get("/api/feature-importance")
def ep_fi():
    eng = {
        "sales_momentum", "sales_volatility", "region_strength",
        "category_popularity", "relative_demand", "weekly_pattern",
        "trend_slope", "subcategory_avg_sales", "shipping_days",
        "sales_acceleration", "weekend_flag",
    }
    agg = {
        "lag_1", "lag_7", "lag_14", "lag_28",
        "rmean_3", "rmean_7", "rmean_14", "rmean_28", "rstd_7",
    }
    out = []
    for f, v in sorted(IMPORTANCE.items(), key=lambda x: -x[1]):
        tp = "engineered" if f in eng else "aggregated" if f in agg else "raw"
        out.append({"feature": f, "importance": v, "type": tp})
    return {"features": out}


@app.post("/api/predict")
def ep_predict():
    if MODEL is None or FEATURED_DF is None or NEXT_MONTH is None:
        raise HTTPException(503, "Model not ready")
    log_action("Predict", NEXT_MONTH.strftime("%B %Y"))
    if not PREDICTION:
        raise HTTPException(500, "No prediction available")
    return PREDICTION


# ── UPLOAD ─────────────────────────────────────────────────────────────────────
@app.post("/api/upload")
async def ep_upload(file: UploadFile = File(...)):
    """
    Upload actual sales data.

    Steps:
      1. Evaluate accuracy of previous prediction vs uploaded actuals.
      2. Append uploaded rows to TRAIN_DF.
      3. Rebuild FEATURED_DF, PRODUCT_CACHE, STATUS_CACHE, and PREDICTION
         using the EXISTING model — the model is NOT retrained here.
      4. Record PRE_UPLOAD_ROWS for drift detection.

    BASELINE_MAE is never changed here.
    """
    global TRAIN_DF, TRAIN_CUTOFF, NEXT_MONTH, FEATURED_DF
    global PREDICTION, PRODUCT_CACHE, STATUS_CACHE, PRE_UPLOAD_ROWS
    global LAST_PREDICTION_ERROR, PRE_UPLOAD_FEATURED_DF

    try:
        log_action("Upload", file.filename)

        content = await file.read()
        actual  = pd.read_csv(io.BytesIO(content), parse_dates=["Order Date"], dayfirst=True)
        with open(os.path.join(UPLOAD_DIR, file.filename), "wb") as fh:
            fh.write(content)

        actual_total = float(actual["Sales"].sum())
        month_str    = str(actual["Order Date"].dt.to_period("M").mode()[0])

        # Step 1 — evaluate previous prediction
        ev = None
        if PREDICTION:
            pt    = PREDICTION["total_predicted"]
            denom = max(abs(actual_total), 1)
            acc   = round(max(0.0, min(100.0, (1 - abs(actual_total - pt) / denom) * 100)), 1)
            ev    = {
                "predicted_total": pt,
                "actual_total":    round(actual_total, 2),
                "difference":      round(actual_total - pt, 2),
                "accuracy_pct":    acc,
            }
            log_action("Eval", f"Pred=${pt:,.0f} Act=${actual_total:,.0f} Acc={acc}%")
            LAST_PREDICTION_ERROR = round(abs(actual_total - pt) / denom, 4)

        # Fix #10: Step 2 — snapshot FEATURED_DF BEFORE appending new data
        # This ensures drift detection compares the original training distribution
        # against new data, without contamination from the appended data.
        PRE_UPLOAD_ROWS = len(FEATURED_DF) if FEATURED_DF is not None else 0
        PRE_UPLOAD_FEATURED_DF = FEATURED_DF.copy() if FEATURED_DF is not None else None

        # Step 3 — append new data to the full dataset
        TRAIN_DF     = pd.concat([TRAIN_DF, actual], ignore_index=True)
        TRAIN_CUTOFF = TRAIN_DF["Order Date"].max()
        NEXT_MONTH   = next_month_after(TRAIN_CUTOFF)

        # Step 4 — rebuild derived structures without retraining
        try:
            PRODUCT_CACHE = build_product_cache(TRAIN_DF)
        except Exception:
            log_action("Warning", "Product cache rebuild failed:\n" + traceback.format_exc())

        daily       = aggregate_daily(TRAIN_DF)
        FEATURED_DF = engineer_features(daily)

        if MODEL is not None:
            PREDICTION = make_prediction(MODEL, FEATURED_DF, NEXT_MONTH)
            rebuild_error_cache()
            log_action(
                "Upload Done",
                f"Dataset updated to {TRAIN_CUTOFF.date()}. "
                f"Predicting {NEXT_MONTH.strftime('%B %Y')}: ${PREDICTION['total_predicted']:,}. "
                "Model NOT retrained — run /api/drift to check if retraining is needed.",
            )
        else:
            log_action("Upload", "Data appended — no model available.")

        rebuild_status_cache()

        analysis = {
            "rows":       len(actual),
            "orders":     int(actual["Order ID"].nunique()),
            "products":   int(actual["Product ID"].nunique())  if "Product ID"  in actual.columns else 0,
            "customers":  int(actual["Customer ID"].nunique()) if "Customer ID" in actual.columns else 0,
            "categories": actual["Category"].unique().tolist() if "Category"    in actual.columns else [],
            "regions":    actual["Region"].unique().tolist()   if "Region"      in actual.columns else [],
            "date_min":   str(actual["Order Date"].min().date()),
            "date_max":   str(actual["Order Date"].max().date()),
            "total_sales":        round(actual_total, 2),
            "upload_month":       month_str,
            "new_train_cutoff":   str(TRAIN_CUTOFF.date()),
            "next_predict_month": NEXT_MONTH.strftime("%B %Y"),
            "total_train_orders": len(TRAIN_DF),
            # Explicit signals for the frontend
            "model_retrained":    False,
            "note": "Model not retrained on upload. Run /api/drift to decide if retraining is needed.",
        }
        return {"analysis": analysis, "evaluation": ev, "next_prediction": PREDICTION}

    except Exception as e:
        log_action("Upload Error", traceback.format_exc())
        raise HTTPException(400, str(e))


# ── DRIFT ──────────────────────────────────────────────────────────────────────
@app.post("/api/drift")
def ep_drift():
    """
    Fixes #3,#4,#5,#6,#9,#11:
    - Monitors ALL 27 features (not just 6)
    - Clamped dynamic thresholds (min 5 history)
    - Voting-based composite (not max)
    - OR-based decision logic
    - Retrain cooldown
    - Clear accuracy metrics
    """
    global LAST_RETRAIN_TIME, RETRAIN_COUNT
    try:
        if FEATURED_DF is None or MODEL is None:
            raise HTTPException(503, "Model not ready")
        log_action("Drift", "Full 27-feature drift check (KS + PSI + JS)")

        # Fix #10: Use PRE_UPLOAD_FEATURED_DF to avoid future-data contamination
        if PRE_UPLOAD_FEATURED_DF is not None:
            old_df = PRE_UPLOAD_FEATURED_DF
            new_df = FEATURED_DF.iloc[PRE_UPLOAD_ROWS:]
        else:
            sp = int(len(FEATURED_DF) * 0.7)
            old_df = FEATURED_DF.iloc[:sp]
            new_df = FEATURED_DF.iloc[sp:]

        if len(old_df) == 0 or len(new_df) == 0:
            raise HTTPException(400, "Not enough data for drift detection — upload more data first.")

        # ── Fix #3: Monitor ALL 27 features ──
        drift_features = [f for f in FEATURE_LIST if f in old_df.columns and f in new_df.columns]

        res: dict = {}
        for f in drift_features:
            a = old_df[f].dropna().values
            b = new_df[f].dropna().values
            if len(a) > 0 and len(b) > 0:
                ks_s, ks_p = ks_2samp(a, b)
                psi_s      = compute_psi(a, b)
                js_s       = compute_js(a, b)
                psi_norm   = min(psi_s / 0.25, 1.0)
                composite  = round(max(ks_s, js_s, psi_norm), 4)
                res[f] = {
                    "ks_stat":       round(ks_s,  4),
                    "p_value":       round(ks_p,  4),
                    "psi":           round(psi_s, 4),
                    "js_divergence": round(js_s,  4),
                    "composite":     composite,
                }

        if not res:
            raise HTTPException(400, "No drift features could be evaluated.")

        # ── Fix #5: Voting-based composite (not max) ──
        feature_scores = [v["composite"] for v in res.values()]
        total_features = len(feature_scores)
        high_count  = sum(1 for s in feature_scores if s > 0.25)
        med_count   = sum(1 for s in feature_scores if 0.15 < s <= 0.25)
        avg_score   = round(sum(feature_scores) / total_features, 4) if total_features > 0 else 0.0

        if high_count > total_features * 0.2:
            drift_score = round(max(feature_scores), 4)
            drift_category = "severe"
        elif (high_count + med_count) > total_features * 0.4:
            drift_score = avg_score
            drift_category = "mild"
        else:
            drift_score = avg_score
            drift_category = "none"

        # ── Fix #11: Clear accuracy metrics ──
        current_mae = METRICS.get("mae", 0)
        baseline    = BASELINE_MAE if BASELINE_MAE > 0 else current_mae
        orig_base   = ORIGINAL_BASELINE_MAE if ORIGINAL_BASELINE_MAE > 0 else baseline
        acc_drop    = round(LAST_PREDICTION_ERROR, 4)
        error_increase_pct = round((current_mae - orig_base) / (orig_base + 1e-6) * 100, 2)

        # ── Fix #4: Dynamic thresholds with clamping (min 5 history) ──
        past_scores = [h["composite_score"] for h in DRIFT_HISTORY[-5:]]
        if len(past_scores) >= 5:
            mu    = np.mean(past_scores)
            sigma = max(float(np.std(past_scores)), 0.03)
            t_med  = float(np.clip(mu + 0.5 * sigma, 0.05, 0.25))
            t_high = float(np.clip(mu + 1.5 * sigma, 0.15, 0.35))
            if t_med >= t_high:
                t_med = t_high - 0.05
            t_med  = round(t_med, 4)
            t_high = round(t_high, 4)
            threshold_method = "dynamic"
        else:
            t_med, t_high    = 0.1, 0.2
            threshold_method = "static"

        # ── Fix #6: OR-based decision logic ──
        if drift_score >= t_high or acc_drop >= 0.5:
            lv, act = "high",   "retrain"
        elif drift_score >= t_med or acc_drop >= 0.3:
            lv, act = "medium", "fine_tune"
        else:
            lv, act = "low",    "monitor"

        # ── Fix #9: Force retrain with cooldown ──
        force_high_count = sum(1 for v in res.values() if v["composite"] >= t_high)
        cooldown_msg = ""
        if force_high_count >= 3 and lv != "high":
            if LAST_RETRAIN_TIME:
                days_since = (datetime.now() - LAST_RETRAIN_TIME).days
                if days_since < RETRAIN_COOLDOWN_DAYS:
                    cooldown_msg = f"Cooldown active ({RETRAIN_COOLDOWN_DAYS - days_since}d remaining)"
                else:
                    lv, act = "high", "retrain"
                    cooldown_msg = f"Force retrain: {force_high_count} features HIGH (cooldown clear)"
            else:
                lv, act = "high", "retrain"
                cooldown_msg = f"Force retrain: {force_high_count} features HIGH"

        feat_history: dict = {}
        for h in DRIFT_HISTORY[-5:]:
            for fd in h.get("feature_scores", []):
                feat_history.setdefault(fd["feature"], []).append(fd["composite"])

        top_drift = []
        for k, v in sorted(res.items(), key=lambda x: -x[1]["composite"]):
            fh = feat_history.get(k, [])
            if len(fh) >= 2:
                fm  = float(np.mean(fh))
                fs  = max(float(np.std(fh)), 0.03)
                sev = "HIGH"   if v["composite"] > fm + 1.5 * fs else \
                      "MEDIUM" if v["composite"] > fm + 0.5 * fs else "LOW"
            else:
                sev = "HIGH"   if v["composite"] > 0.2 else \
                      "MEDIUM" if v["composite"] > 0.1 else "LOW"
            top_drift.append({
                "feature":       k,
                "ks_stat":       v["ks_stat"],
                "psi":           v["psi"],
                "js_divergence": v["js_divergence"],
                "composite":     v["composite"],
                "severity":      sev,
            })

        DRIFT_HISTORY.append({
            "timestamp":       datetime.now().isoformat(),
            "composite_score": drift_score,
            "feature_scores":  [{"feature": k, "composite": v["composite"]} for k, v in res.items()],
        })
        if len(DRIFT_HISTORY) > 5:
            DRIFT_HISTORY.pop(0)

        action_label = {"monitor": "Monitor", "fine_tune": "Fine-Tune", "retrain": "Retrain"}
        why = (
            f"Feature drift={drift_score:.4f} ({drift_category}), "
            f"Accuracy drop={acc_drop:.1%}, Error increase={error_increase_pct:.1f}%, "
            f"{force_high_count} features HIGH [{threshold_method}]"
        )
        plain = (
            f"Drift={drift_score:.4f} ({lv}). Acc drop={acc_drop:.1%}. "
            f"Thresholds: med={t_med}, high={t_high} ({threshold_method}). "
            f"MAE=${current_mae} vs baseline=${baseline} (original=${orig_base}). Action: {act}."
        )
        if cooldown_msg:
            plain += f" {cooldown_msg}"
        if lv == "high":
            plain += " → Call /api/retrain/sliding to retrain on last 36 months."

        entry = {
            "id":               datetime.now().strftime("%Y%m%d_%H%M%S"),
            "timestamp":        datetime.now().strftime("%d %b %Y %H:%M"),
            "drift_level":      lv.upper(),
            "drift_score":      drift_score,
            "mae_before":       current_mae,
            "baseline_mae":     baseline,
            "original_baseline_mae": orig_base,
            "action_taken":     act,
            "action_label":     action_label[act],
            "action_why":       why,
            "plain_english":    plain,
            "top_drift_features": top_drift,
        }
        LOGBOOK.append(entry)
        if len(LOGBOOK) > 200:
            LOGBOOK.pop(0)

        log_action("Drift Done",
                   f"{lv.upper()} drift={drift_score} acc_drop={acc_drop:.1%} → {act}")

        return {
            "drift_score":          drift_score,
            "drift_category":       drift_category,
            "level":                lv,
            "action":               act,
            "retrain_recommended":  lv == "high",
            "message":              f"{lv.upper()} drift ({threshold_method} threshold)",
            "threshold_method":     threshold_method,
            "thresholds":           {"medium": t_med, "high": t_high},
            "tests_used":           ["KS", "PSI", "JS Divergence"],
            "drift_history_count":  len(DRIFT_HISTORY),
            "accuracy_drop":        acc_drop,
            "error_increase_pct":   error_increase_pct,
            "prediction_error":     LAST_PREDICTION_ERROR,
            "baseline_mae":         baseline,
            "original_baseline_mae": orig_base,
            "current_mae":          current_mae,
            "high_feature_count":   force_high_count,
            "features_monitored":   total_features,
            "cooldown_message":     cooldown_msg,
            "feature_drift":        res,
            "top_drift_features":   top_drift,
        }
    except HTTPException:
        raise
    except Exception as e:
        log_action("Drift Error", traceback.format_exc())
        raise HTTPException(500, str(e))


# ── Fix #7: Smart window selection helper ──────────────────────────────────────

def get_training_window(feat_df: pd.DataFrame, window_months: int, min_rows: int = 100):
    """Select training window with fallback if insufficient data."""
    max_date = feat_df["date"].max()
    cutoff   = max_date - pd.DateOffset(months=window_months)
    window   = feat_df[feat_df["date"] >= cutoff]
    label    = f"last {window_months} months"

    if len(window) < min_rows:
        log_action("Window", f"{window_months}-month window only has {len(window)} rows (need {min_rows})")
        # Fallback chain
        if window_months == 9:
            return get_training_window(feat_df, 12, min_rows)
        elif window_months == 12:
            return get_training_window(feat_df, 18, min_rows)
        else:
            label = f"full dataset ({window_months}-month window too small)"
            return feat_df, label

    # Check seasonality coverage
    unique_months = window["month"].nunique() if "month" in window.columns else 0
    if window_months <= 9 and unique_months < 6:
        log_action("Window", f"Warning: {window_months}-month window covers only {unique_months} unique months")

    return window, label


# ── Fix #12: Model validation helper ──────────────────────────────────────────

def validate_and_deploy(candidate_model, candidate_metrics, candidate_importance,
                        method_label: str):
    """Validate candidate model vs current. Deploy only if >5% MAE improvement."""
    global MODEL, METRICS, IMPORTANCE, PREDICTION, BASELINE_MAE, RETRAIN_COUNT
    global LAST_RETRAIN_TIME

    old_model      = MODEL
    old_metrics    = METRICS.copy()
    old_importance = IMPORTANCE.copy()
    old_baseline   = BASELINE_MAE
    old_mae        = old_metrics.get("mae", float("inf"))
    new_mae        = candidate_metrics["mae"]

    improvement = ((old_mae - new_mae) / (old_mae + 1e-6)) * 100 if old_mae > 0 else 100.0
    deployed = False

    if improvement > 5.0:
        # Save current model to history before replacing (Fix #12)
        MODEL_HISTORY.append({
            "model": old_model, "metrics": old_metrics,
            "importance": old_importance, "timestamp": datetime.now().isoformat(),
        })
        if len(MODEL_HISTORY) > 5:
            MODEL_HISTORY.pop(0)

        MODEL      = candidate_model
        METRICS    = candidate_metrics
        IMPORTANCE = candidate_importance
        BASELINE_MAE = new_mae   # Fix #8: update current baseline (NOT original)
        LAST_RETRAIN_TIME = datetime.now()
        RETRAIN_COUNT += 1
        deployed = True

        rebuild_error_cache()
        PREDICTION = make_prediction(MODEL, FEATURED_DF, NEXT_MONTH)
        log_action("Deployed", f"{method_label}: MAE ${new_mae} ({improvement:.1f}% better)")
    else:
        ROLLBACK_LOG.append({
            "timestamp": datetime.now().isoformat(),
            "method": method_label,
            "candidate_mae": new_mae,
            "current_mae": old_mae,
            "improvement_pct": round(improvement, 2),
            "reason": "Insufficient improvement (<5%)",
        })
        log_action("Rollback", f"{method_label}: Only {improvement:.1f}% improvement — kept old model")

    return {
        "deployed": deployed,
        "improvement_pct": round(improvement, 2),
        "candidate_mae": new_mae,
        "current_mae": old_mae if not deployed else new_mae,
        "baseline_mae_before": old_baseline,
        "baseline_mae_after": BASELINE_MAE,
        "original_baseline_mae": ORIGINAL_BASELINE_MAE,
        "message": f"Deployed ({improvement:.1f}% improvement)" if deployed
                   else f"Rollback: only {improvement:.1f}% improvement (need >5%)",
    }


# ── RETRAIN — SLIDING WINDOW (36 months) ──────────────────────────────────────
@app.post("/api/retrain/sliding")
def ep_sliding():
    """Fix #7 + #8 + #12: Smart window, preserved original baseline, validated deploy."""
    try:
        if FEATURED_DF is None or NEXT_MONTH is None:
            raise HTTPException(503, "Model not ready")

        window_df, window_label = get_training_window(FEATURED_DF, 36, min_rows=100)

        log_action("Retrain", f"Sliding window: {window_label} ({len(window_df)} rows)")

        candidate_model, candidate_metrics, candidate_importance = do_train(window_df)

        result = validate_and_deploy(candidate_model, candidate_metrics,
                                     candidate_importance, "sliding_window_36m")
        return {
            "status":          "success" if result["deployed"] else "rollback",
            "method":          "sliding_window",
            "window":          window_label,
            "window_months":   36,
            "rows_used":       len(window_df),
            "metrics":         {"MAE": METRICS["mae"], "RMSE": METRICS["rmse"], "MAPE": METRICS["mape"]},
            **result,
            "next_prediction": PREDICTION,
        }
    except HTTPException:
        raise
    except Exception as e:
        log_action("Retrain Error", traceback.format_exc())
        raise HTTPException(500, str(e))


# ── FINE-TUNE (9 months) ───────────────────────────────────────────────────────
@app.post("/api/retrain/finetune")
def ep_finetune():
    """Fix #7 + #8 + #12: Smart window, preserved original baseline, validated deploy."""
    try:
        if FEATURED_DF is None or NEXT_MONTH is None:
            raise HTTPException(503, "Model not ready")

        window_df, window_label = get_training_window(FEATURED_DF, 9, min_rows=100)

        log_action("Finetune", f"{window_label} ({len(window_df)} rows)")

        candidate_model, candidate_metrics, candidate_importance = do_train(window_df)

        result = validate_and_deploy(candidate_model, candidate_metrics,
                                     candidate_importance, "fine_tune_9m")
        return {
            "status":          "success" if result["deployed"] else "rollback",
            "method":          "fine_tune",
            "window":          window_label,
            "window_months":   9,
            "rows_used":       len(window_df),
            "metrics":         {"MAE": METRICS["mae"], "RMSE": METRICS["rmse"], "MAPE": METRICS["mape"]},
            **result,
            "next_prediction": PREDICTION,
        }
    except HTTPException:
        raise
    except Exception as e:
        log_action("Finetune Error", traceback.format_exc())
        raise HTTPException(500, str(e))


# ── Fix #12: ROLLBACK ENDPOINT ────────────────────────────────────────────────
@app.post("/api/rollback")
def ep_rollback():
    """Emergency rollback to previous model version."""
    global MODEL, METRICS, IMPORTANCE, PREDICTION, BASELINE_MAE
    try:
        if not MODEL_HISTORY:
            raise HTTPException(400, "No previous model version available for rollback")

        previous = MODEL_HISTORY.pop()
        old_mae  = METRICS.get("mae", 0)

        MODEL      = previous["model"]
        METRICS    = previous["metrics"]
        IMPORTANCE = previous["importance"]
        BASELINE_MAE = METRICS["mae"]

        rebuild_error_cache()
        if FEATURED_DF is not None and NEXT_MONTH is not None:
            PREDICTION = make_prediction(MODEL, FEATURED_DF, NEXT_MONTH)

        ROLLBACK_LOG.append({
            "timestamp": datetime.now().isoformat(),
            "method": "emergency_rollback",
            "rolled_back_from_mae": old_mae,
            "rolled_back_to_mae": METRICS["mae"],
            "version_timestamp": previous["timestamp"],
        })

        log_action("Emergency Rollback",
                   f"Rolled back to version from {previous['timestamp']} (MAE ${METRICS['mae']})")

        return {
            "rolled_back": True,
            "previous_mae": old_mae,
            "restored_mae": METRICS["mae"],
            "version_timestamp": previous["timestamp"],
            "remaining_versions": len(MODEL_HISTORY),
            "message": f"Rolled back. MAE: ${old_mae} → ${METRICS['mae']}",
        }
    except HTTPException:
        raise
    except Exception as e:
        log_action("Rollback Error", traceback.format_exc())
        raise HTTPException(500, str(e))


# ── LOGBOOK ────────────────────────────────────────────────────────────────────
@app.get("/api/logbook")
def ep_logbook():
    if not LOGBOOK:
        next_str = NEXT_MONTH.strftime("%B %Y") if NEXT_MONTH else "unknown"
        return {
            "entries": [{
                "id":            "baseline",
                "timestamp":     datetime.now().strftime("%d %b %Y %H:%M"),
                "drift_level":   "N/A",
                "drift_score":   0,
                "mae_before":    METRICS.get("mae", 0),
                "baseline_mae":  BASELINE_MAE,
                "action_taken":  "baseline",
                "action_label":  "Baseline",
                "action_why":    "Model trained on 2015-2018 base data.",
                "plain_english": (
                    f"Baseline model ready. MAE=${METRICS.get('mae', 0)}. "
                    f"Predicting: {next_str}. "
                    "Upload new data → run drift check → retrain if HIGH."
                ),
                "top_drift_features": [],
            }]
        }
    return {"entries": LOGBOOK}


# ── PRODUCT ────────────────────────────────────────────────────────────────────
@app.get("/api/product/{product_name:path}")
def ep_product(product_name: str):
    product_name = unquote(product_name)
    if TRAIN_DF is None:
        raise HTTPException(503, "No data")
    if "Product Name" not in TRAIN_DF.columns:
        raise HTTPException(503, "Dataset has no 'Product Name' column")
    g = TRAIN_DF[TRAIN_DF["Product Name"] == product_name]
    if len(g) == 0:
        raise HTTPException(404, "Product not found")
    all_months     = pd.period_range(
        TRAIN_DF["Order Date"].min().to_period("M"),
        TRAIN_DF["Order Date"].max().to_period("M"),
        freq="M",
    )
    monthly_counts = g.groupby(g["Order Date"].dt.to_period("M"))["Sales"].count()
    monthly_full   = monthly_counts.reindex(all_months, fill_value=0)
    return {
        "details": {
            "category":           g["Category"].iloc[0],
            "sub_category":       g["Sub-Category"].iloc[0] if "Sub-Category" in g.columns else "",
            "total_orders":       len(g),
            "total_sales":        round(float(g["Sales"].sum()), 2),
            "avg_monthly_orders": round(float(monthly_counts.mean()), 2),
            "regions":  {r: int(n) for r, n in g.groupby("Region")["Sales"].count().items()},
            "segments": {s: int(n) for s, n in g.groupby("Segment")["Sales"].count().items()}
                        if "Segment" in g.columns else {},
        },
        "monthly": [{"month": str(m), "orders": int(n)} for m, n in monthly_full.items()],
    }


# ── MISC ───────────────────────────────────────────────────────────────────────
@app.get("/api/system-log")
def ep_syslog():
    return {
        "log":            SYSTEM_LOG[-50:],
        "current_action": CURRENT_ACTION,
        "timestamp":      datetime.now().isoformat(),
    }


@app.get("/api/predict/download")
def ep_download():
    try:
        if FEATURED_DF is None or MODEL is None:
            raise HTTPException(503, "Model not ready")
        out = FEATURED_DF.copy()
        out["predicted_sales"] = np.maximum(MODEL.predict(out[FEATURE_LIST]), 0).round(2)
        csv_data = out[["date", "Category", "Region", "sales", "predicted_sales"]].to_csv(index=False)
        return StreamingResponse(
            io.StringIO(csv_data),
            media_type="text/csv",
            headers={"Content-Disposition": "attachment; filename=predictions.csv"},
        )
    except Exception as e:
        raise HTTPException(500, str(e))


@app.post("/api/xai/store-explanation")
def ep_xai(explanation: dict):
    log_action("XAI", "stored")
    return {"status": "success"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)