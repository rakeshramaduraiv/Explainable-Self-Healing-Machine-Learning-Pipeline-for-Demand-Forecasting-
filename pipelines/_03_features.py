from pipelines.utils import logger, RAW_DIR, PROCESSED_DIR
import pandas as pd
import numpy as np
from sklearn.preprocessing import LabelEncoder


def create_features():
    df = pd.read_parquet(f"{PROCESSED_DIR}/raw_merged.parquet")
    df = df.sort_values(["id", "date"])
    logger.info("🧠 Creating time-based features...")

    for lag in [1, 7, 14, 28]:
        df[f"lag_{lag}"] = df.groupby("id")["sales"].shift(lag)
    for w in [7, 14, 28]:
        grp = df.groupby("id")["sales"]
        df[f"rmean_{w}"] = grp.shift(1).rolling(w).mean()
        df[f"rstd_{w}"]  = grp.shift(1).rolling(w).std()

    df["month"]      = df["date"].dt.month
    df["year"]       = df["date"].dt.year
    df["dayofweek"]  = df["date"].dt.dayofweek
    df["is_weekend"] = (df["dayofweek"] >= 5).astype(int)
    df["dow_sin"]    = np.sin(2 * np.pi * df["dayofweek"] / 7)
    df["dow_cos"]    = np.cos(2 * np.pi * df["dayofweek"] / 7)

    df["price_max"]  = df.groupby(["store_id","item_id"])["sell_price"].transform("max")
    df["price_min"]  = df.groupby(["store_id","item_id"])["sell_price"].transform("min")
    df["price_norm"] = (df["sell_price"] - df["price_min"]) / (df["price_max"] - df["price_min"] + 1e-9)

    for col in ["item_id","dept_id","cat_id","store_id","state_id"]:
        le = LabelEncoder()
        df[col] = le.fit_transform(df[col])

    df = df.dropna(subset=["lag_28"]).fillna(0)
    out = f"{PROCESSED_DIR}/features.parquet"
    df.to_parquet(out, index=False)
    logger.info(f"✅ Feature file saved → {out}")
    return out


def _parse_id(df):
    """Extract item_id and store_id from id column if not present."""
    if "item_id" not in df.columns and "id" in df.columns:
        parts = df["id"].str.rsplit("_", n=2)
        df["store_id"] = parts.str[-2] + "_" + parts.str[-1].str.replace("_validation","")
        df["item_id"]  = parts.str[:-2].str.join("_")
    return df


def create_features_for_new_data(df_new):
    """
    FIX 1: Robust feature reconstruction for any upload format.
    Works for both 3-column (id, date, sales) and 14-column uploads.
    Steps: parse_id → merge history → merge calendar → merge prices → lags → filter new rows
    """
    df_new = df_new.copy()
    df_new["date"] = pd.to_datetime(df_new["date"])

    # STEP 1: parse id → extract item_id, store_id if missing
    df_new = _parse_id(df_new)

    # STEP 2: combine with history (only id, date, sales for continuity)
    hist = pd.read_parquet(f"{PROCESSED_DIR}/features.parquet")[["id","date","sales","item_id","dept_id","cat_id","store_id","state_id","wm_yr_wk","sell_price"]]
    hist["date"] = pd.to_datetime(hist["date"])

    # Keep only columns that exist in both for concat
    shared_cols = [c for c in ["id","date","sales","item_id","dept_id","cat_id","store_id","state_id","wm_yr_wk","sell_price"] if c in df_new.columns]
    combined = pd.concat([hist, df_new[shared_cols]], ignore_index=True)
    combined = combined.drop_duplicates(subset=["id","date"]).sort_values(["id","date"])

    # STEP 3: FIX 3 — always merge calendar to get wm_yr_wk for new rows
    calendar = pd.read_csv(f"{RAW_DIR}/calendar.csv", usecols=["date","wm_yr_wk","snap_CA","snap_TX","snap_WI"])
    calendar["date"] = pd.to_datetime(calendar["date"])
    # only fill wm_yr_wk where missing (new rows won't have it from 3-col upload)
    new_mask = combined["date"].isin(df_new["date"].unique())
    combined = combined.merge(calendar.rename(columns={"wm_yr_wk":"wm_yr_wk_cal","snap_CA":"snap_CA_cal","snap_TX":"snap_TX_cal","snap_WI":"snap_WI_cal"}), on="date", how="left")
    if "wm_yr_wk" not in combined.columns:
        combined["wm_yr_wk"] = combined["wm_yr_wk_cal"]
    else:
        combined["wm_yr_wk"] = combined["wm_yr_wk"].fillna(combined["wm_yr_wk_cal"])
    for snap in ["snap_CA","snap_TX","snap_WI"]:
        if snap not in combined.columns:
            combined[snap] = combined[f"{snap}_cal"]
        else:
            combined[snap] = combined[snap].fillna(combined[f"{snap}_cal"])
    combined.drop(columns=[c for c in combined.columns if c.endswith("_cal")], inplace=True)

    # STEP 4: merge prices if sell_price missing
    if "sell_price" not in combined.columns or combined["sell_price"].isna().all():
        prices = pd.read_csv(f"{RAW_DIR}/sell_prices.csv")
        combined = combined.merge(prices, on=["store_id","item_id","wm_yr_wk"], how="left", suffixes=("","_price"))
        if "sell_price_price" in combined.columns:
            combined["sell_price"] = combined["sell_price"].fillna(combined["sell_price_price"])
            combined.drop(columns=["sell_price_price"], inplace=True)

    combined["sell_price"] = combined["sell_price"].fillna(combined.groupby(["store_id","item_id"])["sell_price"].transform("median"))
    combined["sell_price"] = combined["sell_price"].fillna(0)

    # STEP 5: lag + rolling features
    combined = combined.sort_values(["id","date"])
    for lag in [1, 7, 14, 28]:
        combined[f"lag_{lag}"] = combined.groupby("id")["sales"].shift(lag)
    for w in [7, 14, 28]:
        grp = combined.groupby("id")["sales"]
        combined[f"rmean_{w}"] = grp.shift(1).rolling(w).mean()
        combined[f"rstd_{w}"]  = grp.shift(1).rolling(w).std()

    combined["month"]      = combined["date"].dt.month
    combined["year"]       = combined["date"].dt.year
    combined["dayofweek"]  = combined["date"].dt.dayofweek
    combined["is_weekend"] = (combined["dayofweek"] >= 5).astype(int)
    combined["dow_sin"]    = np.sin(2 * np.pi * combined["dayofweek"] / 7)
    combined["dow_cos"]    = np.cos(2 * np.pi * combined["dayofweek"] / 7)

    combined["price_max"]  = combined.groupby(["store_id","item_id"])["sell_price"].transform("max")
    combined["price_min"]  = combined.groupby(["store_id","item_id"])["sell_price"].transform("min")
    combined["price_norm"] = (combined["sell_price"] - combined["price_min"]) / (combined["price_max"] - combined["price_min"] + 1e-9)

    for col in ["item_id","dept_id","cat_id","store_id","state_id"]:
        if col in combined.columns and combined[col].dtype == object:
            le = LabelEncoder()
            combined[col] = le.fit_transform(combined[col].astype(str))

    # STEP 6: filter only new month rows
    new_dates = df_new["date"].unique()
    result = combined[combined["date"].isin(new_dates)].copy()
    result = result.dropna(subset=["lag_28"]).fillna(0)

    for col in result.select_dtypes(include="object").columns:
        result[col] = result[col].astype(str)

    # STEP 7: save
    result.to_parquet(f"{PROCESSED_DIR}/actual_month_features.parquet", index=False)
    logger.info(f"✅ New month features saved → {len(result):,} rows")
    return result


if __name__ == "__main__":
    create_features()
