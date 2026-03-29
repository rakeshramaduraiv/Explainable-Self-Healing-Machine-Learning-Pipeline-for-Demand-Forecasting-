from pipelines.utils import logger, PROCESSED_DIR, MODEL_DIR, RAW_DIR, mae, rmse, mape
from pipelines._drift import save_feature_schema, validate_feature_schema, get_schema_feature_cols
import pandas as pd
import numpy as np
import lightgbm as lgb
import joblib
import shutil
import json
import os
from datetime import date, datetime

REPORT_DIR          = os.path.join(os.path.dirname(os.path.dirname(__file__)), "reports")
WINDOW_MONTHS       = 6
MAX_TREES           = 1500
MAX_FINE_TUNE_ROUNDS = 3
META_PATH           = os.path.join(MODEL_DIR, "meta.json")


# ── Meta tracker ─────────────────────────────────────────
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


# Must match _03_features._DROP exactly
_DROP = {"id", "date", "sales"}


# ── Fix 1: schema-based feature cols — never recompute from dtype ──
def _get_feature_cols(df=None):
    """Load from saved schema. Falls back to deriving from df if schema missing."""
    try:
        return get_schema_feature_cols()
    except FileNotFoundError:
        if df is None:
            raise
        cols = [c for c in df.columns if c not in _DROP and df[c].dtype != object]
        save_feature_schema(cols)
        return cols


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
        (f"{MODEL_DIR}/model_backup.pkl",                f"{MODEL_DIR}/model.pkl"),
        (f"{PROCESSED_DIR}/predictions_backup.parquet",  f"{PROCESSED_DIR}/predictions.parquet"),
        (f"{PROCESSED_DIR}/features_backup.parquet",     f"{PROCESSED_DIR}/features.parquet"),
    ]:
        if os.path.exists(src):
            shutil.copy(src, dst)
            logger.info(f"🔄 Rolled back → {dst}")


def _update_predictions(model, df):
    X_cols = _get_feature_cols()
    # Fix 5: always predict on full df, not just window
    available = [c for c in X_cols if c in df.columns]
    if set(available) != set(X_cols):
        logger.warning(f"⚠️ Missing cols in prediction df: {set(X_cols) - set(available)}")
    yhat = model.predict(df[available])
    pd.DataFrame({"id": df["id"], "date": df["date"], "yhat": yhat}).to_parquet(
        f"{PROCESSED_DIR}/predictions.parquet", index=False
    )
    logger.info(f"✅ predictions.parquet updated → {len(df):,} rows")


def _save_version(model, metrics, X_cols, label):
    version  = f"{label}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
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


def _dual_eval(old_model, new_model, X_new, y_new, df_full, X_cols):
    # Use last full month as validation — tail(30) was only 30 rows across 30K SKUs
    max_date = df_full["date"].max()
    val_df   = df_full[df_full["date"] >= max_date - pd.DateOffset(months=1)]
    X_val    = val_df[X_cols]
    y_val    = val_df["sales"]

    old_new, _ = _eval_metrics(old_model, X_new, y_new)
    new_new, _ = _eval_metrics(new_model, X_new, y_new)
    old_old, _ = _eval_metrics(old_model, X_val, y_val)
    new_old, _ = _eval_metrics(new_model, X_val, y_val)

    improved    = new_new["RMSE"] < old_new["RMSE"] * 0.98
    no_regress  = new_old["RMSE"] <= old_old["RMSE"] * 1.05

    logger.info(
        f"📊 New RMSE: {old_new['RMSE']:.4f}→{new_new['RMSE']:.4f} | "
        f"Old val RMSE: {old_old['RMSE']:.4f}→{new_old['RMSE']:.4f}"
    )
    return improved and no_regress, new_new


# ── Fix 7: actual tree count from booster ────────────────
def _tree_count(model):
    try:
        return len(model.booster_.dump_model()["tree_info"])
    except Exception:
        return model.n_estimators


# ── Fine-Tune ─────────────────────────────────────────────
def fine_tune():
    meta = _load_meta()

    if meta["fine_tune_count"] >= MAX_FINE_TUNE_ROUNDS:
        logger.warning(f"⚠️ fine_tune_count={meta['fine_tune_count']} ≥ {MAX_FINE_TUNE_ROUNDS} → forcing retrain")
        return sliding_window_retrain()

    _backup_model()
    old_model = joblib.load(f"{MODEL_DIR}/model.pkl")

    # Fix 7: check actual booster tree count
    n_trees = _tree_count(old_model)
    if n_trees > MAX_TREES:
        logger.warning(f"⚠️ Booster has {n_trees} trees > {MAX_TREES} → forcing retrain")
        return sliding_window_retrain()

    df_new  = pd.read_parquet(f"{PROCESSED_DIR}/actual_month_features.parquet")
    df_full = pd.read_parquet(f"{PROCESSED_DIR}/features.parquet")
    df_full["date"] = pd.to_datetime(df_full["date"])
    df_new["date"]  = pd.to_datetime(df_new["date"])

    # Fix 1: use schema cols, not dtype-derived
    X_cols = _get_feature_cols()

    if not validate_feature_schema(X_cols):
        logger.error("❌ Feature schema mismatch — aborting fine-tune")
        return {}

    # Date-based 90-day window — tail() row count breaks when dataset size changes
    cutoff_date = df_full["date"].max() - pd.DateOffset(days=90)
    recent      = df_full[df_full["date"] >= cutoff_date]
    train_df    = pd.concat([recent, df_new], ignore_index=True).drop_duplicates(["id", "date"])

    X_train    = train_df[X_cols]
    y_train    = train_df["sales"]
    X_new_only = df_new[X_cols]
    y_new_only = df_new["sales"]

    lr = 0.02 if len(train_df) < 10_000 else 0.01

    new_model = lgb.LGBMRegressor(
        objective="regression", metric="rmse",
        learning_rate=lr, num_leaves=127,
        feature_fraction=0.8, bagging_fraction=0.8,
        bagging_freq=1, min_data_in_leaf=50,
        verbosity=-1, n_estimators=500, random_state=42
    )
    new_model.fit(X_train, y_train, init_model=old_model.booster_)

    should_deploy, new_metrics = _dual_eval(old_model, new_model, X_new_only, y_new_only, df_full, X_cols)

    if should_deploy:
        joblib.dump(new_model, f"{MODEL_DIR}/model.pkl")
        _save_version(new_model, new_metrics, X_cols, "finetune")

        updated = pd.concat([df_full, df_new], ignore_index=True).drop_duplicates(["id", "date"])
        updated.to_parquet(f"{PROCESSED_DIR}/features.parquet", index=False)
        _update_predictions(new_model, updated)  # Fix 5: full df

        meta["fine_tune_count"] += 1
        _save_meta(meta)
        logger.info(f"✅ Fine-tuned deployed (fine_tune_count={meta['fine_tune_count']})")
        return new_metrics
    else:
        _rollback()
        logger.warning("⚠️ Fine-tune failed dual eval — rolled back")
        return _eval_metrics(old_model, X_new_only, y_new_only)[0]


# ── Sliding Window Retrain ────────────────────────────────
def sliding_window_retrain():
    logger.info("🔁 Sliding window retrain started...")
    df     = pd.read_parquet(f"{PROCESSED_DIR}/features.parquet")
    df_new = pd.read_parquet(f"{PROCESSED_DIR}/actual_month_features.parquet")
    df["date"]     = pd.to_datetime(df["date"])
    df_new["date"] = pd.to_datetime(df_new["date"])

    df = pd.concat([df, df_new], ignore_index=True).drop_duplicates(["id", "date"]).sort_values(["id", "date"])

    max_date  = df["date"].max()
    window_df = df[df["date"] >= max_date - pd.DateOffset(months=WINDOW_MONTHS)]
    cutoff    = max_date - pd.DateOffset(months=1)
    train     = window_df[window_df["date"] <= cutoff]
    valid     = window_df[window_df["date"] >  cutoff]

    # Fix 1: schema-based cols
    X_cols = _get_feature_cols()

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
        verbosity=-1, n_estimators=2000, random_state=42
    )
    new_model.fit(X_tr, y_tr, eval_set=[(X_va, y_va)],
                  callbacks=[lgb.early_stopping(100), lgb.log_evaluation(200)])
    new_metrics, _ = _eval_metrics(new_model, X_va, y_va)

    # regression check on last full month — tail(30) was 30 rows, not 30 days
    max_date_full  = df["date"].max()
    old_val_df     = df[df["date"] >= max_date_full - pd.DateOffset(months=1)]
    new_old, _     = _eval_metrics(new_model, old_val_df[X_cols], old_val_df["sales"])
    old_old, _     = _eval_metrics(old_model, old_val_df[X_cols], old_val_df["sales"])
    no_regression  = new_old["RMSE"] <= old_old["RMSE"] * 1.05

    if new_metrics["RMSE"] < old_metrics["RMSE"] * 0.98 and no_regression:
        joblib.dump(new_model, f"{MODEL_DIR}/model.pkl")
        _save_version(new_model, new_metrics, X_cols, "retrain")
        save_feature_schema(X_cols)

        df.to_parquet(f"{PROCESSED_DIR}/features.parquet", index=False)
        _update_predictions(new_model, df)  # Fix 5: full df, not window_df

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

    # Fix 1: schema-based feature cols
    X_cols = _get_feature_cols()

    # Fix 3: load calendar for wm_yr_wk updates
    calendar = pd.read_csv(f"{RAW_DIR}/calendar.csv", usecols=["date", "wm_yr_wk"])
    calendar["date"] = pd.to_datetime(calendar["date"])

    # price_norm stats already in last_known from features.parquet — no merge needed

    last_known = df.sort_values("date").groupby("id").last().reset_index()

    # Per-SKU mean for padding — zero-padding biases lag features downward
    sku_means = df.groupby("id")["sales"].mean().to_dict()

    buf = {}
    for id_, grp in df.groupby("id"):
        vals    = grp.sort_values("date")["sales"].values[-28:]
        pad_n   = max(0, 28 - len(vals))
        pad_val = sku_means.get(id_, 0.0)
        buf[id_] = np.pad(vals, (pad_n, 0), constant_values=pad_val)

    # Per-SKU historical std for confidence intervals
    sku_std = df.groupby("id")["sales"].std().fillna(0).to_dict()

    results = []

    for d in future_dates:
        day_rows = last_known.copy()
        day_rows["date"]       = d
        day_rows["month"]      = d.month
        day_rows["year"]       = d.year
        day_rows["dayofweek"]  = d.dayofweek
        day_rows["weekofyear"] = d.isocalendar().week
        day_rows["is_weekend"] = int(d.dayofweek >= 5)
        day_rows["dow_sin"]    = np.sin(2 * np.pi * d.dayofweek / 7)
        day_rows["dow_cos"]    = np.cos(2 * np.pi * d.dayofweek / 7)

        # update wm_yr_wk and weekofyear for this forecast date
        wm = calendar.loc[calendar["date"] == d, "wm_yr_wk"]
        if len(wm) > 0:
            day_rows["wm_yr_wk"] = wm.values[0]
        day_rows["weekofyear"] = d.isocalendar().week

        # recompute price_norm using already-present price_max/price_min from last_known
        day_rows["price_norm"] = (
            (day_rows["sell_price"] - day_rows["price_min"]) /
            (day_rows["price_max"] - day_rows["price_min"] + 1e-9)
        )

        ids = day_rows["id"].values
        for lag_name, lag_n in [("lag_1", 1), ("lag_7", 7), ("lag_14", 14), ("lag_28", 28)]:
            day_rows[lag_name] = [buf[i][-lag_n] for i in ids]
        for w, wname in [(7, "rmean_7"), (14, "rmean_14"), (28, "rmean_28")]:
            day_rows[wname] = [buf[i][-w:].mean() for i in ids]
        for w, wname in [(7, "rstd_7"), (14, "rstd_14"), (28, "rstd_28")]:
            day_rows[wname] = [buf[i][-w:].std() for i in ids]

        # Fix 4: strict schema enforcement — no silent column drops
        missing_cols = set(X_cols) - set(day_rows.columns)
        if missing_cols:
            raise ValueError(f"Missing features in forecast day {d.date()}: {missing_cols}")

        X_day = day_rows[X_cols]
        preds = model.predict(X_day).clip(0)
        day_rows["predicted_sales"] = preds

        # Per-SKU confidence interval using historical sales std
        per_sku_std       = np.array([sku_std.get(i, 0.0) for i in ids])
        day_rows["upper"] = (preds + 1.96 * per_sku_std).clip(0)
        day_rows["lower"] = (preds - 1.96 * per_sku_std).clip(0)

        for i, id_ in enumerate(ids):
            buf[id_] = np.append(buf[id_], preds[i])[-28:]

        results.append(day_rows[["id", "date", "predicted_sales", "upper", "lower"]])
        logger.info(f"  📅 {d.date()} — {len(ids):,} SKUs")

    out = pd.concat(results, ignore_index=True)
    out.to_parquet(f"{PROCESSED_DIR}/next_month_predictions.parquet", index=False)
    logger.info(f"✅ Forecast complete → {len(out):,} rows | {next_start.date()} → {next_end.date()}")
    return out
