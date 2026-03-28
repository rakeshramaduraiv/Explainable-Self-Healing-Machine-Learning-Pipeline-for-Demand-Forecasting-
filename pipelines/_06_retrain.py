from pipelines.utils import logger, PROCESSED_DIR, MODEL_DIR, mae, rmse, mape
import pandas as pd
import numpy as np
import lightgbm as lgb
import joblib
import shutil
import os

WINDOW_MONTHS = 6  # sliding window size in months

def _get_feature_cols(df):
    drop = ['id', 'date', 'sales'] + list(df.select_dtypes(include='object').columns)
    return [c for c in df.columns if c not in drop]

def _eval_metrics(model, X, y):
    yhat = model.predict(X)
    return {"MAE": mae(y, yhat), "RMSE": rmse(y, yhat), "MAPE": mape(y, yhat)}, yhat

def _backup_model():
    src = f"{MODEL_DIR}/model.pkl"
    dst = f"{MODEL_DIR}/model_backup.pkl"
    if os.path.exists(src):
        shutil.copy(src, dst)
        logger.info(f"💾 Model backed up → {dst}")

def _rollback():
    backup = f"{MODEL_DIR}/model_backup.pkl"
    current = f"{MODEL_DIR}/model.pkl"
    if os.path.exists(backup):
        shutil.copy(backup, current)
        logger.info("🔄 Rollback successful — restored backup model.")
    else:
        logger.error("❌ No backup model found for rollback.")

def fine_tune():
    logger.info("🔧 Fine-tuning existing model on new month data...")
    df_new   = pd.read_parquet(f"{PROCESSED_DIR}/actual_month_features.parquet")
    df_full  = pd.read_parquet(f"{PROCESSED_DIR}/features.parquet")
    cutoff   = df_full["date"].max()

    X_cols   = _get_feature_cols(df_new)
    X_new    = df_new[X_cols]
    y_new    = df_new["sales"]

    _backup_model()
    old_model = joblib.load(f"{MODEL_DIR}/model.pkl")
    old_metrics, _ = _eval_metrics(old_model, X_new, y_new)
    logger.info(f"📊 Old model metrics: {old_metrics}")

    new_model = lgb.LGBMRegressor(
        objective="regression", metric="rmse",
        learning_rate=0.01, num_leaves=127,
        feature_fraction=0.8, bagging_fraction=0.8,
        bagging_freq=1, min_data_in_leaf=50,
        verbosity=-1, n_estimators=500
    )
    new_model.fit(X_new, y_new, init_model=old_model.booster_)
    new_metrics, _ = _eval_metrics(new_model, X_new, y_new)
    logger.info(f"📊 Fine-tuned model metrics: {new_metrics}")

    if new_metrics["RMSE"] < old_metrics["RMSE"]:
        joblib.dump(new_model, f"{MODEL_DIR}/model.pkl")
        logger.info("✅ Fine-tuned model saved.")
        return new_metrics
    else:
        _rollback()
        logger.warning("⚠️ Fine-tuned model worse — rolled back.")
        return old_metrics

def sliding_window_retrain():
    logger.info("🔁 Sliding window retrain started...")
    df = pd.read_parquet(f"{PROCESSED_DIR}/features.parquet")
    df["date"] = pd.to_datetime(df["date"])

    # Append new actual month
    df_new = pd.read_parquet(f"{PROCESSED_DIR}/actual_month_features.parquet")
    df_new["date"] = pd.to_datetime(df_new["date"])
    df = pd.concat([df, df_new], ignore_index=True).drop_duplicates(subset=["id", "date"])
    df = df.sort_values(["id", "date"])

    # Slide window: last WINDOW_MONTHS months
    max_date   = df["date"].max()
    min_date   = max_date - pd.DateOffset(months=WINDOW_MONTHS)
    window_df  = df[df["date"] >= min_date]

    cutoff     = max_date - pd.DateOffset(months=1)
    train      = window_df[window_df["date"] <= cutoff]
    valid      = window_df[window_df["date"] > cutoff]

    X_cols     = _get_feature_cols(window_df)
    X_tr, y_tr = train[X_cols], train["sales"]
    X_va, y_va = valid[X_cols], valid["sales"]

    _backup_model()
    old_model = joblib.load(f"{MODEL_DIR}/model.pkl")
    old_metrics, _ = _eval_metrics(old_model, X_va, y_va)
    logger.info(f"📊 Old model metrics on validation: {old_metrics}")

    params = {
        "objective": "regression", "metric": "rmse",
        "learning_rate": 0.05, "num_leaves": 127,
        "feature_fraction": 0.8, "bagging_fraction": 0.8,
        "bagging_freq": 1, "min_data_in_leaf": 100, "verbosity": -1
    }
    new_model = lgb.LGBMRegressor(**params, n_estimators=2000)
    new_model.fit(X_tr, y_tr, eval_set=[(X_va, y_va)],
                  callbacks=[lgb.early_stopping(100), lgb.log_evaluation(200)])

    new_metrics, _ = _eval_metrics(new_model, X_va, y_va)
    logger.info(f"📊 New model metrics: {new_metrics}")

    if new_metrics["RMSE"] < old_metrics["RMSE"]:
        joblib.dump(new_model, f"{MODEL_DIR}/model.pkl")
        # Save updated full dataset
        df.to_parquet(f"{PROCESSED_DIR}/features.parquet", index=False)
        logger.info("✅ New model saved after sliding window retrain.")
        return new_metrics
    else:
        _rollback()
        logger.warning("⚠️ New model worse — rolled back to previous model.")
        return old_metrics

def predict_next_month():
    logger.info("🔮 Predicting next month...")
    df = pd.read_parquet(f"{PROCESSED_DIR}/features.parquet")
    df["date"] = pd.to_datetime(df["date"])

    max_date   = df["date"].max()
    next_start = (max_date + pd.DateOffset(days=1)).replace(day=1)
    next_end   = (next_start + pd.DateOffset(months=1)) - pd.DateOffset(days=1)
    future_dates = pd.date_range(next_start, next_end, freq="D")

    # Build future rows using last known features per id
    last_known = df.sort_values("date").groupby("id").last().reset_index()
    rows = []
    for d in future_dates:
        tmp = last_known.copy()
        tmp["date"]      = d
        tmp["month"]     = d.month
        tmp["year"]      = d.year
        tmp["dayofweek"] = d.dayofweek
        tmp["is_weekend"]= int(d.dayofweek >= 5)
        tmp["dow_sin"]   = np.sin(2 * np.pi * d.dayofweek / 7)
        tmp["dow_cos"]   = np.cos(2 * np.pi * d.dayofweek / 7)
        rows.append(tmp)

    future_df = pd.concat(rows, ignore_index=True)
    X_cols    = _get_feature_cols(future_df)
    model     = joblib.load(f"{MODEL_DIR}/model.pkl")
    future_df["predicted_sales"] = model.predict(future_df[X_cols]).clip(0)

    out = future_df[["id", "date", "predicted_sales"]]
    out.to_parquet(f"{PROCESSED_DIR}/next_month_predictions.parquet", index=False)
    logger.info(f"✅ Next month predictions saved. Rows: {len(out):,}")
    return out
