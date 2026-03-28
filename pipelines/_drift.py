from scipy.stats import ks_2samp
from sklearn.metrics import mean_absolute_error
from sklearn.preprocessing import MinMaxScaler
from pipelines.utils import logger, PROCESSED_DIR, MODEL_DIR
import pandas as pd
import numpy as np
import joblib
import os
import json
from datetime import date

REPORT_DIR  = os.path.join(os.path.dirname(os.path.dirname(__file__)), "reports")
DRIFT_LOG   = os.path.join(REPORT_DIR, "drift_history.csv")
SCHEMA_PATH = os.path.join(MODEL_DIR, "feature_schema.pkl")

# ── Thresholds ───────────────────────────────────────────
KS_LOW  = 0.1;  KS_HIGH  = 0.3
PSI_LOW = 0.1;  PSI_HIGH = 0.25
DRIFT_FEATURES = ["sell_price", "lag_7", "lag_28", "rmean_7", "rmean_28"]


# ── Upgrade B: Feature Schema ────────────────────────────
def save_feature_schema(feature_cols):
    os.makedirs(MODEL_DIR, exist_ok=True)
    joblib.dump(feature_cols, SCHEMA_PATH)
    logger.info(f"✅ Feature schema saved → {len(feature_cols)} features")


def load_feature_schema():
    if os.path.exists(SCHEMA_PATH):
        return joblib.load(SCHEMA_PATH)
    return None


def get_schema_feature_cols():
    """Fix 1: always return the saved training feature list — never recompute from dtype."""
    cols = load_feature_schema()
    if cols is None:
        raise FileNotFoundError("feature_schema.pkl not found — run train_and_predict() first")
    return cols


def validate_feature_schema(X_cols):
    expected = load_feature_schema()
    if expected is None:
        logger.warning("⚠️ No feature schema found — skipping schema check")
        return True
    missing  = set(expected) - set(X_cols)
    extra    = set(X_cols) - set(expected)
    if missing or extra:
        logger.error(f"❌ Feature mismatch — missing: {missing} | extra: {extra}")
        return False
    return True


# ── Upgrade C: Baseline MAE ──────────────────────────────
def _get_baseline_mae():
    try:
        m = pd.read_csv(os.path.join(REPORT_DIR, "metrics_summary.csv"))
        return float(m["MAE"].iloc[0])
    except Exception:
        return 1.0


# ── Method 1: PSI ────────────────────────────────────────
def compute_psi(expected, actual, bins=10):
    breakpoints      = np.linspace(0, 100, bins + 1)
    expected_pct     = np.histogram(expected, breakpoints)[0] / len(expected)
    actual_pct       = np.histogram(actual,   breakpoints)[0] / len(actual)
    expected_pct     = np.where(expected_pct == 0, 1e-6, expected_pct)
    actual_pct       = np.where(actual_pct   == 0, 1e-6, actual_pct)
    psi = np.sum((expected_pct - actual_pct) * np.log(expected_pct / actual_pct))
    return round(float(psi), 4)


# ── Method 2: KS Test with normalization ─────────────────
def compute_ks(actual, predicted):
    # Upgrade C: normalize before KS to fix integer vs float scale mismatch
    scaler = MinMaxScaler()
    a_scaled = scaler.fit_transform(actual.reshape(-1, 1)).flatten()
    p_scaled = scaler.fit_transform(predicted.reshape(-1, 1)).flatten()
    stat, _  = ks_2samp(a_scaled, p_scaled)
    return round(float(stat), 4)


# ── Method 3: Error-Based Drift ──────────────────────────
def compute_error_drift(y_true, y_pred):
    baseline_mae = _get_baseline_mae()
    current_mae  = mean_absolute_error(y_true, y_pred)
    if current_mae > baseline_mae * 1.2:
        return "high", round(current_mae, 6)
    elif current_mae > baseline_mae * 1.1:
        return "medium", round(current_mae, 6)
    else:
        return "low", round(current_mae, 6)


# ── Upgrade C: Weighted Drift Score ──────────────────────
def weighted_drift_score(psi, ks, error_level):
    """More stable than hard thresholds — weighted combination."""
    error_score = {"low": 0.0, "medium": 0.5, "high": 1.0}.get(error_level, 0.5)
    score = round(0.4 * psi + 0.3 * ks + 0.3 * error_score, 4)
    if score < 0.1:
        return "low",    score
    elif score < 0.3:
        return "medium", score
    else:
        return "high",   score


# ── Feature-wise PSI ─────────────────────────────────────
def compute_feature_drift(train_df, new_df):
    results = {}
    for col in DRIFT_FEATURES:
        if col in train_df.columns and col in new_df.columns:
            t = train_df[col].dropna().values
            n = new_df[col].dropna().values
            if len(t) > 0 and len(n) > 0:
                results[col] = compute_psi(t, n)
    return results


# ── Upgrade C: Drift History Logging ─────────────────────
def _log_drift(result):
    os.makedirs(REPORT_DIR, exist_ok=True)
    row = {
        "date":        str(date.today()),
        "ks_stat":     result.get("ks_stat"),
        "psi":         result.get("psi"),
        "mae":         result.get("mae"),
        "error_level": result.get("error_level"),
        "drift_score": result.get("drift_score"),
        "level":       result.get("level"),
    }
    # append feature PSI values
    for col, val in result.get("feature_drift", {}).items():
        row[f"psi_{col}"] = val

    df_row = pd.DataFrame([row])
    if os.path.exists(DRIFT_LOG):
        existing = pd.read_csv(DRIFT_LOG)
        pd.concat([existing, df_row], ignore_index=True).to_csv(DRIFT_LOG, index=False)
    else:
        df_row.to_csv(DRIFT_LOG, index=False)
    logger.info(f"📝 Drift logged → {DRIFT_LOG}")


# ── Main Entry Point ─────────────────────────────────────
def run_drift_check():
    actual = pd.read_parquet(f"{PROCESSED_DIR}/actual_month.parquet")
    preds  = pd.read_parquet(f"{PROCESSED_DIR}/predictions.parquet")
    train  = pd.read_parquet(f"{PROCESSED_DIR}/features.parquet")

    actual_sales = actual["sales"].dropna().values if "sales" in actual.columns else np.array([])
    pred_sales   = preds["yhat"].dropna().values   if "yhat"  in preds.columns  else np.array([])

    logger.info(f"actual_sales: {len(actual_sales)} | pred_sales: {len(pred_sales)}")

    if len(actual_sales) == 0 or len(pred_sales) == 0:
        logger.warning("⚠️ Empty data.")
        return {"ks_stat": None, "psi": None, "mae": None,
                "error_level": None, "drift_score": None,
                "feature_drift": {}, "level": "unknown"}

    psi         = compute_psi(train["sales"].dropna().values, actual_sales)
    ks          = compute_ks(actual_sales, pred_sales)
    min_len     = min(len(actual_sales), len(pred_sales))
    error_level, current_mae = compute_error_drift(actual_sales[:min_len], pred_sales[:min_len])
    feature_drift = compute_feature_drift(train, actual)

    # Upgrade C: weighted score for stable decision
    level, drift_score = weighted_drift_score(psi, ks, error_level)

    # Fix 5: high PSI → override to high drift (skip fine-tune)
    if psi > 0.2 and level != "high":
        logger.warning(f"⚠️ PSI={psi} > 0.2 → overriding level to HIGH (skip fine-tune)")
        level = "high"

    logger.info(f"📊 PSI:{psi} | KS:{ks} | MAE:{current_mae} | Score:{drift_score} → {level.upper()}")

    result = {
        "ks_stat":       ks,
        "psi":           psi,
        "mae":           current_mae,
        "error_level":   error_level,
        "drift_score":   drift_score,
        "feature_drift": feature_drift,
        "level":         level,
    }

    # Upgrade C: log to drift_history.csv
    _log_drift(result)

    return result
