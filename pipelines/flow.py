from prefect import flow, task
from pipelines.utils import logger, REPORT_DIR, save_json
from pipelines import _01_ingest, _02_validate, _03_features, _04_predict, _05_evaluate
from pipelines._drift import run_drift_check
from pipelines._06_retrain import fine_tune, sliding_window_retrain, predict_next_month
import sys, os
sys.path.append(os.path.dirname(os.path.dirname(__file__)))


# ── Fix 1+2: @task with retries ───────────────────────────
@task(retries=2, retry_delay_seconds=10)
def ingest_task():
    return _01_ingest.ingest_data()

@task(retries=1, retry_delay_seconds=5)
def validate_task():
    return _02_validate.validate_data()

@task(retries=1, retry_delay_seconds=5)
def feature_task():
    return _03_features.create_features()

@task(retries=1, retry_delay_seconds=5)
def train_task():
    return _04_predict.train_and_predict()

@task(retries=1, retry_delay_seconds=5)
def eval_task():
    return _05_evaluate.evaluate()

@task(retries=1, retry_delay_seconds=10)
def drift_task():
    return run_drift_check()

@task(retries=1, retry_delay_seconds=10)
def feature_new_data_task(actual_df=None):
    # Fix 6: generate engineered features before drift check
    if actual_df is not None:
        return _03_features.create_features_for_new_data(actual_df)
    import pandas as pd
    actual_df = pd.read_parquet(f"{os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data', 'processed', 'actual_month.parquet')}")
    return _03_features.create_features_for_new_data(actual_df)

@task(retries=1, retry_delay_seconds=10)
def fine_tune_task():
    return fine_tune()

@task(retries=1, retry_delay_seconds=10)
def retrain_task():
    return sliding_window_retrain()

@task
def forecast_task():
    return predict_next_month()


# ── Full pipeline (initial training) ─────────────────────
@flow(name="m5_full_pipeline")
def full_pipeline():
    logger.info("🚀 Full pipeline started")
    ingest_task()
    validate_task()
    feature_task()
    train_task()
    eval_task()
    logger.info("✅ Full pipeline completed")


# ── Monthly update pipeline ───────────────────────────────
@flow(name="m5_monthly_update")
def monthly_update_pipeline(actual_df=None):
    logger.info("🚀 Monthly update pipeline started")

    # Fix 6: features must exist before drift check
    feature_new_data_task(actual_df)

    result = drift_task()

    # Fix 4: persist drift result for dashboard + audit
    save_json(result, os.path.join(REPORT_DIR, "latest_drift.json"))

    level = result.get("level", "unknown")

    # Fix 5: guard against unknown drift — don't retrain on bad data
    if level == "unknown":
        logger.warning("⚠️ Drift level unknown — skipping retrain (insufficient data)")
        return

    # Fix 3: logged decision
    logger.info(f"📊 Drift level: {level.upper()}")

    if level == "medium":
        fine_tune_task()
    elif level == "high":
        retrain_task()
    else:
        logger.info("✅ LOW drift — model is stable, no update needed")

    forecast_task()
    logger.info("✅ Monthly update pipeline completed")


if __name__ == "__main__":
    full_pipeline()
