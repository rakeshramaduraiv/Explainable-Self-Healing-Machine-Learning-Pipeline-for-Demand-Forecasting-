from pipelines.utils import logger, PROCESSED_DIR, MODEL_DIR, mae, rmse, mape
from pipelines._drift import save_feature_schema
import pandas as pd
import lightgbm as lgb
import joblib
import json
import os

REPORT_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "reports")


def _save_model_metadata(version, metrics, feature_cols, trained_on):
    """Upgrade D: Save model metadata for versioning and debugging."""
    meta = {
        "version":    version,
        "trained_on": trained_on,
        "mae":        round(metrics["MAE"],  4),
        "rmse":       round(metrics["RMSE"], 4),
        "mape":       round(metrics["MAPE"], 4),
        "n_features": len(feature_cols),
        "features":   feature_cols,
    }
    path = os.path.join(MODEL_DIR, "metadata.json")
    with open(path, "w") as f:
        json.dump(meta, f, indent=2)
    logger.info(f"✅ Model metadata saved → {path}")


def train_and_predict():
    df     = pd.read_parquet(f"{PROCESSED_DIR}/features.parquet")
    cutoff = pd.Timestamp("2016-03-27")

    train = df[df.date <= cutoff]
    valid = df[df.date >  cutoff]

    drop_cols  = ["id","date","sales"] + list(df.select_dtypes(include="object").columns)
    X_cols     = [c for c in df.columns if c not in drop_cols]
    X_tr, y_tr = train[X_cols], train["sales"]
    X_va, y_va = valid[X_cols], valid["sales"]

    logger.info(f"🧩 Training LightGBM — {len(X_tr):,} rows | {len(X_cols)} features")
    params = {
        "objective": "regression", "metric": "rmse",
        "learning_rate": 0.05, "num_leaves": 127,
        "feature_fraction": 0.8, "bagging_fraction": 0.8,
        "bagging_freq": 1, "min_data_in_leaf": 100, "verbosity": -1
    }
    model = lgb.LGBMRegressor(**params, n_estimators=2000)
    model.fit(X_tr, y_tr, eval_set=[(X_va, y_va)], eval_metric="rmse",
              callbacks=[lgb.early_stopping(100), lgb.log_evaluation(200)])

    # Upgrade D: versioned model save
    version   = "v1"
    model_path = os.path.join(MODEL_DIR, "model.pkl")
    joblib.dump(model, model_path)
    joblib.dump(model, os.path.join(MODEL_DIR, f"model_{version}.pkl"))
    logger.info(f"✅ Model saved → {model_path}")

    # Validation metrics
    yhat_va  = model.predict(X_va)
    val_mae  = mae(y_va, yhat_va)
    val_rmse = rmse(y_va, yhat_va)
    val_mape = mape(y_va, yhat_va)
    metrics  = {"MAE": val_mae, "RMSE": val_rmse, "MAPE": val_mape}
    logger.info(f"📊 Validation → {metrics}")

    # Save baseline metrics
    os.makedirs(REPORT_DIR, exist_ok=True)
    pd.DataFrame({"MAE": [val_mae], "RMSE": [val_rmse], "MAPE": [val_mape]}).to_csv(
        f"{REPORT_DIR}/metrics_summary.csv", index=False
    )

    # Upgrade B: save feature schema
    save_feature_schema(X_cols)

    # Upgrade D: save model metadata
    trained_on = str(df["date"].max().date())
    _save_model_metadata(version, metrics, X_cols, trained_on)

    # Full predictions for drift detection
    yhat_full = model.predict(df[X_cols])
    pd.DataFrame({"id": df["id"], "date": df["date"], "yhat": yhat_full}).to_parquet(
        f"{PROCESSED_DIR}/predictions.parquet", index=False
    )
    logger.info(f"✅ predictions.parquet → {len(df):,} rows")

    return metrics


if __name__ == "__main__":
    train_and_predict()
