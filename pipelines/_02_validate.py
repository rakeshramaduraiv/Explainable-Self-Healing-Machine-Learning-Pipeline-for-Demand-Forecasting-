from pipelines.utils import logger, PROCESSED_DIR
import pandas as pd


def validate_data():
    logger.info("🔍 Validating merged data...")
    df = pd.read_parquet(f"{PROCESSED_DIR}/raw_merged.parquet")

    errors = []

    # 1. Negative sales
    if not df["sales"].ge(0).all():
        errors.append(f"Negative sales found: {df[df['sales'] < 0].shape[0]} rows")

    # 2. Null values
    null_counts = df.isnull().sum()
    critical_nulls = null_counts[null_counts > 0]
    if len(critical_nulls) > 0:
        errors.append(f"Null values found: {critical_nulls.to_dict()}")

    # 3. Duplicate rows
    dupes = df.duplicated(["id", "date"]).sum()
    if dupes > 0:
        errors.append(f"Duplicate (id, date) rows: {dupes}")

    # 4. Date gaps per SKU
    df_sorted = df.sort_values(["id", "date"])
    gaps = df_sorted.groupby("id")["date"].diff().dropna().dt.days
    max_gap = gaps.max()
    if max_gap > 1:
        logger.warning(f"⚠️ Max date gap across SKUs: {max_gap} days — may affect lag features")

    if errors:
        for e in errors:
            logger.error(f"❌ {e}")
        raise ValueError(f"Validation failed with {len(errors)} error(s). See logs above.")

    logger.info(f"✅ Validation passed — {len(df):,} rows | {df['id'].nunique():,} SKUs | date range: {df['date'].min().date()} → {df['date'].max().date()}")


def validate_upload(actual_df, reference_ids):
    """Validate user-uploaded actual month data against known SKU IDs."""
    errors = []

    # 1. Date nulls
    if actual_df["date"].isna().any():
        errors.append("Invalid dates found — use YYYY-MM-DD format")

    # 2. Negative sales
    if actual_df["sales"].lt(0).any():
        errors.append("Negative sales values found")

    # 3. Unknown SKU IDs
    if reference_ids is not None:
        unknown = set(actual_df["id"].unique()) - set(reference_ids)
        if unknown:
            errors.append(f"{len(unknown)} unknown SKU IDs found — not in training data")

    # 4. Duplicates
    dupes = actual_df.duplicated(["id", "date"]).sum()
    if dupes > 0:
        errors.append(f"{dupes} duplicate (id, date) rows found")

    return errors


if __name__ == "__main__":
    validate_data()
