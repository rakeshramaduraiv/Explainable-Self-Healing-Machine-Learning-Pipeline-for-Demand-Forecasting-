"""
Prepare real Kaggle data for the SH-DFS pipeline.

Files used:
  train.csv          — 913,000 rows | date, store, item, sales | 2013-2017
  test.csv           — 45,000 rows  | id, date, store, item    | 2018 (no sales)
  sample_submission  — 45,000 rows  | id, sales                | filled after prediction

Pipeline data (data/uploaded_data.csv):
  Uses ALL years from train.csv aggregated to weekly demand.
  All years except last → training. Last year → test simulation + drift detection.

Submission data (data/submission_input.csv):
  Uses test.csv (2018) — fed to model after training for final predictions.
  Results written to data/sample_submission_filled.csv.
"""

import pandas as pd
import os
import sys

TRAIN_CSV      = "train.csv"
TEST_CSV       = "test.csv"
SUBMISSION_CSV = "sample_submission.csv"
OUT_PIPELINE   = "data/uploaded_data.csv"
OUT_SUBMISSION = "data/submission_input.csv"


def _weekly(df):
    """Aggregate daily rows to weekly (week-ending Friday)."""
    df["week"] = df["date"].dt.to_period("W-FRI").apply(lambda p: p.end_time.normalize())
    weekly = df.groupby(["week", "store", "item"])["sales"].sum().reset_index()
    return weekly


def prepare_pipeline():
    """Process train.csv → data/uploaded_data.csv (2016 + 2017, weekly)."""
    print(f"Reading {TRAIN_CSV}...")
    df = pd.read_csv(TRAIN_CSV)
    df.columns = df.columns.str.strip().str.lower()
    df["date"] = pd.to_datetime(df["date"])

    print(f"  Rows: {len(df):,} | Stores: {df['store'].nunique()} | Items: {df['item'].nunique()}")
    print(f"  Range: {df['date'].min().date()} → {df['date'].max().date()}")

    weekly = _weekly(df)
    weekly["year"] = weekly["week"].dt.year

    # Use last 2 full years for train+test simulation (last year = test, rest = train)
    years = sorted(weekly["year"].unique())
    use = years  # use ALL available years
    weekly = weekly[weekly["year"].isin(use)].copy()
    print(f"  Using all years: {use[0]} – {use[-1]} (last year = test simulation, rest = training)")

    out = pd.DataFrame({
        "Date":    weekly["week"].dt.strftime("%d-%m-%Y"),
        "Store":   weekly["store"].astype(int),
        "Product": weekly["item"].astype(int),
        "Demand":  weekly["sales"].astype(int),
    }).sort_values(["Date", "Store", "Product"]).reset_index(drop=True)

    os.makedirs("data", exist_ok=True)
    out.to_csv(OUT_PIPELINE, index=False)
    print(f"  Saved {len(out):,} rows → {OUT_PIPELINE}")
    for y in use:
        ydf = out[pd.to_datetime(out["Date"], dayfirst=True).dt.year == y]
        print(f"    {y}: {len(ydf):,} rows")
    return out


def prepare_submission():
    """Process test.csv + sample_submission.csv → data/submission_input.csv."""
    print(f"\nReading {TEST_CSV} + {SUBMISSION_CSV}...")
    te = pd.read_csv(TEST_CSV)
    te.columns = te.columns.str.strip().str.lower()
    te["date"] = pd.to_datetime(te["date"])

    out = pd.DataFrame({
        "id":      te["id"].astype(int),
        "Date":    te["date"].dt.strftime("%d-%m-%Y"),
        "Store":   te["store"].astype(int),
        "Product": te["item"].astype(int),
    }).sort_values(["Date", "Store", "Product"]).reset_index(drop=True)

    os.makedirs("data", exist_ok=True)
    out.to_csv(OUT_SUBMISSION, index=False)
    print(f"  Saved {len(out):,} rows → {OUT_SUBMISSION}")
    print(f"  Range: {te['date'].min().date()} → {te['date'].max().date()}")
    return out


if __name__ == "__main__":
    missing = [f for f in [TRAIN_CSV, TEST_CSV, SUBMISSION_CSV] if not os.path.exists(f)]
    if missing:
        print(f"ERROR: Missing files: {missing}")
        print("Download from: https://www.kaggle.com/datasets/dhrubangtalukdar/store-item-demand-forecasting-dataset")
        sys.exit(1)

    prepare_pipeline()
    prepare_submission()
    print("\nDone. Run: python main.py")
