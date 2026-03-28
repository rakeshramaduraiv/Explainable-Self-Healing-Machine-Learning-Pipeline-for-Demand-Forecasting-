import os
import json
import logging
import numpy as np
import pandas as pd
from datetime import datetime

# ── Paths ─────────────────────────────────────────────────
PROJECT_ROOT  = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
DATA_DIR      = os.path.join(PROJECT_ROOT, "data")
RAW_DIR       = os.path.join(DATA_DIR, "raw")
PROCESSED_DIR = os.path.join(DATA_DIR, "processed")
REPORT_DIR    = os.path.join(PROJECT_ROOT, "reports")
MODEL_DIR     = os.path.join(PROJECT_ROOT, "models", "lightgbm")

for _p in [DATA_DIR, RAW_DIR, PROCESSED_DIR, REPORT_DIR, MODEL_DIR]:
    os.makedirs(_p, exist_ok=True)

# Fix 5: central config — single source of truth for all thresholds
CONFIG = {
    "max_trees":           1500,
    "max_fine_tune_rounds": 3,
    "psi_high_threshold":  0.2,
    "drift_low":           0.1,
    "drift_high":          0.3,
    "window_months":       6,
    "retrain_improvement": 0.98,   # new RMSE must be < old * this
    "regression_tolerance": 1.05,  # new RMSE on old val must be < old * this
}

# Fix 1: dual-handler logging — file + console
LOG_FORMAT = "%(asctime)s | %(levelname)s | %(message)s"
_log_file  = os.path.join(REPORT_DIR, "pipeline.log")

logging.basicConfig(
    level=logging.INFO,
    format=LOG_FORMAT,
    handlers=[
        logging.FileHandler(_log_file, encoding="utf-8"),
        logging.StreamHandler(),
    ]
)
logger = logging.getLogger("forecasting")


# ── Metrics ───────────────────────────────────────────────
def mae(y, yhat):
    return float(np.mean(np.abs(np.array(y) - np.array(yhat))))

def rmse(y, yhat):
    return float(np.sqrt(np.mean((np.array(y) - np.array(yhat)) ** 2)))

# Fix 2: MAPE excludes zero-sales rows — they distort the metric
def mape(y, yhat):
    y, yhat = np.array(y), np.array(yhat)
    mask = y != 0
    if mask.sum() == 0:
        return 0.0
    return float(np.mean(np.abs((y[mask] - yhat[mask]) / y[mask])) * 100)

def evaluate_forecast(y_true, y_pred):
    return {"MAE": mae(y_true, y_pred), "RMSE": rmse(y_true, y_pred), "MAPE": mape(y_true, y_pred)}


# ── Fix 3: DataFrame validator ────────────────────────────
def validate_dataframe(df, name="dataframe"):
    if df.empty:
        raise ValueError(f"{name} is empty")
    nulls = df.isnull().sum().sum()
    if nulls > 0:
        logger.warning(f"⚠️ {name} has {nulls:,} missing values")


# ── File utilities ────────────────────────────────────────
def save_json(obj, path):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        json.dump(obj, f, indent=2)
    logger.info(f"✅ JSON saved → {path}")

def load_json(path):
    if not os.path.exists(path):
        raise FileNotFoundError(f"JSON not found: {path}")
    with open(path, "r") as f:
        return json.load(f)

def save_dataframe(df, path, index=False):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    if path.endswith(".csv"):
        df.to_csv(path, index=index)
    elif path.endswith(".parquet"):
        df.to_parquet(path, index=index)
    else:
        raise ValueError("Unsupported format — use .csv or .parquet")
    logger.info(f"✅ DataFrame saved → {path}")

def load_dataframe(path):
    if not os.path.exists(path):
        raise FileNotFoundError(f"File not found: {path}")
    if path.endswith(".csv"):
        return pd.read_csv(path)
    elif path.endswith(".parquet"):
        return pd.read_parquet(path)
    else:
        raise ValueError("Unsupported format — use .csv or .parquet")

# Fix 4: versioned parquet save — preserves history, never overwrites
def save_versioned(df, base_path):
    ts   = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = f"{base_path}_{ts}.parquet"
    os.makedirs(os.path.dirname(path), exist_ok=True)
    df.to_parquet(path, index=False)
    logger.info(f"✅ Versioned save → {path}")
    return path


if __name__ == "__main__":
    logger.info(f"PROJECT_ROOT: {PROJECT_ROOT}")
    logger.info(f"RAW_DIR contents: {os.listdir(RAW_DIR) if os.path.exists(RAW_DIR) else 'missing'}")
    y_true = np.array([100, 200, 300])
    y_pred = np.array([110, 190, 310])
    logger.info(f"Metrics self-test → {evaluate_forecast(y_true, y_pred)}")
