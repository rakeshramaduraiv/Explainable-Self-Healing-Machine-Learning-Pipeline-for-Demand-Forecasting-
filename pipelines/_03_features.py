from pipelines.utils import logger, RAW_DIR, PROCESSED_DIR
import pandas as pd
import numpy as np
from sklearn.preprocessing import LabelEncoder

def create_features():
    df = pd.read_parquet(f"{PROCESSED_DIR}/raw_merged.parquet")
    df = df.sort_values(["id", "date"])
    logger.info("🧠 Creating time-based features...")

    # Lags
    for lag in [1, 7, 14, 28]:
        df[f"lag_{lag}"] = df.groupby("id")["sales"].shift(lag)

    # Rolling windows
    for w in [7, 14, 28]:
        grp = df.groupby("id")["sales"]
        df[f"rmean_{w}"] = grp.shift(1).rolling(w).mean()
        df[f"rstd_{w}"] = grp.shift(1).rolling(w).std()

    # Date features
    df['month'] = df['date'].dt.month
    df['year'] = df['date'].dt.year
    df['dayofweek'] = df['date'].dt.dayofweek
    df['is_weekend'] = (df['dayofweek'] >= 5).astype(int)

    # Cyclic encoding
    df['dow_sin'] = np.sin(2 * np.pi * df['dayofweek'] / 7)
    df['dow_cos'] = np.cos(2 * np.pi * df['dayofweek'] / 7)

    # Price normalization
    df['price_max'] = df.groupby(['store_id','item_id'])['sell_price'].transform('max')
    df['price_min'] = df.groupby(['store_id','item_id'])['sell_price'].transform('min')
    df['price_norm'] = (df['sell_price'] - df['price_min']) / (df['price_max'] - df['price_min'])

    # Label encoding
    for col in ['item_id','dept_id','cat_id','store_id','state_id']:
        le = LabelEncoder()
        df[col] = le.fit_transform(df[col])

    df = df.dropna(subset=['lag_28']).fillna(0)
    out = f"{PROCESSED_DIR}/features.parquet"
    df.to_parquet(out, index=False)
    logger.info(f"✅ Feature file saved → {out}")
    return out

def create_features_for_new_data(df_new):
    """Engineer features for a newly uploaded month's data."""
    # Load existing features to get label encoder mappings
    df_hist = pd.read_parquet(f"{PROCESSED_DIR}/features.parquet")
    df_new  = df_new.sort_values(["id", "date"])

    # Append to history for lag/rolling continuity
    combined = pd.concat([df_hist, df_new], ignore_index=True).drop_duplicates(subset=["id","date"])
    combined = combined.sort_values(["id", "date"])

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

    if "sell_price" in combined.columns:
        combined["price_max"]  = combined.groupby(["store_id","item_id"])["sell_price"].transform("max")
        combined["price_min"]  = combined.groupby(["store_id","item_id"])["sell_price"].transform("min")
        combined["price_norm"] = (combined["sell_price"] - combined["price_min"]) / (combined["price_max"] - combined["price_min"] + 1e-9)

    for col in ["item_id","dept_id","cat_id","store_id","state_id"]:
        if col in combined.columns and combined[col].dtype == object:
            le = LabelEncoder()
            combined[col] = le.fit_transform(combined[col].astype(str))

    # Return only the new month rows with features
    new_dates  = df_new["date"].unique()
    result     = combined[combined["date"].isin(new_dates)].dropna(subset=["lag_28"]).fillna(0)

    # Fix mixed-type object columns before saving to parquet
    for col in result.select_dtypes(include="object").columns:
        result[col] = result[col].astype(str)

    out        = f"{PROCESSED_DIR}/actual_month_features.parquet"
    result.to_parquet(out, index=False)
    logger.info(f"✅ New month features saved → {out}")
    return result


if __name__ == "__main__":
    create_features()
