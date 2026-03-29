"""
logbook.py — Central history store for every pipeline event.
Writes human-readable entries to reports/logbook.csv.
Each row = one event (drift check, action taken, forecast, rollback).
"""
import os
import json
import pandas as pd
from datetime import datetime
from pipelines.utils import logger

REPORT_DIR   = os.path.join(os.path.dirname(os.path.dirname(__file__)), "reports")
LOGBOOK_PATH = os.path.join(REPORT_DIR, "logbook.csv")

COLUMNS = [
    "timestamp", "month_uploaded", "event_type", "drift_level",
    "drift_score", "psi", "ks_stat", "mae",
    "top_drift_features",          # e.g. "sell_price(0.42), lag_7(0.31)"
    "action_taken",                # MONITOR / FINE_TUNE / RETRAIN / ROLLBACK / FORECAST
    "action_reason",               # plain-English why
    "model_version_before",
    "model_version_after",
    "mae_before", "rmse_before",
    "mae_after",  "rmse_after",
    "shap_top_features",           # top SHAP contributors for this month
    "notes",
]


def _load() -> pd.DataFrame:
    if os.path.exists(LOGBOOK_PATH):
        return pd.read_csv(LOGBOOK_PATH)
    return pd.DataFrame(columns=COLUMNS)


def _save(df: pd.DataFrame):
    os.makedirs(REPORT_DIR, exist_ok=True)
    df.to_csv(LOGBOOK_PATH, index=False)


def _now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


# ── Public API ────────────────────────────────────────────

def log_drift_event(month_label: str, drift_result: dict, model_version: str = ""):
    """
    Called right after run_drift_check().
    Stores drift metrics + plain-English action reason.
    """
    level       = drift_result.get("level", "unknown")
    psi         = drift_result.get("psi")
    ks          = drift_result.get("ks_stat")
    mae_val     = drift_result.get("mae")
    score       = drift_result.get("drift_score")
    feat_drift  = drift_result.get("feature_drift", {})

    # Top drift features as readable string
    top_feats = sorted(feat_drift.items(), key=lambda x: x[1], reverse=True)[:3]
    top_str   = ", ".join(f"{f}({v:.3f})" for f, v in top_feats) if top_feats else "N/A"

    # Plain-English action reason
    reason = _build_reason(level, psi, ks, mae_val, score, top_feats)

    action = {
        "low":     "MONITOR",
        "medium":  "FINE_TUNE",
        "high":    "RETRAIN",
        "unknown": "SKIPPED",
    }.get(level, "SKIPPED")

    row = {c: "" for c in COLUMNS}
    row.update({
        "timestamp":           _now(),
        "month_uploaded":      month_label,
        "event_type":          "DRIFT_CHECK",
        "drift_level":         level.upper(),
        "drift_score":         round(score, 4) if score is not None else "",
        "psi":                 round(psi,   4) if psi   is not None else "",
        "ks_stat":             round(ks,    4) if ks    is not None else "",
        "mae":                 round(mae_val, 4) if mae_val is not None else "",
        "top_drift_features":  top_str,
        "action_taken":        action,
        "action_reason":       reason,
        "model_version_before": model_version,
    })

    df = _load()
    df = pd.concat([df, pd.DataFrame([row])], ignore_index=True)
    _save(df)
    logger.info(f"📓 Logbook: drift event recorded for {month_label}")


def log_action_event(
    month_label: str,
    action: str,
    metrics_before: dict,
    metrics_after: dict,
    model_before: str,
    model_after: str,
    rolled_back: bool = False,
    notes: str = "",
):
    """
    Called after fine_tune() / sliding_window_retrain() / rollback.
    action: 'FINE_TUNE' | 'RETRAIN' | 'ROLLBACK' | 'MONITOR'
    """
    row = {c: "" for c in COLUMNS}
    row.update({
        "timestamp":            _now(),
        "month_uploaded":       month_label,
        "event_type":           "MODEL_ACTION",
        "action_taken":         action if not rolled_back else "ROLLBACK",
        "action_reason":        "New model did not improve — rolled back to previous." if rolled_back
                                else _action_note(action),
        "model_version_before": model_before,
        "model_version_after":  model_after,
        "mae_before":           round(metrics_before.get("MAE",  0), 4),
        "rmse_before":          round(metrics_before.get("RMSE", 0), 4),
        "mae_after":            round(metrics_after.get("MAE",   0), 4),
        "rmse_after":           round(metrics_after.get("RMSE",  0), 4),
        "notes":                notes,
    })

    df = _load()
    df = pd.concat([df, pd.DataFrame([row])], ignore_index=True)
    _save(df)
    logger.info(f"📓 Logbook: action event '{action}' recorded for {month_label}")


def log_forecast_event(month_label: str, forecast_month: str, n_rows: int, model_version: str = ""):
    """Called after predict_next_month() completes."""
    row = {c: "" for c in COLUMNS}
    row.update({
        "timestamp":           _now(),
        "month_uploaded":      month_label,
        "event_type":          "FORECAST",
        "action_taken":        "FORECAST",
        "action_reason":       f"Next month forecast generated for {forecast_month} — {n_rows:,} SKU-day rows.",
        "model_version_after": model_version,
        "notes":               f"Forecast covers {forecast_month}",
    })

    df = _load()
    df = pd.concat([df, pd.DataFrame([row])], ignore_index=True)
    _save(df)
    logger.info(f"📓 Logbook: forecast event recorded → {forecast_month}")


def log_shap_event(month_label: str, shap_summary: str):
    """Called after SHAP explanation is computed."""
    row = {c: "" for c in COLUMNS}
    row.update({
        "timestamp":        _now(),
        "month_uploaded":   month_label,
        "event_type":       "SHAP_EXPLANATION",
        "action_taken":     "EXPLAIN",
        "shap_top_features": shap_summary,
        "action_reason":    "SHAP feature importance computed for this month's predictions.",
    })

    df = _load()
    df = pd.concat([df, pd.DataFrame([row])], ignore_index=True)
    _save(df)


def get_logbook() -> pd.DataFrame:
    return _load()


# ── Plain-English builders ────────────────────────────────

def _build_reason(level, psi, ks, mae, score, top_feats) -> str:
    feat_names = [f[0] for f in top_feats] if top_feats else []
    feat_str   = ", ".join(feat_names) if feat_names else "no specific features"

    psi_s  = f"{psi:.3f}"  if psi  is not None else "N/A"
    ks_s   = f"{ks:.3f}"   if ks   is not None else "N/A"
    mae_s  = f"{mae:.3f}"  if mae  is not None else "N/A"
    score_s = f"{score:.3f}" if score is not None else "N/A"

    base = (
        f"Drift Score: {score_s} (PSI={psi_s}, KS={ks_s}, MAE={mae_s}). "
        f"Most changed features: {feat_str}. "
    )

    if level == "low":
        return (
            base +
            "All drift signals are within safe thresholds (Score < 0.10). "
            "The model's understanding of demand patterns has not changed significantly. "
            "No update needed — continue monitoring next month."
        )
    elif level == "medium":
        return (
            base +
            "Drift score is moderate (0.10–0.30). The data distribution has shifted slightly, "
            f"mainly driven by {feat_str}. "
            "Fine-tuning adds new trees on top of the existing model to adapt to recent patterns "
            "without discarding historical knowledge."
        )
    elif level == "high":
        return (
            base +
            "Drift score exceeds 0.30 or PSI > 0.20 — significant distribution shift detected. "
            f"Features most responsible: {feat_str}. "
            "A full sliding window retrain is required using the last 6 months of data "
            "to rebuild the model on the current demand patterns."
        )
    else:
        return base + "Drift level could not be determined — insufficient data or feature mismatch."


def _action_note(action: str) -> str:
    return {
        "FINE_TUNE": "Model fine-tuned: new trees added on top of existing model using last 90 days + new month data.",
        "RETRAIN":   "Model retrained from scratch using sliding window of last 6 months of data.",
        "MONITOR":   "No model update. Drift was low — model performance is stable.",
        "FORECAST":  "Next month forecast generated using recursive day-by-day prediction.",
    }.get(action, "")
