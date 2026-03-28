from scipy.stats import ks_2samp
from pipelines.utils import logger, PROCESSED_DIR, MODEL_DIR
import pandas as pd
import numpy as np
import joblib
import os

# KS thresholds
LOW    = 0.1
HIGH   = 0.3

def run_drift_check():
    actual = pd.read_parquet(f"{PROCESSED_DIR}/actual_month.parquet")
    preds  = pd.read_parquet(f"{PROCESSED_DIR}/predictions.parquet")

    merged = actual.merge(preds, on=["id", "date"], how="inner")
    if merged.empty:
        logger.warning("⚠️ No overlapping rows between actual and predictions.")
        return {"ks_stat": None, "level": "unknown"}

    ks_stat, _ = ks_2samp(merged["sales"].values, merged["yhat"].values)
    logger.info(f"📊 KS Statistic: {ks_stat:.4f}")

    if ks_stat < LOW:
        level = "low"
        logger.info("✅ Drift LOW — monitoring only.")
    elif ks_stat < HIGH:
        level = "medium"
        logger.info("⚠️ Drift MEDIUM — fine-tuning required.")
    else:
        level = "high"
        logger.info("🚨 Drift HIGH — sliding window retrain required.")

    return {"ks_stat": round(ks_stat, 4), "level": level}
