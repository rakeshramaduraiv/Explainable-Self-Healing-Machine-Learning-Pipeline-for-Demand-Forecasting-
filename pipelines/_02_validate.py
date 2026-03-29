from pipelines.utils import logger, PROCESSED_DIR
import pandas as pd
import os

CRITICAL_COLS = ["sales", "date", "id"]
MIN_SKUS      = 30_000
MIN_DATE      = pd.Timestamp("2011-01-01")


def validate_data():
    logger.info("🔍 Validating merged data...")
    df = pd.read_parquet(f"{PROCESSED_DIR}/raw_merged.parquet")

    errors = []

    # Fix 1: critical columns only (sell_price / event cols can be null)
    nulls = df[CRITICAL_COLS].isnull().sum()
    if nulls.sum() > 0:
        errors.append(f"Critical nulls: {nulls[nulls > 0].to_dict()}")

    # negative sales
    if df["sales"].lt(0).any():
        errors.append(f"Negative sales: {df['sales'].lt(0).sum():,} rows")

    # duplicates
    dupes = df.duplicated(["id", "date"]).sum()
    if dupes > 0:
        errors.append(f"{dupes:,} duplicate (id, date) rows")

    # Fix 2: date range sanity
    if df["date"].min() < MIN_DATE:
        errors.append(f"Dates before {MIN_DATE.date()} detected")
    if df["date"].max() > pd.Timestamp.today():
        errors.append("Future dates detected")

    # Fix 4: SKU count sanity
    n_skus = df["id"].nunique()
    if n_skus < MIN_SKUS:
        errors.append(f"Only {n_skus:,} SKUs — expected ≥ {MIN_SKUS:,} (ingestion may be incomplete)")

    # Fix 3: gap check — warn only, don't fail (M5 has some legitimate gaps)
    gaps = df.sort_values(["id", "date"]).groupby("id")["date"].diff().dropna().dt.days
    irregular = (gaps > 1).sum()
    if irregular > 0:
        logger.warning(f"⚠️ {irregular:,} date gaps > 1 day detected across SKUs")

    if errors:
        for e in errors:
            logger.error(f"❌ {e}")
        raise ValueError(f"Validation failed with {len(errors)} error(s)")

    logger.info(
        f"✅ Validation passed — {len(df):,} rows | {n_skus:,} SKUs | "
        f"{df['date'].min().date()} → {df['date'].max().date()}"
    )


def validate_upload(actual_df, reference_ids):
    errors = []

    # Minimum upload size — too few rows makes drift metrics meaningless
    if len(actual_df) < 1_000:
        errors.append(f"Upload has only {len(actual_df):,} rows — minimum 1,000 required for reliable drift detection")

    # Fix 7: type check before anything else
    if not pd.api.types.is_numeric_dtype(actual_df["sales"]):
        errors.append("Sales column must be numeric")
        return errors  # can't continue safely

    # date nulls
    if actual_df["date"].isna().any():
        errors.append("Invalid dates — use YYYY-MM-DD format")

    # Fix 2: date range sanity
    if actual_df["date"].min() < MIN_DATE:
        errors.append(f"Upload contains dates before {MIN_DATE.date()}")
    if actual_df["date"].max() > pd.Timestamp.today():
        errors.append("Upload contains future dates")

    # negative sales
    if actual_df["sales"].lt(0).any():
        errors.append("Negative sales values found")

    # Fix 6: outlier warning (not a hard error)
    p99 = actual_df["sales"].quantile(0.99)
    if p99 > 1000:
        logger.warning(f"⚠️ Extreme sales values detected (99th pct = {p99:.0f}) — possible anomaly")

    # duplicates
    if actual_df.duplicated(["id", "date"]).sum() > 0:
        errors.append("Duplicate (id, date) rows found")

    # Fix 5: date continuity — upload must be a continuous month
    dates    = pd.to_datetime(actual_df["date"].unique())
    expected = pd.date_range(dates.min(), dates.max())
    missing  = len(expected) - len(dates)
    if missing > 0:
        errors.append(f"Upload is missing {missing} date(s) — must be a continuous date range")

    # unknown SKU IDs
    if reference_ids is not None:
        unknown = set(actual_df["id"].unique()) - set(reference_ids)
        if unknown:
            errors.append(f"{len(unknown):,} unknown SKU IDs not in training data")

    return errors


def get_expected_upload_month():
    """Returns (year, month) of the next expected upload based on features.parquet max date."""
    feat = pd.read_parquet(os.path.join(PROCESSED_DIR, "features.parquet"))
    max_date = pd.to_datetime(feat["date"]).max()
    nxt = (max_date + pd.Timedelta(days=1)).replace(day=1)
    return nxt.year, int(nxt.month)


def validate_upload_month(actual_df):
    """Raises ValueError if uploaded data is not exactly the next expected month."""
    feat = pd.read_parquet(os.path.join(PROCESSED_DIR, "features.parquet"))
    max_date = pd.to_datetime(feat["date"]).max()
    expected_start = (max_date + pd.Timedelta(days=1)).replace(day=1)
    upload_start   = pd.to_datetime(actual_df["date"]).min().replace(day=1)
    if upload_start != expected_start:
        raise ValueError(
            f"Wrong month uploaded. Expected {expected_start.strftime('%B %Y')}, "
            f"got {upload_start.strftime('%B %Y')}."
        )


if __name__ == "__main__":
    validate_data()
