from pipelines.utils import logger, RAW_DIR, PROCESSED_DIR
from pipelines._drift import save_feature_schema, validate_feature_schema
import pandas as pd
import numpy as np
from sklearn.preprocessing import LabelEncoder
import joblib
import os

ENCODER_PATH = os.path.join(PROCESSED_DIR, "encoders.pkl")
CAT_COLS     = ["item_id", "dept_id", "cat_id", "store_id", "state_id"]
LAG_COLS     = [1, 7, 14, 28]
ROLL_WINDOWS = [7, 14, 28]
CAL_COLS     = ["date", "wm_yr_wk", "snap_CA", "snap_TX", "snap_WI"]


# ── Fix 2: correct M5 id parsing ─────────────────────────
def _parse_id(df):
    if "item_id" not in df.columns and "id" in df.columns:
        parts          = df["id"].str.split("_")
        df["cat_id"]   = parts.str[0]
        df["dept_id"]  = parts.str[0] + "_" + parts.str[1]
        df["item_id"]  = parts.str[0] + "_" + parts.str[1] + "_" + parts.str[2]
        df["state_id"] = parts.str[3]
        df["store_id"] = parts.str[3] + "_" + parts.str[4]
    return df


# ── Fix 1: save encoders fitted on training data ──────────
def _fit_and_save_encoders(df):
    encoders = {}
    for col in CAT_COLS:
        if col in df.columns:
            le = LabelEncoder()
            df[col] = le.fit_transform(df[col].astype(str))
            encoders[col] = le
    joblib.dump(encoders, ENCODER_PATH)
    logger.info(f"✅ Encoders saved → {ENCODER_PATH}")
    return df


# ── Bootstrap encoders from existing features.parquet ────
def bootstrap_encoders():
    """Build and save encoders.pkl from already-existing features.parquet.
    Called automatically when encoders.pkl is missing.
    """
    logger.info("🔧 Bootstrapping encoders from features.parquet...")
    feat_path = os.path.join(PROCESSED_DIR, "features.parquet")
    if not os.path.exists(feat_path):
        raise FileNotFoundError("features.parquet not found — run create_features() first")
    df = pd.read_parquet(feat_path)
    # rebuild original string labels from raw_merged if available
    raw_path = os.path.join(PROCESSED_DIR, "raw_merged.parquet")
    if os.path.exists(raw_path):
        raw = pd.read_parquet(raw_path, columns=[c for c in CAT_COLS if c in pd.read_parquet(raw_path, columns=CAT_COLS).columns])
        encoders = {}
        for col in CAT_COLS:
            if col in raw.columns:
                le = LabelEncoder()
                le.fit(raw[col].astype(str).unique())
                encoders[col] = le
    else:
        # fallback: fit on integer codes already in features.parquet
        encoders = {}
        for col in CAT_COLS:
            if col in df.columns:
                le = LabelEncoder()
                le.fit(df[col].astype(str).unique())
                encoders[col] = le
    joblib.dump(encoders, ENCODER_PATH)
    logger.info(f"✅ Encoders bootstrapped → {ENCODER_PATH}")
    return encoders


# ── Fix 1: apply saved encoders on new data ───────────────
def _apply_encoders(df):
    if not os.path.exists(ENCODER_PATH):
        logger.warning("⚠️ encoders.pkl missing — auto-bootstrapping")
        bootstrap_encoders()
    encoders = joblib.load(ENCODER_PATH)
    for col in CAT_COLS:
        if col in df.columns and df[col].dtype == object:
            le      = encoders[col]
            known   = set(le.classes_)
            df[col] = df[col].astype(str).apply(lambda x: x if x in known else le.classes_[0])
            df[col] = le.transform(df[col])
    return df


# ── Shared: lag + rolling features ───────────────────────
def _add_lag_roll(df):
    df = df.sort_values(["id", "date"]).reset_index(drop=True)  # Fix 7
    grp = df.groupby("id")["sales"]
    for lag in LAG_COLS:
        df[f"lag_{lag}"] = grp.shift(lag)
    for w in ROLL_WINDOWS:
        df[f"rmean_{w}"] = grp.shift(1).rolling(w).mean()
        df[f"rstd_{w}"]  = grp.shift(1).rolling(w).std()
    return df


# ── Shared: date + price features ────────────────────────
def _add_date_price_features(df):
    df["month"]      = df["date"].dt.month
    df["year"]       = df["date"].dt.year
    df["dayofweek"]  = df["date"].dt.dayofweek
    df["is_weekend"] = (df["dayofweek"] >= 5).astype(int)
    df["dow_sin"]    = np.sin(2 * np.pi * df["dayofweek"] / 7)
    df["dow_cos"]    = np.cos(2 * np.pi * df["dayofweek"] / 7)

    df["price_max"]  = df.groupby(["store_id", "item_id"])["sell_price"].transform("max")
    df["price_min"]  = df.groupby(["store_id", "item_id"])["sell_price"].transform("min")
    df["price_norm"] = (df["sell_price"] - df["price_min"]) / (df["price_max"] - df["price_min"] + 1e-9)
    return df


def create_features():
    df = pd.read_parquet(f"{PROCESSED_DIR}/raw_merged.parquet")
    logger.info(f"🧠 Creating features — {df.shape}")

    # Fix 8: downcast early to reduce memory
    df["sales"]      = df["sales"].astype("float32")
    df["sell_price"] = df["sell_price"].astype("float32")

    df = _add_lag_roll(df)
    df = _add_date_price_features(df)

    # Fix 1: fit + save encoders
    df = _fit_and_save_encoders(df)

    # Fix 5: drop lag_28 nulls only, fill sell_price only — no blanket fillna
    df = df.dropna(subset=["lag_28"])
    df["sell_price"] = df["sell_price"].fillna(0)

    # Fix 9: empty result guard
    if df.empty:
        raise ValueError("Feature dataframe is empty after dropna — check raw data")

    out = f"{PROCESSED_DIR}/features.parquet"
    df.to_parquet(out, index=False)

    # Fix 6: save feature schema for retrain validation
    feat_cols = [c for c in df.columns if c not in ["id", "date", "sales"]
                 and df[c].dtype != object]
    save_feature_schema(feat_cols)

    logger.info(f"✅ Features saved → {out} | {len(df):,} rows | {len(feat_cols)} features")
    return out


def create_features_for_new_data(df_new):
    df_new = df_new.copy()
    df_new["date"] = pd.to_datetime(df_new["date"])

    # Fix 2: correct id parsing
    df_new = _parse_id(df_new)

    # combine with history
    hist_cols = ["id", "date", "sales", "item_id", "dept_id", "cat_id",
                 "store_id", "state_id", "wm_yr_wk", "sell_price"]
    hist = pd.read_parquet(f"{PROCESSED_DIR}/features.parquet")[
        [c for c in hist_cols if c in pd.read_parquet(f"{PROCESSED_DIR}/features.parquet").columns]
    ]
    hist["date"] = pd.to_datetime(hist["date"])

    shared = [c for c in hist_cols if c in df_new.columns]
    combined = pd.concat([hist, df_new[shared]], ignore_index=True)
    combined = combined.drop_duplicates(subset=["id", "date"]).sort_values(["id", "date"]).reset_index(drop=True)

    # Fix 3: calendar merge — only needed columns
    calendar = pd.read_csv(f"{RAW_DIR}/calendar.csv", usecols=CAL_COLS)
    calendar["date"] = pd.to_datetime(calendar["date"])
    combined = combined.merge(
        calendar.rename(columns={c: f"{c}_cal" for c in CAL_COLS if c != "date"}),
        on="date", how="left"
    )
    for col in ["wm_yr_wk", "snap_CA", "snap_TX", "snap_WI"]:
        cal_col = f"{col}_cal"
        if col not in combined.columns:
            combined[col] = combined[cal_col]
        else:
            combined[col] = combined[col].fillna(combined[cal_col])
        combined.drop(columns=[cal_col], inplace=True, errors="ignore")

    # Fix 4: merge prices if ANY sell_price is missing (not just all)
    if "sell_price" not in combined.columns or combined["sell_price"].isna().sum() > 0:
        prices = pd.read_csv(f"{RAW_DIR}/sell_prices.csv")
        combined = combined.merge(prices, on=["store_id", "item_id", "wm_yr_wk"],
                                  how="left", suffixes=("", "_price"))
        if "sell_price_price" in combined.columns:
            combined["sell_price"] = combined["sell_price"].fillna(combined.pop("sell_price_price"))

    combined["sell_price"] = combined.groupby(["store_id", "item_id"])["sell_price"].ffill()
    combined["sell_price"] = combined["sell_price"].fillna(0)

    # Fix 8: downcast
    combined["sales"]      = combined["sales"].astype("float32")
    combined["sell_price"] = combined["sell_price"].astype("float32")

    combined = _add_lag_roll(combined)
    combined = _add_date_price_features(combined)

    # Fix 1: apply saved encoders (consistent with training)
    combined = _apply_encoders(combined)

    # filter to new month rows only
    new_dates = df_new["date"].unique()
    result = combined[combined["date"].isin(new_dates)].copy()
    result = result.dropna(subset=["lag_28"])

    # Fix 5: targeted fill only — no blanket fillna(0)
    result["sell_price"] = result["sell_price"].fillna(0)

    # Fix 9: empty result guard
    if result.empty:
        raise ValueError("No valid rows after feature generation — check upload date range")

    # Fix 6: save/update schema from result (always in sync)
    _DROP = {"id", "date", "sales", "item_id", "dept_id", "cat_id", "store_id", "state_id"}
    feat_cols = [c for c in result.columns if c not in _DROP and result[c].dtype != object]
    expected  = load_feature_schema()
    if expected is not None and set(expected) != set(feat_cols):
        logger.warning(f"Schema updated: {set(expected)-set(feat_cols)} removed | {set(feat_cols)-set(expected)} added")
        save_feature_schema(feat_cols)

    result.to_parquet(f"{PROCESSED_DIR}/actual_month_features.parquet", index=False)
    logger.info(f"✅ New month features saved → {len(result):,} rows | {len(feat_cols)} features")
    return result


if __name__ == "__main__":
    create_features()
