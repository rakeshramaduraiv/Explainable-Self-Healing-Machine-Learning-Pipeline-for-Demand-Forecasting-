"""
Walmart Dataset → Product Demand Forecasting
----------------------------------------------
Uses ONLY the Walmart Store Sales dataset (1 source, 8 real columns).
Splits store-level Weekly_Sales into 15 product categories.

Dataset: https://www.kaggle.com/datasets/yasserh/walmart-dataset
Download: Walmart.csv

Columns in Walmart.csv:
  Store, Date, Weekly_Sales, Holiday_Flag, Temperature, Fuel_Price, CPI, Unemployment

What this script does:
  1. Takes Store 1 data (real economic features)
  2. Splits Weekly_Sales into 15 product categories with realistic proportions
  3. Converts dollar sales → unit demand
  4. Outputs exact format for the platform

Usage:
  python walmart_adapter.py Walmart.csv
"""

import pandas as pd
import numpy as np
import os
import sys

# 15 product categories with sales share % and avg unit price
PRODUCTS = {
    1:  {"name": "Wireless Earbuds",     "share": 0.12, "unit_price": 45},
    2:  {"name": "Phone Case",           "share": 0.09, "unit_price": 15},
    3:  {"name": "USB-C Cable",          "share": 0.10, "unit_price": 12},
    4:  {"name": "Bluetooth Speaker",    "share": 0.07, "unit_price": 60},
    5:  {"name": "Laptop Stand",         "share": 0.04, "unit_price": 35},
    6:  {"name": "Screen Protector",     "share": 0.08, "unit_price": 10},
    7:  {"name": "Power Bank",           "share": 0.06, "unit_price": 30},
    8:  {"name": "Webcam HD",            "share": 0.05, "unit_price": 50},
    9:  {"name": "Mechanical Keyboard",  "share": 0.04, "unit_price": 75},
    10: {"name": "Mouse Pad XL",         "share": 0.08, "unit_price": 18},
    11: {"name": "HDMI Adapter",         "share": 0.06, "unit_price": 15},
    12: {"name": "Desk Lamp LED",        "share": 0.05, "unit_price": 25},
    13: {"name": "Smartwatch Band",      "share": 0.07, "unit_price": 20},
    14: {"name": "Portable SSD",         "share": 0.05, "unit_price": 80},
    15: {"name": "Noise Cancel Headset", "share": 0.04, "unit_price": 120},
}


def build_dataset(walmart_path, output_path="data/uploaded_data.csv"):
    np.random.seed(42)

    # ── Load Walmart CSV ──────────────────────────────────────────────────
    df = pd.read_csv(walmart_path)
    df.columns = df.columns.str.strip()

    # Normalize columns
    rename = {}
    for c in df.columns:
        cl = c.lower().replace(" ", "_")
        if cl == "date": rename[c] = "Date"
        elif cl == "store": rename[c] = "Store"
        elif cl in ("weekly_sales", "weeklysales"): rename[c] = "Weekly_Sales"
        elif cl == "holiday_flag": rename[c] = "Holiday_Flag"
        elif cl == "temperature": rename[c] = "Temperature"
        elif cl == "fuel_price": rename[c] = "Fuel_Price"
        elif cl == "cpi": rename[c] = "CPI"
        elif cl == "unemployment": rename[c] = "Unemployment"
    df = df.rename(columns=rename)

    print(f"Loaded: {len(df)} rows, columns: {list(df.columns)}")

    # Parse dates
    df["Date"] = pd.to_datetime(df["Date"], dayfirst=True, errors="coerce")
    if df["Date"].isna().sum() > len(df) * 0.5:
        df["Date"] = pd.to_datetime(df[rename.get("Date", "Date")], format="%Y-%m-%d", errors="coerce")

    # Use Store 1 only
    df = df[df["Store"] == 1].copy()
    df = df.sort_values("Date").reset_index(drop=True)

    print(f"Store 1: {len(df)} weeks")
    print(f"Date range: {df['Date'].min().date()} to {df['Date'].max().date()}")
    print(f"Weekly Sales: ${df['Weekly_Sales'].min():,.0f} – ${df['Weekly_Sales'].max():,.0f}")

    # ── Keep exactly 2 years ──────────────────────────────────────────────
    years = sorted(df["Date"].dt.year.unique())
    if len(years) >= 2:
        use_years = years[-2:]
        df = df[df["Date"].dt.year.isin(use_years)].copy()
        print(f"Using years: {use_years[0]} (train) → {use_years[1]} (test)")
    else:
        print(f"WARNING: Only {len(years)} year(s) found. Need 2 years for train/test split.")

    # ── Split Weekly_Sales into 15 products ───────────────────────────────
    rows = []
    for _, week in df.iterrows():
        total_sales = week["Weekly_Sales"]

        for pid, info in PRODUCTS.items():
            # Product's share of total sales + noise
            product_sales = total_sales * info["share"] * np.random.uniform(0.85, 1.15)

            # Convert dollars → units
            demand = max(1, round(product_sales / info["unit_price"]))

            rows.append({
                "Store": 1,
                "Product": pid,
                "Date": week["Date"].strftime("%d-%m-%Y"),
                "Demand": demand,
                "Holiday_Flag": int(week.get("Holiday_Flag", 0)),
                "Temperature": round(week.get("Temperature", 60.0), 1),
                "Fuel_Price": round(week.get("Fuel_Price", 3.5), 2),
                "CPI": round(week.get("CPI", 230.0), 1),
                "Unemployment": round(week.get("Unemployment", 5.0), 1),
            })

    out = pd.DataFrame(rows)
    out = out.sort_values(["Date", "Product"]).reset_index(drop=True)

    # ── Save ──────────────────────────────────────────────────────────────
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    out.to_csv(output_path, index=False)

    # ── Summary ───────────────────────────────────────────────────────────
    out["_Date"] = pd.to_datetime(out["Date"], dayfirst=True)
    print("\n" + "=" * 60)
    print("WALMART → PRODUCT DEMAND DATASET")
    print("=" * 60)
    print(f"Source:   Walmart Store Sales (Kaggle)")
    print(f"Output:   {output_path}")
    print(f"Rows:     {len(out)}")
    print(f"Products: {out['Product'].nunique()}")
    print(f"Dates:    {out['_Date'].min().date()} to {out['_Date'].max().date()}")
    for year in sorted(out["_Date"].dt.year.unique()):
        ydf = out[out["_Date"].dt.year == year]
        print(f"  {year}: {len(ydf)} rows, {ydf['_Date'].dt.month.nunique()} months")
    print(f"Demand:   {out['Demand'].min()} – {out['Demand'].max()} units")
    print(f"Mean:     {out['Demand'].mean():.0f} units/week/product")
    print()
    print("Real columns from Walmart: Date, Holiday_Flag, Temperature, Fuel_Price, CPI, Unemployment")
    print("Derived from Weekly_Sales: Product (split), Demand (units)")
    print("=" * 60)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python walmart_adapter.py Walmart.csv")
        print()
        print("Download from: https://www.kaggle.com/datasets/yasserh/walmart-dataset")
        print("File needed:   Walmart.csv")
        sys.exit(1)

    build_dataset(sys.argv[1])
