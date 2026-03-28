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

REPORT_DIR     = os.path.join(os.path.dirname(os.path.dirname(__file__)), "reports")
WINDOW_MONTHS  = 6
MAX_TREES      = 1500   # Fix 1: tree explosion cap
MAX_FINE_TUNE_ROUNDS = 3  # Fix 1 + 9: force retrain after 3 fine-tunes
META_PATH      = os.path.join(MODEL_DIR, "meta.json")


# ── Fix 1: Model meta (fine_tune_count tracker) ──────────
def _load_meta():
    try:
        with open(META_PATH, "r") as f:
            return json.load(f)
    except Exception:
        return {"fine_tune_count": 0}


def _save_meta(meta):
    os.makedirs(MODEL_DIR, exist_ok=True)
    with open(META_PATH, "w") as f:
        json.dump(meta, f, indent=2)


# ── Helpers ───────────────────────────────────────────────
def _get_feature_cols(df):
    drop = ["id", "date", "sales"] + list(df.select_dtypes(include="object").columns)
    return [c for c in df.columns if c not in drop]


def _eval_metrics(model, X, y):
    yhat = model.predict(X)
    return {"MAE": mae(y, yhat), "RMSE": rmse(y, yhat), "MAPE": mape(y, yhat)}, yhat


def _backup_model():
    for src, dst in [
        (f"{MODEL_DIR}/model.pkl",               f"{MODEL_DIR}/model_backup.pkl"),
        (f"{PROCESSED_DIR}/predictions.parquet", f"{PROCESSED_DIR}/predictions_backup.parquet"),
        (f"{PROCESSED_DIR}/features.parquet",    f"{PROCESSED_DIR}/features_backup.parquet"),
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
    version  = f"{label}_{date.today()}"
    ver_path = os.path.join(MODEL_DIR, f"model_{version}.pkl")
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


# ── Fix 4: Dual evaluation (new data + old validation slice) ──
def _dual_eval(old_model, new_model, X_new, y_new, df_full, X_cols):
    val_df   = df_full.sort_values("date").tail(30)
    X_val    = val_df[[c for c in X_cols if c in val_df.columns]]
    y_val    = val_df["sales"]

    old_rmse_new, _ = _eval_metrics(old_model, X_new, y_new)
    new_rmse_new, _ = _eval_metrics(new_model, X_new, y_new)
    old_rmse_old, _ = _eval_metrics(old_model, X_val, y_val)
    new_rmse_old, _ = _eval_metrics(new_model, X_val, y_val)

    improved_on_new = new_rmse_new["RMSE"] < old_rmse_new["RMSE"] * 0.98
    no_regression   = new_rmse_old["RMSE"] <= old_rmse_old["RMSE"] * 1.05

    logger.info(
        f"📊 New data RMSE: {old_rmse_new['RMSE']:.4f} → {new_rmse_new['RMSE']:.4f} | "
        f"Old val RMSE: {old_rmse_old['RMSE']:.4f} → {new_rmse_old['RMSE']:.4f}"
    )
    return improved_on_new and no_regression, new_rmse_new


# ── Fine-Tune ─────────────────────────────────────────────
def fine_tune():
    meta = _load_meta()

    # Fix 1 + 9: too many fine-tunes → force retrain
    if meta["fine_tune_count"] >= MAX_FINE_TUNE_ROUNDS:
        logger.warning(f"⚠️ fine_tune_count={meta['fine_tune_count']} ≥ {MAX_FINE_TUNE_ROUNDS} → forcing retrain")
        return sliding_window_retrain()

    _backup_model()
    old_model = joblib.load(f"{MODEL_DIR}/model.pkl")

    # Fix 1: tree explosion guard
    if old_model.n_estimators > MAX_TREES:
        logger.warning(f"⚠️ Tree count {old_model.n_estimators} > {MAX_TREES} → forcing retrain")
        return sliding_window_retrain()

    df_new  = pd.read_parquet(f"{PROCESSED_DIR}/actual_month_features.parquet")
    df_full = pd.read_parquet(f"{PROCESSED_DIR}/features.parquet")
    df_full["date"] = pd.to_datetime(df_full["date"])
    df_new["date"]  = pd.to_datetime(df_new["date"])

    X_cols = _get_feature_cols(df_new)

    if not validate_feature_schema(X_cols):
        logger.error("❌ Feature schema mismatch — aborting fine-tune")
        return {}

    # Fix 2: use last 3 months + new month for stability
    recent = df_full.sort_values("date").tail(
        int(len(df_full) / df_full["date"].nunique() * 90)  # ~90 days worth of rows
    )
    train_df = pd.concat([recent, df_new], ignore_index=True).drop_duplicates(["id", "date"])

    X_train, y_train = train_df[X_cols], train_df["sales"]
    X_new_only       = df_new[X_cols]
    y_new_only       = df_new["sales"]

    # Fix 3: dynamic learning rate
    lr = 0.02 if len(train_df) < 10_000 else 0.01

    new_model = lgb.LGBMRegressor(
        objective="regression", metric="rmse",
        learning_rate=lr, num_leaves=127,
        feature_fraction=0.8, bagging_fraction=0.8,
        bagging_freq=1, min_data_in_leaf=50,
        verbosity=-1, n_estimators=500
    )
    new_model.fit(X_train, y_train, init_model=old_model.booster_)

    # Fix 4: dual evaluation before deploy
    should_deploy, new_metrics = _dual_eval(old_model, new_model, X_new_only, y_new_only, df_full, X_cols)

    if should_deploy:
        joblib.dump(new_model, f"{MODEL_DIR}/model.pkl")
        _save_version(new_model, new_metrics, X_cols, "finetune")

        updated = pd.concat([df_full, df_new], ignore_index=True).drop_duplicates(subset=["id", "date"])
        updated.to_parquet(f"{PROCESSED_DIR}/features.parquet", index=False)
        _update_predictions(new_model, updated)

        meta["fine_tune_count"] += 1
        _save_meta(meta)

        logger.info(f"✅ Fine-tuned model deployed (fine_tune_count={meta['fine_tune_count']})")
        return new_metrics
    else:
        _rollback()
        logger.warning("⚠️ Fine-tune did not pass dual eval — rolled back")
        return _eval_metrics(old_model, X_new_only, y_new_only)[0]


# ── Sliding Window Retrain ────────────────────────────────
def sliding_window_retrain():
    logger.info("🔁 Sliding window retrain started...")
    df     = pd.read_parquet(f"{PROCESSED_DIR}/features.parquet")
    df_new = pd.read_parquet(f"{PROCESSED_DIR}/actual_month_features.parquet")
    df["date"]     = pd.to_datetime(df["date"])
    df_new["date"] = pd.to_datetime(df_new["date"])

    df = pd.concat([df, df_new], ignore_index=True).drop_duplicates(subset=["id", "date"])
    df = df.sort_values(["id", "date"])

    max_date  = df["date"].max()
    window_df = df[df["date"] >= max_date - pd.DateOffset(months=WINDOW_MONTHS)]
    cutoff    = max_date - pd.DateOffset(months=1)
    train     = window_df[window_df["date"] <= cutoff]
    valid     = window_df[window_df["date"] >  cutoff]

    X_cols = _get_feature_cols(window_df)

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

    # Fix 4: also check no regression on old val slice
    old_val_df = df.sort_values("date").tail(30)
    X_ov = old_val_df[[c for c in X_cols if c in old_val_df.columns]]
    y_ov = old_val_df["sales"]
    new_rmse_old, _ = _eval_metrics(new_model, X_ov, y_ov)
    old_rmse_old, _ = _eval_metrics(old_model, X_ov, y_ov)
    no_regression   = new_rmse_old["RMSE"] <= old_rmse_old["RMSE"] * 1.05

    if new_metrics["RMSE"] < old_metrics["RMSE"] * 0.98 and no_regression:
        joblib.dump(new_model, f"{MODEL_DIR}/model.pkl")
        _save_version(new_model, new_metrics, X_cols, "retrain")
        save_feature_schema(X_cols)

        df.to_parquet(f"{PROCESSED_DIR}/features.parquet", index=False)
        _update_predictions(new_model, window_df)

        # Fix 1 + 9: reset fine_tune_count after full retrain
        meta = _load_meta()
        meta["fine_tune_count"] = 0
        _save_meta(meta)

        logger.info(f"✅ Retrain deployed. RMSE: {old_metrics['RMSE']:.4f} → {new_metrics['RMSE']:.4f}")
        return new_metrics
    else:
        _rollback()
        logger.warning("⚠️ Retrain not better enough — rolled back")
        return old_metrics


# ── Predict Next Month (vectorized) ──────────────────────
def predict_next_month():
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

    last_known = df.sort_values("date").groupby("id").last().reset_index()

    buf = (
        df.sort_values("date")
          .groupby("id")
          .tail(28)[["id", "sales"]]
          .groupby("id")["sales"]
          .apply(np.array)
          .to_dict()
    )

    for d in future_dates:
        day_rows = last_known.copy()
        day_rows["date"]       = d
        day_rows["month"]      = d.month
        day_rows["year"]       = d.year
        day_rows["dayofweek"]  = d.dayofweek
        day_rows["is_weekend"] = int(d.dayofweek >= 5)
        day_rows["dow_sin"]    = np.sin(2 * np.pi * d.dayofweek / 7)
        day_rows["dow_cos"]    = np.cos(2 * np.pi * d.dayofweek / 7)

        ids = day_rows["id"].values
        for lag_name, lag_n in [("lag_1", 1), ("lag_7", 7), ("lag_14", 14), ("lag_28", 28)]:
            day_rows[lag_name] = [buf[i][-lag_n] if len(buf[i]) >= lag_n else 0 for i in ids]
        for w, wname in [(7, "rmean_7"), (14, "rmean_14"), (28, "rmean_28")]:
            day_rows[wname] = [buf[i][-w:].mean() if len(buf[i]) >= w else buf[i].mean() for i in ids]
        for w, wname in [(7, "rstd_7"), (14, "rstd_14"), (28, "rstd_28")]:
            day_rows[wname] = [buf[i][-w:].std() if len(buf[i]) >= w else 0.0 for i in ids]

        X_day  = day_rows[[c for c in X_cols if c in day_rows.columns]]
        preds  = model.predict(X_day).clip(0)
        day_rows["predicted_sales"] = preds

        for i, id_ in enumerate(ids):
            buf[id_] = np.append(buf[id_], preds[i])[-28:]

        results.append(day_rows[["id", "date", "predicted_sales"]])
        logger.info(f"  📅 {d.date()} — {len(ids):,} SKUs")

    out = pd.concat(results, ignore_index=True)
    out.to_parquet(f"{PROCESSED_DIR}/next_month_predictions.parquet", index=False)
    logger.info(f"✅ Forecast complete → {len(out):,} rows | {next_start.date()} → {next_end.date()}")
    return out
