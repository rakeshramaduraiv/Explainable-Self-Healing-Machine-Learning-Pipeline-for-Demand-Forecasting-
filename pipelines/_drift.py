from scipy.stats import ks_2samp
from sklearn.metrics import mean_absolute_error
from pipelines.utils import logger, PROCESSED_DIR, MODEL_DIR
import pandas as pd
import numpy as np
import joblib
import os
import shap
from datetime import date

REPORT_DIR  = os.path.join(os.path.dirname(os.path.dirname(__file__)), "reports")
DRIFT_LOG   = os.path.join(REPORT_DIR, "drift_history.csv")
SCHEMA_PATH = os.path.join(MODEL_DIR, "feature_schema.pkl")
MIN_SAMPLES = 50

# All engineered features used for PSI — not just a subset
DRIFT_FEATURES = [
    "sell_price", "lag_1", "lag_7", "lag_14", "lag_28",
    "rmean_7", "rmean_14", "rmean_28",
    "rstd_7", "rstd_14", "rstd_28",
    "price_norm", "is_weekend", "dayofweek", "month",
]


# ── Feature Schema ────────────────────────────────────────
def save_feature_schema(feature_cols):
    os.makedirs(MODEL_DIR, exist_ok=True)
    joblib.dump(feature_cols, SCHEMA_PATH)
    logger.info(f"Feature schema saved -> {len(feature_cols)} features")


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
        logger.warning("No feature schema found — skipping schema check")
        return True
    missing = set(expected) - set(X_cols)
    extra   = set(X_cols) - set(expected)
    if missing or extra:
        logger.error(f"Feature mismatch — missing: {missing} | extra: {extra}")
        return False
    return True


# ── Baseline MAE ──────────────────────────────────────────
def _get_baseline_mae():
    try:
        m = pd.read_csv(os.path.join(REPORT_DIR, "metrics_summary.csv"))
        return float(m["MAE"].iloc[0])
    except Exception:
        return 1.0


# ── 1. PSI — Feature Distribution Drift ──────────────────
# Compares: training feature distribution vs new upload features
# PSI < 0.1  → no drift
# 0.1–0.2    → medium drift
# > 0.2      → high drift
def compute_psi(expected, actual, bins=10):
    expected = np.array(expected, dtype=float)
    actual   = np.array(actual,   dtype=float)
    breakpoints  = np.unique(np.percentile(expected, np.linspace(0, 100, bins + 1)))
    if len(breakpoints) < 2:
        return 0.0
    expected_pct = np.histogram(expected, breakpoints)[0] / len(expected)
    actual_pct   = np.histogram(actual,   breakpoints)[0] / len(actual)
    expected_pct = np.where(expected_pct == 0, 1e-6, expected_pct)
    actual_pct   = np.where(actual_pct   == 0, 1e-6, actual_pct)
    psi = np.sum((expected_pct - actual_pct) * np.log(expected_pct / actual_pct))
    return round(float(psi), 4)


# ── 2. KS — Target Distribution Drift ────────────────────
# Compares: training sales distribution vs actual sales distribution
# NOT actual vs predicted — that is performance, not concept drift
# KS < 0.1  → stable
# 0.1–0.2   → medium drift
# > 0.2     → strong drift
def compute_ks(train_sales, actual_sales):
    stat, _ = ks_2samp(train_sales, actual_sales)
    return round(float(stat), 4)


# ── 3. Performance Drift — MAE Ratio ─────────────────────
# error_ratio = current_mae / baseline_mae
# <= 1.1  → stable
# 1.1–1.3 → medium drift
# > 1.3   → high drift
def compute_error_drift(y_true, y_pred):
    baseline_mae = _get_baseline_mae()
    current_mae  = mean_absolute_error(y_true, y_pred)
    error_ratio  = current_mae / baseline_mae if baseline_mae > 0 else 1.0
    if error_ratio > 1.3:
        return "high",   round(current_mae, 6)
    elif error_ratio > 1.1:
        return "medium", round(current_mae, 6)
    else:
        return "low",    round(current_mae, 6)


# ── 4. Weighted Score → Final Decision ───────────────────
# score = 0.35*PSI + 0.35*KS + 0.30*error_score
# < 0.1  → LOW    (monitor only)
# 0.1–0.2 → MEDIUM (fine-tune)
# >= 0.2  → HIGH   (sliding window retrain)
def weighted_drift_score(psi, ks, error_level):
    error_score = {"low": 0.0, "medium": 0.5, "high": 1.0}.get(error_level, 0.5)
    score = round(0.35 * psi + 0.35 * ks + 0.30 * error_score, 4)
    if score < 0.1:
        return "low",    score
    elif score < 0.2:
        return "medium", score
    else:
        return "high",   score


# ── PSI across all drift features ────────────────────────
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
        "error_ratio": result.get("error_ratio"),
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
    logger.info(f"Drift logged -> {DRIFT_LOG}")


def _check_drift_trend():
    if not os.path.exists(DRIFT_LOG):
        return
    history = pd.read_csv(DRIFT_LOG)
    if len(history) >= 3 and history["drift_score"].tail(3).mean() > 0.2:
        logger.warning("Continuous drift trend detected (3-run avg > 0.2) — consider full retrain")


# ── Main Entry Point ──────────────────────────────────────
def run_drift_check():
    actual = pd.read_parquet(f"{PROCESSED_DIR}/actual_month.parquet")
    train  = pd.read_parquet(f"{PROCESSED_DIR}/features.parquet")

    # FIX 1: force datetime on both sides
    actual["date"] = pd.to_datetime(actual["date"])
    train["date"]  = pd.to_datetime(train["date"])

    _EMPTY = {"ks_stat": None, "psi": None, "mae": None,
              "error_ratio": None, "error_level": None,
              "drift_score": None, "feature_drift": {}, "level": "unknown"}

    if "sales" not in actual.columns:
        logger.warning("Missing sales column in actual upload")
        return _EMPTY

    # FIX 2 + FIX 4: smart predictions source — use next_month_predictions
    # when upload dates don't overlap with training predictions
    actual_min     = actual["date"].min()
    preds_path     = f"{PROCESSED_DIR}/predictions.parquet"
    next_pred_path = f"{PROCESSED_DIR}/next_month_predictions.parquet"
    preds = None

    if os.path.exists(preds_path):
        _p = pd.read_parquet(preds_path)
        _p["date"] = pd.to_datetime(_p["date"])
        if _p["date"].max() >= actual_min:
            preds = _p
            logger.info("Using predictions.parquet for drift check")

    if preds is None and os.path.exists(next_pred_path):
        _p = pd.read_parquet(next_pred_path)
        _p["date"] = pd.to_datetime(_p["date"])
        if "predicted_sales" in _p.columns and "yhat" not in _p.columns:
            _p = _p.rename(columns={"predicted_sales": "yhat"})
        if _p["date"].max() >= actual_min:
            preds = _p
            logger.info("Using next_month_predictions.parquet for drift check")

    # Last resort: use any available predictions file so PSI + KS can still run
    if preds is None:
        for _fallback in [preds_path, next_pred_path]:
            if os.path.exists(_fallback):
                _p = pd.read_parquet(_fallback)
                _p["date"] = pd.to_datetime(_p["date"])
                if "predicted_sales" in _p.columns and "yhat" not in _p.columns:
                    _p = _p.rename(columns={"predicted_sales": "yhat"})
                if "yhat" in _p.columns:
                    preds = _p
                    logger.warning(f"No date-matching predictions — using {_fallback} for MAE drift only")
                    break

    if preds is None or "yhat" not in preds.columns:
        logger.warning("No predictions file available")
        return _EMPTY

    # FIX 3: normalise ID — strip _validation suffix on both sides
    actual_clean = actual[["id", "date", "sales"]].copy()
    preds_clean  = preds[["id", "date", "yhat"]].copy()
    actual_clean["id"] = actual_clean["id"].str.replace("_validation", "", regex=False)
    preds_clean["id"]  = preds_clean["id"].str.replace("_validation", "", regex=False)

    # FIX 5: hard check — only warn, don't return _EMPTY
    # PSI and KS can still run without predictions overlap
    merged = actual_clean.merge(preds_clean, on=["id", "date"], how="inner")
    if len(merged) == 0:
        logger.warning(
            "No overlapping rows between actual and predictions — "
            "MAE drift skipped. PSI + KS will still run."
        )
        actual_sales = actual_clean["sales"].values
        pred_sales   = np.array([])
    else:
        actual_sales = merged["sales"].values
        pred_sales   = merged["yhat"].values

    if len(actual_sales) < MIN_SAMPLES:
        logger.warning(f"Only {len(actual_sales)} rows — too few for reliable drift")
        return _EMPTY

    logger.info(f"Aligned rows: {len(merged):,} | upload: {actual['date'].min().date()} -> {actual['date'].max().date()}")

    # ── 1. PSI: feature distribution drift ───────────────
    # Uses actual_month_features.parquet (engineered, not raw upload)
    # PSI does NOT need predictions — compares training vs new upload features
    actual_feat_path = f"{PROCESSED_DIR}/actual_month_features.parquet"
    if os.path.exists(actual_feat_path):
        actual_feat = pd.read_parquet(actual_feat_path)

        if actual_feat.empty:
            logger.error("actual_month_features.parquet is empty — feature generation failed")
            return _EMPTY

        expected_schema = load_feature_schema()
        if expected_schema is not None:
            feat_cols  = [c for c in actual_feat.columns if c not in {"id", "date", "sales"}]
            missing_fc = set(expected_schema) - set(feat_cols)
            extra_fc   = set(feat_cols) - set(expected_schema)
            if missing_fc or extra_fc:
                logger.error(f"Feature schema mismatch — missing:{missing_fc} extra:{extra_fc}")
                return _EMPTY

        psi_values = []
        for col in DRIFT_FEATURES:
            if col in train.columns and col in actual_feat.columns:
                psi_values.append(compute_psi(
                    train[col].dropna().values,
                    actual_feat[col].dropna().values
                ))
        psi           = round(float(np.mean(psi_values)), 4) if psi_values else 0.0
        feature_drift = compute_feature_drift(train, actual_feat)
        logger.info(f"PSI computed across {len(psi_values)} features: {psi}")
    else:
        psi           = compute_psi(train["sales"].dropna().values, actual_sales)
        feature_drift = {}
        logger.warning("actual_month_features.parquet not found — using sales-only PSI")

    # ── 2. KS: training sales vs actual sales ────────────
    # Correct: compare distributions, NOT actual vs predicted
    train_sales = train["sales"].dropna().values
    ks = compute_ks(train_sales, actual_sales)
    logger.info(f"KS (train_sales vs actual_sales): {ks}")

    # ── 3. Performance drift: MAE ratio vs baseline ──────
    # Only compute if we have matching predictions for this month
    # If no overlap, use error_level=low (PSI+KS still drive the decision)
    if len(merged) > 0:
        error_level, current_mae = compute_error_drift(actual_sales, pred_sales)
        baseline_mae = _get_baseline_mae()
        error_ratio  = round(current_mae / baseline_mae, 4) if baseline_mae > 0 else 1.0
        logger.info(f"MAE: current={current_mae:.4f} baseline={baseline_mae:.4f} ratio={error_ratio}")
    else:
        error_level  = "low"
        current_mae  = None
        error_ratio  = None
        logger.info("No date-matching predictions — MAE drift skipped, using PSI+KS only")

    # ── 4. Weighted score → final decision ───────────────
    level, drift_score = weighted_drift_score(psi, ks, error_level)

    # PSI override: strong feature drift forces HIGH
    if psi > 0.2 and level != "high":
        logger.warning(f"PSI={psi} > 0.2 -> overriding to HIGH")
        level = "high"

    if feature_drift:
        top = sorted(feature_drift.items(), key=lambda x: x[1], reverse=True)[:3]
        logger.info(f"Top drift features: {top}")

    logger.info(f"PSI:{psi} | KS:{ks} | MAE_ratio:{error_ratio} | Score:{drift_score} -> {level.upper()}")

    result = {
        "ks_stat":       ks,
        "psi":           psi,
        "mae":           current_mae,
        "error_ratio":   error_ratio,
        "error_level":   error_level,
        "drift_score":   drift_score,
        "feature_drift": feature_drift,
        "level":         level,
    }

    _log_drift(result)
    _check_drift_trend()

    return result


# ── SHAP Explanation ──────────────────────────────────────
def run_shap_explanation(sample_n: int = 500) -> dict:
    feat_path = os.path.join(PROCESSED_DIR, "actual_month_features.parquet")
    if not os.path.exists(feat_path):
        logger.warning("SHAP skipped — actual_month_features.parquet not found")
        return {}

    model  = joblib.load(os.path.join(MODEL_DIR, "model.pkl"))
    X_cols = load_feature_schema()
    if X_cols is None:
        logger.warning("SHAP skipped — feature schema not found")
        return {}

    df        = pd.read_parquet(feat_path)
    available = [c for c in X_cols if c in df.columns]
    X         = df[available].dropna().sample(min(sample_n, len(df)), random_state=42)

    explainer   = shap.TreeExplainer(model)
    shap_values = explainer.shap_values(X)

    mean_abs = pd.Series(
        np.abs(shap_values).mean(axis=0), index=available
    ).sort_values(ascending=False)

    shap_df = mean_abs.reset_index()
    shap_df.columns = ["feature", "mean_abs_shap"]
    shap_df["mean_abs_shap"] = shap_df["mean_abs_shap"].round(4)

    top5        = shap_df.head(5)
    summary_str = ", ".join(f"{r.feature}({r.mean_abs_shap})" for _, r in top5.iterrows())

    lines = [f"  - {_shap_feature_explain(r.feature, r.mean_abs_shap)}" for _, r in top5.iterrows()]
    plain_text = (
        "The model's predictions this month were most influenced by:\n" +
        "\n".join(lines) +
        "\n\nFeatures with higher SHAP values had a stronger effect on whether "
        "the model predicted high or low sales for each SKU."
    )

    logger.info(f"SHAP top features: {summary_str}")
    return {"shap_df": shap_df, "summary_str": summary_str, "plain_text": plain_text}


_FEATURE_DESCRIPTIONS = {
    "sell_price":  "Selling price of the item",
    "lag_1":       "Yesterday's actual sales",
    "lag_7":       "Sales from 7 days ago (same weekday last week)",
    "lag_14":      "Sales from 14 days ago",
    "lag_28":      "Sales from 28 days ago (same weekday last month)",
    "rmean_7":     "Average sales over the last 7 days",
    "rmean_14":    "Average sales over the last 14 days",
    "rmean_28":    "Average sales over the last 28 days",
    "rstd_7":      "Sales variability over the last 7 days",
    "rstd_14":     "Sales variability over the last 14 days",
    "rstd_28":     "Sales variability over the last 28 days",
    "dayofweek":   "Day of the week (0=Monday, 6=Sunday)",
    "is_weekend":  "Whether the day is a weekend",
    "month":       "Month of the year",
    "year":        "Year",
    "weekofyear":  "Week number within the year",
    "wm_yr_wk":    "Walmart fiscal week number",
    "snap_CA":     "SNAP benefit active in California",
    "snap_TX":     "SNAP benefit active in Texas",
    "snap_WI":     "SNAP benefit active in Wisconsin",
    "price_norm":  "Normalised price (0=cheapest, 1=most expensive for this SKU)",
    "price_max":   "Maximum historical price for this SKU",
    "price_min":   "Minimum historical price for this SKU",
    "dow_sin":     "Cyclical encoding of day-of-week (sine)",
    "dow_cos":     "Cyclical encoding of day-of-week (cosine)",
    "item_id":     "Encoded product identifier",
    "dept_id":     "Encoded department (e.g. FOODS_1)",
    "cat_id":      "Encoded category (FOODS / HOBBIES / HOUSEHOLD)",
    "store_id":    "Encoded store identifier",
    "state_id":    "Encoded state (CA / TX / WI)",
}


def _shap_feature_explain(feature: str, shap_val: float) -> str:
    desc = _FEATURE_DESCRIPTIONS.get(feature, feature)
    return f"{desc} — average impact on prediction: {shap_val:.4f} units"
