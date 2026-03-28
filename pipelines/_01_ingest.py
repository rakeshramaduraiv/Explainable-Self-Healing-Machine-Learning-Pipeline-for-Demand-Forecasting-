from pipelines.utils import logger, RAW_DIR, PROCESSED_DIR
import pandas as pd

REQUIRED_SALES_COLS = {"id", "item_id", "dept_id", "cat_id", "store_id", "state_id"}
ID_COLS             = ["id", "item_id", "dept_id", "cat_id", "store_id", "state_id"]


def ingest_data():
    logger.info("🚀 Starting data ingestion...")

    calendar = pd.read_csv(f"{RAW_DIR}/calendar.csv")
    prices   = pd.read_csv(f"{RAW_DIR}/sell_prices.csv")
    sales    = pd.read_csv(f"{RAW_DIR}/sales_train_validation.csv")

    logger.info(f"Loaded — sales:{sales.shape} | calendar:{calendar.shape} | prices:{prices.shape}")

    # Fix 1: column validation
    missing_cols = REQUIRED_SALES_COLS - set(sales.columns)
    if missing_cols:
        raise ValueError(f"Missing columns in sales data: {missing_cols}")

    # Fix 2: melt wide → long
    logger.info("Melting sales data (wide → long)...")
    df = sales.melt(id_vars=ID_COLS, var_name="d", value_name="sales")
    logger.info(f"After melt: {df.shape}")

    # merge calendar + prices
    df = df.merge(calendar, on="d", how="left")
    df = df.merge(prices, on=["store_id", "item_id", "wm_yr_wk"], how="left")

    # Fix: date parsing with coerce to catch corrupt values
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df = df.dropna(subset=["date"])

    # Fix 3: forward-fill price per SKU, then fill remaining with 0
    df["sell_price"] = df.groupby(["store_id", "item_id"])["sell_price"].ffill()
    df["sell_price"] = df["sell_price"].fillna(0)

    # Fix 5: remove duplicates
    before = len(df)
    df = df.drop_duplicates(subset=["id", "date"])
    dupes = before - len(df)
    if dupes:
        logger.warning(f"Removed {dupes:,} duplicate rows")

    # Fix 4: sort for correct lag feature computation downstream
    df = df.sort_values(["id", "date"]).reset_index(drop=True)

    # Fix 6: downcast types to reduce memory
    df["sales"]      = df["sales"].astype("int16")
    df["sell_price"] = df["sell_price"].astype("float32")

    # Fix 7: log shape + missing values
    logger.info(f"Final shape: {df.shape}")
    nulls = df.isnull().sum()
    nulls = nulls[nulls > 0]
    if len(nulls):
        logger.warning(f"Missing values:\n{nulls}")
    else:
        logger.info("No missing values ✅")

    out = f"{PROCESSED_DIR}/raw_merged.parquet"
    df.to_parquet(out, index=False)
    logger.info(f"✅ Ingestion complete → {out}")
    return out


if __name__ == "__main__":
    ingest_data()
