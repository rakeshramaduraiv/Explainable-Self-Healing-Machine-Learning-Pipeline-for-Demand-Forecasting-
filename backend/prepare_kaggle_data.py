"""
Kaggle Store Item Demand Forecasting → SH-DFS Format
------------------------------------------------------
Dataset: https://www.kaggle.com/competitions/demand-forecasting-kernels-only
File:    train.csv (columns: date, store, item, sales)

Converts daily item sales → weekly product demand for the pipeline.
Picks Store 1, first 15 items, last 2 full years.

Usage:
  python prepare_kaggle_data.py train.csv
"""

import pandas as pd
import os
import sys


def prepare(csv_path, num_products=15, output_path="data/uploaded_data.csv"):
    df = pd.read_csv(csv_path)
    df.columns = df.columns.str.strip().str.lower()

    # Parse
    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values("date")

    print(f"Loaded: {len(df)} rows | {df['store'].nunique()} stores | {df['item'].nunique()} items")
    print(f"Range:  {df['date'].min().date()} → {df['date'].max().date()}")

    # Store 1, first N items
    df = df[df["store"] == 1].copy()
    items = sorted(df["item"].unique())[:num_products]
    df = df[df["item"].isin(items)].copy()

    # Remap item IDs → 1..N
    item_map = {old: i + 1 for i, old in enumerate(items)}
    df["item"] = df["item"].map(item_map)

    # Daily → Weekly (Friday end)
    df["week"] = df["date"].dt.to_period("W-FRI").apply(lambda p: p.end_time.date())
    df["week"] = pd.to_datetime(df["week"])
    weekly = df.groupby(["week", "item"])["sales"].sum().reset_index()

    # Last 2 full years
    weekly["year"] = weekly["week"].dt.year
    years = sorted(weekly["year"].unique())
    use = years[-3:-1] if len(years) >= 3 else years[-2:]  # avoid partial last year
    weekly = weekly[weekly["year"].isin(use)].copy()

    print(f"Using:  {use[0]} (train) → {use[1]} (test)")
    print(f"Weeks:  {weekly['week'].nunique()} | Rows: {len(weekly)}")

    # Format for pipeline
    out = pd.DataFrame({
        "Product": weekly["item"].astype(int),
        "Date": weekly["week"].dt.strftime("%d-%m-%Y"),
        "Demand": weekly["sales"].astype(int),
    })
    out = out.sort_values(["Date", "Product"]).reset_index(drop=True)

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    out.to_csv(output_path, index=False)

    # Summary
    out["_d"] = pd.to_datetime(out["Date"], dayfirst=True)
    print(f"\n{'='*50}")
    print(f"OUTPUT: {output_path}")
    print(f"Rows:     {len(out)}")
    print(f"Products: {out['Product'].nunique()}")
    print(f"Range:    {out['_d'].min().date()} → {out['_d'].max().date()}")
    for y in sorted(out["_d"].dt.year.unique()):
        ydf = out[out["_d"].dt.year == y]
        print(f"  {y}: {len(ydf)} rows, {ydf['_d'].dt.month.nunique()} months")
    print(f"Demand:   {out['Demand'].min()} – {out['Demand'].max()} units")
    print(f"Mean:     {out['Demand'].mean():.0f} units/week/product")
    print(f"{'='*50}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python prepare_kaggle_data.py <train.csv> [num_products]")
        print()
        print("Download train.csv from:")
        print("  https://www.kaggle.com/competitions/demand-forecasting-kernels-only/data")
        sys.exit(1)

    path = sys.argv[1]
    n = int(sys.argv[2]) if len(sys.argv) > 2 else 15
    prepare(path, n)
