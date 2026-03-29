from scipy.stats import ks_2samp
from sklearn.metrics import mean_absolute_error
from sklearn.preprocessing import MinMaxScaler
from pipelines.utils import logger, PROCESSED_DIR, MODEL_DIR
import pandas as pd
import numpy as np
import joblib
import os
from datetime import date

REPORT_DIR     = os.path.join(os.path.dirname(os.path.dirname(__file__)), "reports")
DRIFT_LOG      = os.path.join(REPORT_DIR, "drift_history.csv")
SCHEMA_PATH    = os.path.join(MODEL_DIR, "feature_schema.pkl")
DRIFT_FEATURES = ["sell_price", "lag_7", "lag_28", "rmean_7", "rmean_28"]
MIN_SAMPLES    = 50
MIN_UPLOAD_ROWS = 1_000  # minimum rows for reliable drift detection


# ── Feature Schema ────────────────────────────────────────
def save_feature_schema(feature_cols):
    os.makedirs(MODEL_DIR, exist_ok=True)
    joblib.dump(feature_cols, SCHEMA_PATH)
    logger.info(f"✅ Feature schema saved → {len(feature_cols)} features")


def load_feature_schema():
    if os.path.exists(SCHEMA_PATH):
        return joblib.load(SCHEMA_PATH)
    return None


def get_schema_feature_cols():
    cols = load_feature_schema()
    if cols is None:
        raise FileNotFoundError("feature_schema.pkl not found — run train_and_predict() first")
    return cols


def validate_feature_schema(X_cols):
    expected = load_feature_schema()
    if expected is None:
        logger.warning("⚠️ No feature schema found — skipping schema check")
        return True
    missing = set(expected) - set(X_cols)
    extra   = set(X_cols) - set(expected)
    if missing or extra:
        logger.error(f"❌ Feature mismatch — missing: {missing} | extra: {extra}")
        return False
    return True


# ── Baseline MAE ──────────────────────────────────────────
def _get_baseline_mae():
    try:
        m = pd.read_csv(os.path.join(REPORT_DIR, "metrics_summary.csv"))
        return float(m["MAE"].iloc[0])
    except Exception:
        return 1.0


# ── Fix 1: PSI with percentile-based bins ────────────────
def compute_psi(expected, actual, bins=10):
    expected = np.array(expected, dtype=float)
    actual   = np.array(actual,   dtype=float)
    # percentile bins from expected distribution — works for any scale
    breakpoints  = np.unique(np.percentile(expected, np.linspace(0, 100, bins + 1)))
    if len(breakpoints) < 2:
        return 0.0
    expected_pct = np.histogram(expected, breakpoints)[0] / len(expected)
    actual_pct   = np.histogram(actual,   breakpoints)[0] / len(actual)
    expected_pct = np.where(expected_pct == 0, 1e-6, expected_pct)
    actual_pct   = np.where(actual_pct   == 0, 1e-6, actual_pct)
    psi = np.sum((expected_pct - actual_pct) * np.log(expected_pct / actual_pct))
    return round(float(psi), 4)


# ── Fix 5: KS vs historical distribution (not vs predictions) ──
def compute_ks(train_sales, actual_sales):
    scaler   = MinMaxScaler()
    t_scaled = scaler.fit_transform(train_sales.reshape(-1, 1)).flatten()
    a_scaled = scaler.fit_transform(actual_sales.reshape(-1, 1)).flatten()
    stat, _  = ks_2samp(t_scaled, a_scaled)
    return round(float(stat), 4)


# ── Error-Based Drift ─────────────────────────────────────
def compute_error_drift(y_true, y_pred):
    baseline_mae = _get_baseline_mae()
    current_mae  = mean_absolute_error(y_true, y_pred)
    if current_mae > baseline_mae * 1.2:
        return "high",   round(current_mae, 6)
    elif current_mae > baseline_mae * 1.1:
        return "medium", round(current_mae, 6)
    else:
        return "low",    round(current_mae, 6)


# ── Fix 6: balanced weighted score ───────────────────────
def weighted_drift_score(psi, ks, error_level):
    error_score = {"low": 0.0, "medium": 0.5, "high": 1.0}.get(error_level, 0.5)
    score = round(0.35 * psi + 0.35 * ks + 0.30 * error_score, 4)
    if score < 0.1:
        return "low",    score
    elif score < 0.3:
        return "medium", score
    else:
        return "high",   score


# ── Fix 3+4: feature-wise PSI on engineered features ─────
def compute_feature_drift(train_df, actual_feat_df):
    results = {}
    for col in DRIFT_FEATURES:
        if col in train_df.columns and col in actual_feat_df.columns:
            t = train_df[col].dropna().values
            n = actual_feat_df[col].dropna().values
            if len(t) > 0 and len(n) > 0:
                results[col] = compute_psi(t, n)
    return results


# ── Drift History Logging ─────────────────────────────────
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
    for col, val in result.get("feature_drift", {}).items():
        row[f"psi_{col}"] = val

    df_row = pd.DataFrame([row])
    if os.path.exists(DRIFT_LOG):
        pd.concat([pd.read_csv(DRIFT_LOG), df_row], ignore_index=True).to_csv(DRIFT_LOG, index=False)
    else:
        df_row.to_csv(DRIFT_LOG, index=False)
    logger.info(f"📝 Drift logged → {DRIFT_LOG}")


# ── Fix 9: drift trend analysis ──────────────────────────
def _check_drift_trend():
    if not os.path.exists(DRIFT_LOG):
        return
    history = pd.read_csv(DRIFT_LOG)
    if len(history) >= 3 and history["drift_score"].tail(3).mean() > 0.25:
        logger.warning("⚠️ Continuous drift trend detected (3-run avg > 0.25) — consider full retrain")


# ── Main Entry Point ─────────────────────────────────────
def run_drift_check():
    actual      = pd.read_parquet(f"{PROCESSED_DIR}/actual_month.parquet")
    preds       = pd.read_parquet(f"{PROCESSED_DIR}/predictions.parquet")
    train       = pd.read_parquet(f"{PROCESSED_DIR}/features.parquet")

    actual["date"] = pd.to_datetime(actual["date"])
    preds["date"]  = pd.to_datetime(preds["date"])
    train["date"]  = pd.to_datetime(train["date"])

    _EMPTY = {"ks_stat": None, "psi": None, "mae": None,
              "error_level": None, "drift_score": None,
              "feature_drift": {}, "level": "unknown"}

    if "sales" not in actual.columns or "yhat" not in preds.columns:
        logger.warning("⚠️ Missing sales or yhat column")
        return _EMPTY

    # Fix 2: align actual + predictions by id + date
    # Normalise id — strip _validation suffix if present so both sides match
    actual_clean = actual[["id", "date", "sales"]].copy()
    preds_clean  = preds[["id", "date", "yhat"]].copy()
    actual_clean["id"] = actual_clean["id"].str.replace("_validation$", "", regex=True)
    preds_clean["id"]  = preds_clean["id"].str.replace("_validation$", "", regex=True)

    merged = actual_clean.merge(preds_clean, on=["id", "date"], how="inner")
    if len(merged) == 0:
        logger.warning("⚠️ No matching (id, date) rows between actual and predictions — check id format or date range")
        return _EMPTY

    actual_sales = merged["sales"].values
    pred_sales   = merged["yhat"].values

    # Fix 7: minimum data guard
    if len(actual_sales) < MIN_SAMPLES:
        logger.warning(f"⚠️ Only {len(actual_sales)} aligned rows — too few for reliable drift")
        return _EMPTY

    logger.info(f"Aligned rows: {len(merged):,} | actual_sales: {len(actual_sales)} | pred_sales: {len(pred_sales)}")

    # Feature consistency check — actual features must match training schema
    actual_feat_path = f"{PROCESSED_DIR}/actual_month_features.parquet"
    if os.path.exists(actual_feat_path):
        actual_feat = pd.read_parquet(actual_feat_path)

        # Guard: empty feature output means feature generation failed
        if actual_feat.empty:
            logger.error("❌ actual_month_features.parquet is empty — feature generation failed")
            return _EMPTY

        # Guard: feature columns must match training schema
        expected_schema = load_feature_schema()
        if expected_schema is not None:
            feat_cols   = [c for c in actual_feat.columns if c not in {"id", "date", "sales"}]
            missing_fc  = set(expected_schema) - set(feat_cols)
            extra_fc    = set(feat_cols) - set(expected_schema)
            if missing_fc or extra_fc:
                logger.error(f"❌ Feature schema mismatch in actual_month_features — missing: {missing_fc} | extra: {extra_fc}")
                return _EMPTY

        psi_values  = []
        for col in DRIFT_FEATURES:
            if col in train.columns and col in actual_feat.columns:
                psi_values.append(compute_psi(train[col].dropna().values, actual_feat[col].dropna().values))
        psi           = round(float(np.mean(psi_values)), 4) if psi_values else compute_psi(train["sales"].dropna().values, actual_sales)
        feature_drift = compute_feature_drift(train, actual_feat)
    else:
        # fallback: sales-only PSI if features not yet generated
        psi           = compute_psi(train["sales"].dropna().values, actual_sales)
        feature_drift = {}
        logger.warning("⚠️ actual_month_features.parquet not found — using sales-only PSI")

    # Fix 5: KS compares actual vs historical training distribution (not vs predictions)
    train_tail = train["sales"].dropna().tail(len(actual_sales)).values
    ks          = compute_ks(train_tail, actual_sales)

    error_level, current_mae = compute_error_drift(actual_sales, pred_sales)

    # Fix 6: balanced weights
    level, drift_score = weighted_drift_score(psi, ks, error_level)

    # PSI override: high data drift → force retrain regardless of weighted score
    if psi > 0.2 and level != "high":
        logger.warning(f"⚠️ PSI={psi} > 0.2 → overriding to HIGH")
        level = "high"

    # Fix 8: log top drift features
    if feature_drift:
        top = sorted(feature_drift.items(), key=lambda x: x[1], reverse=True)[:3]
        logger.info(f"🔥 Top drift features: {top}")

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

    _log_drift(result)
    _check_drift_trend()  # Fix 9

    return result
