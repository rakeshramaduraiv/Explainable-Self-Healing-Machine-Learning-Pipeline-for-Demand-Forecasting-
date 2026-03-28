from prefect import flow, task
import sys, os
sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from pipelines import _01_ingest, _02_validate, _03_features, _04_predict, _05_evaluate
from pipelines._drift import run_drift_check
from pipelines._06_retrain import fine_tune, sliding_window_retrain, predict_next_month

@flow(name="m5_forecasting_pipeline")
def full_pipeline():
    _01_ingest.ingest_data()
    _02_validate.validate_data()
    _03_features.create_features()
    _04_predict.train_and_predict()
    _05_evaluate.evaluate()

@flow(name="monthly_update_pipeline")
def monthly_update_pipeline():
    """Run after uploading actual month data via dashboard."""
    result = run_drift_check()
    level  = result["level"]

    if level == "medium":
        fine_tune()
    elif level == "high":
        sliding_window_retrain()

    predict_next_month()

if __name__ == "__main__":
    full_pipeline()
