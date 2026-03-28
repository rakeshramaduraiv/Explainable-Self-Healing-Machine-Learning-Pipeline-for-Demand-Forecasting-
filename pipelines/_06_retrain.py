from pipelines.utils import logger, PROCESSED_DIR, MODEL_DIR, mae, rmse, mape
from pipelines._drift import save_feature_schema, validate_feature_schema
import pandas as pd
import numpy as np
import lightgbm as lgb
import joblib
import shutil
import json
import os
from datetime import date

REPORT_DIR   = os.path.join(os.path.dirname(os.path.dirname(__file__)), "reports")
WINDOW_MONTHS = 6


def _get_feature_cols(df):
    drop = ["id","date","sales"] + list(df.select_dtypes(include="object").columns)
    return [c for c in df.columns if c not in drop]


def _eval_metrics(model, X, y):
    yhat = model.predict(X)
    return {"MAE": mae(y, yhat), "RMSE": rmse(y, yhat), "MAPE": mape(y, yhat)}, yhat


def _backup_model():
    for src, dst in [
        (f"{MODEL_DIR}/model.pkl",                    f"{MODEL_DIR}/model_backup.pkl"),
        (f"{PROCESSED_DIR}/predictions.parquet",      f"{PROCESSED_DIR}/predictions_backup.parquet"),
        (f"{PROCESSED_DIR}/features.parquet",         f"{PROCESSED_DIR}/features_backup.parquet"),
    ]:
        if os.path.exists(src):
            shutil.copy(src, dst)
    logger.info("💾 Backup complete (model + predictions + features)")


def _rollback():
    for src, dst in [
        (f"{MODEL_DIR}/model_backup.pkl",                    f"{MODEL_DIR}/model.pkl"),
        (f"{PROCESSED_DIR}/predictions_backup.parquet",      f"{PROCESSED_DIR}/predictions.parquet"),
        (f"{PROCESSED_DIR}/features_backup.parquet",         f"{PROCESSED_DIR}/features.parquet"),
    ]:
        if os.path.exists(src):
            shutil.copy(src, dst)
            logger.info(f"🔄 Rolled back → {dst}")


def _update_predictions(model, df):
    X_cols = _get_feature_cols(df)
    yhat   = model.predict(df[X_cols])
    pd.DataFrame({"id": df["id"], "date": df["date"], "yhat": yhat}).to_parquet(
        f"{PROCESSED_DIR}/predictions.parquet", index=False
    )
    logger.info(f"✅ predictions.parquet updated → {len(df):,} rows")


def _save_version(model, metrics, X_cols, label):
    """Upgrade D: save versioned model + metadata."""
    version    = f"{label}_{date.today()}"
    ver_path   = os.path.join(MODEL_DIR, f"model_{version}.pkl")
    joblib.dump(model, ver_path)
    meta = {
        "version":    version,
        "trained_on": str(date.today()),
        "mae":        round(metrics["MAE"],  4),
        "rmse":       round(metrics["RMSE"], 4),
        "n_features": len(X_cols),
    }
    with open(os.path.join(MODEL_DIR, "metadata.json"), "w") as f:
        json.dump(meta, f, indent=2)
    logger.info(f"✅ Model version saved → {ver_path}")


def fine_tune():
    logger.info("🔧 Fine-tuning model on new month data...")
    df_new  = pd.read_parquet(f"{PROCESSED_DIR}/actual_month_features.parquet")
    df_full = pd.read_parquet(f"{PROCESSED_DIR}/features.parquet")

    X_cols = _get_feature_cols(df_new)

    # Upgrade B: validate feature schema before training
    if not validate_feature_schema(X_cols):
        logger.error("❌ Feature schema mismatch — aborting fine-tune")
        return {}

    X_new, y_new = df_new[X_cols], df_new["sales"]

    _backup_model()
    old_model      = joblib.load(f"{MODEL_DIR}/model.pkl")
    old_metrics, _ = _eval_metrics(old_model, X_new, y_new)

    new_model = lgb.LGBMRegressor(
        objective="regression", metric="rmse",
        learning_rate=0.01, num_leaves=127,
        feature_fraction=0.8, bagging_fraction=0.8,
        bagging_freq=1, min_data_in_leaf=50,
        verbosity=-1, n_estimators=500
    )
    new_model.fit(X_new, y_new, init_model=old_model.booster_)
    new_metrics, _ = _eval_metrics(new_model, X_new, y_new)

    # Upgrade D: retrain safety check — only deploy if improvement > 2%
    if new_metrics["RMSE"] < old_metrics["RMSE"] * 0.98:
        joblib.dump(new_model, f"{MODEL_DIR}/model.pkl")
        _save_version(new_model, new_metrics, X_cols, "finetune")

        df_full["date"] = pd.to_datetime(df_full["date"])
        df_new["date"]  = pd.to_datetime(df_new["date"])
        updated = pd.concat([df_full, df_new], ignore_index=True).drop_duplicates(subset=["id","date"])
        updated.to_parquet(f"{PROCESSED_DIR}/features.parquet", index=False)
        _update_predictions(new_model, updated)

        logger.info(f"✅ Fine-tuned model deployed. RMSE: {old_metrics['RMSE']:.4f} → {new_metrics['RMSE']:.4f}")
        return new_metrics
    else:
        _rollback()
        logger.warning(f"⚠️ Fine-tune not better enough (RMSE {new_metrics['RMSE']:.4f} vs {old_metrics['RMSE']:.4f}) — rolled back")
        return old_metrics


def sliding_window_retrain():
    logger.info("🔁 Sliding window retrain started...")
    df     = pd.read_parquet(f"{PROCESSED_DIR}/features.parquet")
    df_new = pd.read_parquet(f"{PROCESSED_DIR}/actual_month_features.parquet")
    df["date"]     = pd.to_datetime(df["date"])
    df_new["date"] = pd.to_datetime(df_new["date"])

    df = pd.concat([df, df_new], ignore_index=True).drop_duplicates(subset=["id","date"])
    df = df.sort_values(["id","date"])

    max_date  = df["date"].max()
    window_df = df[df["date"] >= max_date - pd.DateOffset(months=WINDOW_MONTHS)]
    cutoff    = max_date - pd.DateOffset(months=1)
    train     = window_df[window_df["date"] <= cutoff]
    valid     = window_df[window_df["date"] >  cutoff]

    X_cols     = _get_feature_cols(window_df)

    # Upgrade B: validate feature schema
    if not validate_feature_schema(X_cols):
        logger.error("❌ Feature schema mismatch — aborting retrain")
        return {}

    X_tr, y_tr = train[X_cols], train["sales"]
    X_va, y_va = valid[X_cols], valid["sales"]

    _backup_model()
    old_model      = joblib.load(f"{MODEL_DIR}/model.pkl")
    old_metrics, _ = _eval_metrics(old_model, X_va, y_va)

    new_model = lgb.LGBMRegressor(
        objective="regression", metric="rmse",
        learning_rate=0.05, num_leaves=127,
        feature_fraction=0.8, bagging_fraction=0.8,
        bagging_freq=1, min_data_in_leaf=100,
        verbosity=-1, n_estimators=2000
    )
    new_model.fit(X_tr, y_tr, eval_set=[(X_va, y_va)],
                  callbacks=[lgb.early_stopping(100), lgb.log_evaluation(200)])
    new_metrics, _ = _eval_metrics(new_model, X_va, y_va)

    # Upgrade D: retrain safety check
    if new_metrics["RMSE"] < old_metrics["RMSE"] * 0.98:
        joblib.dump(new_model, f"{MODEL_DIR}/model.pkl")
        _save_version(new_model, new_metrics, X_cols, "retrain")
        save_feature_schema(X_cols)

        df.to_parquet(f"{PROCESSED_DIR}/features.parquet", index=False)
        _update_predictions(new_model, window_df)

        logger.info(f"✅ Retrain deployed. RMSE: {old_metrics['RMSE']:.4f} → {new_metrics['RMSE']:.4f}")
        return new_metrics
    else:
        _rollback()
        logger.warning(f"⚠️ Retrain not better enough — rolled back")
        return old_metrics


def predict_next_month():
    """Upgrade E: Vectorized recursive forecasting — predict all SKUs per day at once."""
    logger.info("🔮 Predicting next month (vectorized recursive)...")
    df    = pd.read_parquet(f"{PROCESSED_DIR}/features.parquet")
    df["date"] = pd.to_datetime(df["date"])
    model = joblib.load(f"{MODEL_DIR}/model.pkl")

    max_date     = df["date"].max()
    next_start   = (max_date + pd.DateOffset(days=1)).replace(day=1)
    next_end     = (next_start + pd.DateOffset(months=1)) - pd.DateOffset(days=1)
    future_dates = pd.date_range(next_start, next_end, freq="D")

    X_cols     = _get_feature_cols(df)
    results    = []

    # Build last known feature row per SKU (vectorized — no per-SKU scan)
    last_known = df.sort_values("date").groupby("id").last().reset_index()

    # Pre-build lag buffer as numpy arrays per SKU for fast access
    buf = (
        df.sort_values("date")
          .groupby("id")
          .tail(28)[["id","sales"]]
          .groupby("id")["sales"]
          .apply(np.array)
          .to_dict()
    )

    for d in future_dates:
        day_rows = last_known.copy()

        # Upgrade E: update all date features at once (vectorized)
        day_rows["date"]       = d
        day_rows["month"]      = d.month
        day_rows["year"]       = d.year
        day_rows["dayofweek"]  = d.dayofweek
        day_rows["is_weekend"] = int(d.dayofweek >= 5)
        day_rows["dow_sin"]    = np.sin(2 * np.pi * d.dayofweek / 7)
        day_rows["dow_cos"]    = np.cos(2 * np.pi * d.dayofweek / 7)

        # Upgrade E: build lag arrays vectorized using numpy indexing
        ids = day_rows["id"].values
        for lag_name, lag_n in [("lag_1",1),("lag_7",7),("lag_14",14),("lag_28",28)]:
            day_rows[lag_name] = [buf[i][-lag_n] if len(buf[i]) >= lag_n else 0 for i in ids]
        for w, wname in [(7,"rmean_7"),(14,"rmean_14"),(28,"rmean_28")]:
            day_rows[wname] = [buf[i][-w:].mean() if len(buf[i]) >= w else buf[i].mean() for i in ids]
        for w, wname in [(7,"rstd_7"),(14,"rstd_14"),(28,"rstd_28")]:
            day_rows[wname] = [buf[i][-w:].std() if len(buf[i]) >= w else 0.0 for i in ids]

        # Predict all SKUs at once
        X_day  = day_rows[[c for c in X_cols if c in day_rows.columns]]
        preds  = model.predict(X_day).clip(0)
        day_rows["predicted_sales"] = preds

        # Upgrade E: update buffer for all SKUs at once
        for i, id_ in enumerate(ids):
            buf[id_] = np.append(buf[id_], preds[i])[-28:]

        results.append(day_rows[["id","date","predicted_sales"]])
        logger.info(f"  📅 {d.date()} — {len(ids):,} SKUs")

    out = pd.concat(results, ignore_index=True)
    out.to_parquet(f"{PROCESSED_DIR}/next_month_predictions.parquet", index=False)
    logger.info(f"✅ Forecast complete → {len(out):,} rows | {next_start.date()} → {next_end.date()}")
    return out
