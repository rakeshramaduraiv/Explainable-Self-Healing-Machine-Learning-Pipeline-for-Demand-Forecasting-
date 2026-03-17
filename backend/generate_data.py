"""
Generate Dataset for Self-Healing Product Demand Forecasting
--------------------------------------------------------------
Uses ONLY the real Kaggle Store Item Demand Forecasting dataset.
  https://www.kaggle.com/datasets/dhrubangtalukdar/store-item-demand-forecasting-dataset
  File: train.csv (columns: date, store, item, sales)

Usage:
  python generate_data.py                  # auto-detect train.csv
  python generate_data.py train.csv        # explicit path
  python generate_data.py train.csv 15     # use first 15 items
"""

import pandas as pd
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


if __name__ == "__main__":
    if len(sys.argv) > 1 and os.path.exists(sys.argv[1]):
        n = int(sys.argv[2]) if len(sys.argv) > 2 else 15
        prepare_kaggle(sys.argv[1], n)
    elif os.path.exists("train.csv"):
        print("Found train.csv — using Kaggle dataset")
        prepare_kaggle("train.csv")
    else:
        print("ERROR: train.csv not found.")
        print("Download the Kaggle dataset from:")
        print("  https://www.kaggle.com/datasets/dhrubangtalukdar/store-item-demand-forecasting-dataset")
        print("Place train.csv in the backend/ folder and re-run.")
        sys.exit(1)
