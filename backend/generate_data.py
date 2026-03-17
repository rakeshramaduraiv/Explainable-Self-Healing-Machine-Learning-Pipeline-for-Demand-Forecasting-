"""
Generate Dataset for Self-Healing Product Demand Forecasting
--------------------------------------------------------------
Primary: Use real Kaggle Store Item Demand Forecasting dataset
  https://www.kaggle.com/datasets/dhrubangtalukdar/store-item-demand-forecasting-dataset
  File: train.csv (columns: date, store, item, sales)

Fallback: Generate synthetic data if no Kaggle CSV found.

Usage:
  python generate_data.py                  # auto-detect train.csv or generate synthetic
  python generate_data.py train.csv        # use Kaggle dataset
  python generate_data.py month 2026-01    # generate monthly actuals for prediction cycle
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import os
import sys


def prepare_kaggle(csv_path, num_products=15, output_path="data/uploaded_data.csv"):
    """Convert Kaggle Store Item Demand Forecasting → pipeline format."""
    df = pd.read_csv(csv_path)
    df.columns = df.columns.str.strip().str.lower()
    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values("date")

    print(f"Loaded: {len(df)} rows | {df['store'].nunique()} stores | {df['item'].nunique()} items")
    print(f"Range:  {df['date'].min().date()} -> {df['date'].max().date()}")

    # Store 1, first N items
    df = df[df["store"] == 1].copy()
    items = sorted(df["item"].unique())[:num_products]
    df = df[df["item"].isin(items)].copy()
    item_map = {old: i + 1 for i, old in enumerate(items)}
    df["item"] = df["item"].map(item_map)

    # Daily -> Weekly (Friday end)
    df["week"] = df["date"].dt.to_period("W-FRI").apply(lambda p: p.end_time.date())
    df["week"] = pd.to_datetime(df["week"])
    weekly = df.groupby(["week", "item"])["sales"].sum().reset_index()

    # Last 2 full years (avoid partial last year)
    weekly["year"] = weekly["week"].dt.year
    years = sorted(weekly["year"].unique())
    use = years[-3:-1] if len(years) >= 3 else years[-2:]
    weekly = weekly[weekly["year"].isin(use)].copy()

    print(f"Using:  {use[0]} (train) -> {use[1]} (test)")

    out = pd.DataFrame({
        "Product": weekly["item"].astype(int),
        "Date": weekly["week"].dt.strftime("%d-%m-%Y"),
        "Demand": weekly["sales"].astype(int),
    })
    out = out.sort_values(["Date", "Product"]).reset_index(drop=True)

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    out.to_csv(output_path, index=False)

    out["_d"] = pd.to_datetime(out["Date"], dayfirst=True)
    print(f"\n{'='*55}")
    print(f"KAGGLE STORE ITEM DEMAND FORECASTING DATASET")
    print(f"{'='*55}")
    print(f"Source:   https://www.kaggle.com/datasets/dhrubangtalukdar/store-item-demand-forecasting-dataset")
    print(f"Output:   {output_path}")
    print(f"Rows:     {len(out)}")
    print(f"Products: {out['Product'].nunique()}")
    print(f"Range:    {out['_d'].min().date()} -> {out['_d'].max().date()}")
    for y in sorted(out["_d"].dt.year.unique()):
        ydf = out[out["_d"].dt.year == y]
        print(f"  {y}: {len(ydf)} rows, {ydf['_d'].dt.month.nunique()} months")
    print(f"Demand:   {out['Demand'].min()} - {out['Demand'].max()} units")
    print(f"Mean:     {out['Demand'].mean():.0f} units/week/product")
    print(f"{'='*55}")
    return out


def generate_synthetic(start_year=2024, num_years=2, num_products=5, output_path="data/uploaded_data.csv"):
    """Fallback: generate synthetic demand data."""
    np.random.seed(42)
    rows = []
    bases = {1: 140, 2: 85, 3: 200, 4: 50, 5: 120}

    for year in range(start_year, start_year + num_years):
        start_date = datetime(year, 1, 1)
        first_friday = start_date + timedelta(days=(4 - start_date.weekday()) % 7)
        current_date = first_friday
        while current_date.year == year:
            month = current_date.month
            for pid in range(1, num_products + 1):
                demand = bases[pid]
                demand *= 1 + (year - start_year) * 0.05
                demand *= np.random.uniform(0.82, 1.18)
                rows.append({
                    "Product": pid,
                    "Date": current_date.strftime("%d-%m-%Y"),
                    "Demand": max(1, round(demand)),
                })
            current_date += timedelta(days=7)

    df = pd.DataFrame(rows)
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    df.to_csv(output_path, index=False)
    print(f"Generated synthetic: {len(df)} rows -> {output_path}")
    return df


def generate_monthly_actuals(month_str, num_products=15, output_path=None):
    """Generate monthly actuals for the prediction cycle."""
    np.random.seed(int(month_str.replace("-", "")))
    year, month = map(int, month_str.split("-"))
    if output_path is None:
        os.makedirs("uploads", exist_ok=True)
        output_path = f"uploads/{month_str}_actual.csv"

    rows = []
    start_date = datetime(year, month, 1)
    current_date = start_date + timedelta(days=(4 - start_date.weekday()) % 7)
    while current_date.month == month:
        for pid in range(1, num_products + 1):
            demand = (50 + pid * 20) * np.random.uniform(0.82, 1.18)
            rows.append({
                "Product": pid,
                "Date": current_date.strftime("%d-%m-%Y"),
                "Demand": max(1, round(demand)),
            })
        current_date += timedelta(days=7)

    df = pd.DataFrame(rows)
    df.to_csv(output_path, index=False)
    print(f"Generated {month_str} actuals: {len(df)} rows -> {output_path}")
    return df


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "month":
        month = sys.argv[2] if len(sys.argv) > 2 else "2026-01"
        generate_monthly_actuals(month)
    elif len(sys.argv) > 1 and os.path.exists(sys.argv[1]):
        n = int(sys.argv[2]) if len(sys.argv) > 2 else 15
        prepare_kaggle(sys.argv[1], n)
    elif os.path.exists("train.csv"):
        print("Found train.csv — using Kaggle dataset")
        prepare_kaggle("train.csv")
    else:
        print("No train.csv found — generating synthetic data")
        print("For real data, download from:")
        print("  https://www.kaggle.com/datasets/dhrubangtalukdar/store-item-demand-forecasting-dataset")
        print("  Place train.csv in backend/ and re-run")
        generate_synthetic()
