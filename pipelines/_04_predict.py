from pipelines.utils import logger, PROCESSED_DIR, MODEL_DIR, mae, rmse, mape
from pipelines._drift import save_feature_schema
import pandas as pd
import numpy as np
import lightgbm as lgb
import matplotlib.pyplot as plt
import joblib
import json
import os

REPORT_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "reports")

# Fix 1: explicit feature exclusions — never rely on dtype to drop columns
_DROP_COLS = {"id", "date", "sales", "item_id", "dept_id", "cat_id", "store_id", "state_id"}


def _get_feature_cols(df):
    return [c for c in df.columns if c not in _DROP_COLS and df[c].dtype != object]


def _save_model_metadata(version, metrics, feature_cols, trained_on):
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
    logger.info(f"✅ Metadata saved → {path}")


def train_and_predict():
    df = pd.read_parquet(f"{PROCESSED_DIR}/features.parquet")
    df["date"] = pd.to_datetime(df["date"])

    # Fix 3: dynamic cutoff — last 28 days as validation
    max_date = df["date"].max()
    cutoff   = max_date - pd.Timedelta(days=28)

    train = df[df["date"] <= cutoff]
    valid = df[df["date"] >  cutoff]

    # Fix 4: empty split guard
    if len(train) == 0 or len(valid) == 0:
        raise ValueError(f"Train/valid split is empty — cutoff={cutoff.date()}, max={max_date.date()}")

    X_cols     = _get_feature_cols(df)
    X_tr, y_tr = train[X_cols], train["sales"]
    X_va, y_va = valid[X_cols], valid["sales"]

    # Fix 8: log split details
    logger.info(f"Train: {len(train):,} rows | {train['date'].min().date()} → {train['date'].max().date()}")
    logger.info(f"Valid: {len(valid):,} rows | {valid['date'].min().date()} → {valid['date'].max().date()}")
    logger.info(f"Features: {len(X_cols)}")

    # Fix 9: NaN check before training
    nan_count = X_tr.isnull().sum().sum()
    if nan_count > 0:
        bad_cols = X_tr.columns[X_tr.isnull().any()].tolist()
        raise ValueError(f"NaNs in training features: {bad_cols}")

    # Fix 5: random_state for reproducibility
    params = {
        "objective": "regression", "metric": "rmse",
        "learning_rate": 0.05, "num_leaves": 127,
        "feature_fraction": 0.8, "bagging_fraction": 0.8,
        "bagging_freq": 1, "min_data_in_leaf": 100,
        "verbosity": -1, "random_state": 42,
    }
    model = lgb.LGBMRegressor(**params, n_estimators=2000)
    model.fit(X_tr, y_tr, eval_set=[(X_va, y_va)], eval_metric="rmse",
              callbacks=[lgb.early_stopping(100), lgb.log_evaluation(200)])

    # save model
    os.makedirs(MODEL_DIR, exist_ok=True)
    joblib.dump(model, os.path.join(MODEL_DIR, "model.pkl"))
    joblib.dump(model, os.path.join(MODEL_DIR, "model_v1.pkl"))
    logger.info(f"✅ Model saved → {MODEL_DIR}/model.pkl")

    # validation metrics
    yhat_va  = model.predict(X_va)
    metrics  = {"MAE": mae(y_va, yhat_va), "RMSE": rmse(y_va, yhat_va), "MAPE": mape(y_va, yhat_va)}
    logger.info(f"📊 Validation → MAE={metrics['MAE']:.4f} | RMSE={metrics['RMSE']:.4f} | MAPE={metrics['MAPE']:.2f}%")

    os.makedirs(REPORT_DIR, exist_ok=True)
    pd.DataFrame([metrics]).to_csv(f"{REPORT_DIR}/metrics_summary.csv", index=False)

    # Fix 2: save feature schema + Fix 2 order check on reload
    save_feature_schema(X_cols)

    trained_on = str(max_date.date())
    _save_model_metadata("v1", metrics, X_cols, trained_on)

    # Fix 10: save feature stats for drift baseline
    feature_stats = {
        col: {"mean": float(X_tr[col].mean()), "std": float(X_tr[col].std())}
        for col in X_cols
    }
    with open(os.path.join(MODEL_DIR, "feature_stats.json"), "w") as f:
        json.dump(feature_stats, f, indent=2)
    logger.info(f"✅ Feature stats saved → {MODEL_DIR}/feature_stats.json")

    # Fix 6: save feature importance chart
    fig, ax = plt.subplots(figsize=(8, 6))
    lgb.plot_importance(model, ax=ax, max_num_features=20, importance_type="gain")
    ax.set_title("Feature Importance (Gain)")
    fig.tight_layout()
    fig.savefig(f"{REPORT_DIR}/feature_importance.png")
    plt.close(fig)
    logger.info(f"✅ Feature importance saved → {REPORT_DIR}/feature_importance.png")

    # Fix 7: merge new predictions with existing instead of overwriting
    new_preds = pd.DataFrame({"id": df["id"], "date": df["date"], "yhat": model.predict(df[X_cols])})
    pred_path = f"{PROCESSED_DIR}/predictions.parquet"
    if os.path.exists(pred_path):
        old_preds = pd.read_parquet(pred_path)
        new_preds = pd.concat([old_preds, new_preds]).drop_duplicates(["id", "date"], keep="last")
    new_preds.to_parquet(pred_path, index=False)
    logger.info(f"✅ predictions.parquet → {len(new_preds):,} rows")

    return metrics


if __name__ == "__main__":
    train_and_predict()
