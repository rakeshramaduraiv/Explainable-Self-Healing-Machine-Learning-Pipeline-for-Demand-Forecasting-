"""
Build Real Dataset from Two Kaggle Sources
--------------------------------------------
Combines:
  1. Walmart Store Sales Forecasting → economic features
     https://www.kaggle.com/competitions/walmart-recruiting-store-sales-forecasting
     File needed: walmart.csv (columns: Store, Date, Weekly_Sales, Holiday_Flag, Temperature, Fuel_Price, CPI, Unemployment)

  2. Store Item Demand Forecasting → product-level demand
     https://www.kaggle.com/competitions/demand-forecasting-kernels-only
     File needed: demand.csv (columns: date, store, item, sales)

Output: data/uploaded_data.csv with all 9 required columns

Usage:
  python build_real_dataset.py walmart.csv demand.csv
"""

import pandas as pd
import numpy as np
import os
import sys


def build_dataset(walmart_path, demand_path, num_products=15, output_path="data/uploaded_data.csv"):
    # ── Load Walmart (economic features) ──────────────────────────────────
    wm = pd.read_csv(walmart_path)
    wm.columns = wm.columns.str.strip()

    # Normalize column names
    col_map = {}
    for c in wm.columns:
        cl = c.lower()
        if cl == "date": col_map[c] = "Date"
        elif cl == "store": col_map[c] = "Store"
        elif cl in ("weekly_sales", "weeklysales"): col_map[c] = "Weekly_Sales"
        elif cl == "holiday_flag": col_map[c] = "Holiday_Flag"
        elif cl == "temperature": col_map[c] = "Temperature"
        elif cl == "fuel_price": col_map[c] = "Fuel_Price"
        elif cl == "cpi": col_map[c] = "CPI"
        elif cl == "unemployment": col_map[c] = "Unemployment"
    wm = wm.rename(columns=col_map)

    wm["Date"] = pd.to_datetime(wm["Date"], dayfirst=True, errors="coerce")
    if wm["Date"].isna().all():
        wm["Date"] = pd.to_datetime(wm.iloc[:, wm.columns.get_loc("Date")], format="%Y-%m-%d")

    # Pick Store 1 only (single-store platform)
    wm = wm[wm["Store"] == 1].copy()
    wm = wm.sort_values("Date").reset_index(drop=True)

    # Weekly economic features (one row per week)
    econ_cols = ["Date", "Holiday_Flag", "Temperature", "Fuel_Price", "CPI", "Unemployment"]
    available = [c for c in econ_cols if c in wm.columns]
    econ = wm[available].drop_duplicates(subset=["Date"]).sort_values("Date").reset_index(drop=True)

    print(f"Walmart: {len(wm)} rows, date range: {wm['Date'].min().date()} to {wm['Date'].max().date()}")
    print(f"Economic features: {len(econ)} weeks")

    # ── Load Demand (product-level sales) ─────────────────────────────────
    dm = pd.read_csv(demand_path)
    dm.columns = dm.columns.str.strip()

    col_map2 = {}
    for c in dm.columns:
        cl = c.lower()
        if cl == "date": col_map2[c] = "Date"
        elif cl == "store": col_map2[c] = "Store"
        elif cl == "item": col_map2[c] = "Product"
        elif cl == "sales": col_map2[c] = "Demand"
    dm = dm.rename(columns=col_map2)

    dm["Date"] = pd.to_datetime(dm["Date"], errors="coerce")

    # Pick Store 1, first N products
    dm = dm[dm["Store"] == 1].copy()
    top_products = sorted(dm["Product"].unique())[:num_products]
    dm = dm[dm["Product"].isin(top_products)].copy()

    # Remap product IDs to 1..N
    prod_map = {old: i + 1 for i, old in enumerate(top_products)}
    dm["Product"] = dm["Product"].map(prod_map)

    print(f"Demand: {len(dm)} rows, {dm['Product'].nunique()} products")
    print(f"Demand date range: {dm['Date'].min().date()} to {dm['Date'].max().date()}")

    # ── Align dates ───────────────────────────────────────────────────────
    # Demand dataset is daily → aggregate to weekly (Friday)
    dm["Week"] = dm["Date"].dt.to_period("W-FRI").apply(lambda p: p.end_time.date())
    dm["Week"] = pd.to_datetime(dm["Week"])

    weekly_demand = dm.groupby(["Week", "Product"])["Demand"].sum().reset_index()
    weekly_demand = weekly_demand.rename(columns={"Week": "Date"})

    # Find overlapping date range
    econ_dates = set(econ["Date"].dt.date)
    demand_dates = set(weekly_demand["Date"].dt.date)

    # If no overlap, shift demand dates to match walmart dates
    overlap = econ_dates & demand_dates
    if len(overlap) < 10:
        print(f"\nDate overlap: {len(overlap)} weeks — aligning demand dates to walmart range...")
        # Shift demand data to start at walmart's start date
        wm_start = econ["Date"].min()
        dm_start = weekly_demand["Date"].min()
        shift = wm_start - dm_start
        weekly_demand["Date"] = weekly_demand["Date"] + shift
        print(f"Shifted demand dates by {shift.days} days")

    # ── Merge ─────────────────────────────────────────────────────────────
    # Match each demand week to nearest economic week
    econ = econ.sort_values("Date")
    weekly_demand = weekly_demand.sort_values("Date")

    merged = pd.merge_asof(
        weekly_demand.sort_values("Date"),
        econ.sort_values("Date"),
        on="Date",
        direction="nearest",
        tolerance=pd.Timedelta(days=7),
    )

    # Drop rows where economic features couldn't be matched
    before = len(merged)
    merged = merged.dropna(subset=["Temperature", "Fuel_Price", "CPI", "Unemployment"])
    print(f"Merged: {before} → {len(merged)} rows (dropped {before - len(merged)} unmatched)")

    # ── Format for platform ───────────────────────────────────────────────
    merged["Store"] = 1
    merged["Holiday_Flag"] = merged["Holiday_Flag"].fillna(0).astype(int)
    merged["Demand"] = merged["Demand"].astype(int)
    merged["Product"] = merged["Product"].astype(int)

    # Keep exactly 2 years of data (for train/test split)
    merged = merged.sort_values("Date")
    years = sorted(merged["Date"].dt.year.unique())
    if len(years) >= 2:
        # Take last 2 full years
        use_years = years[-2:]
        merged = merged[merged["Date"].dt.year.isin(use_years)]
        print(f"Using years: {use_years[0]} (train) → {use_years[1]} (test)")
    else:
        # Split single year into two halves, relabel
        mid = len(merged) // 2
        merged.iloc[:mid, merged.columns.get_loc("Date")] = merged.iloc[:mid]["Date"] - pd.DateOffset(years=1)
        print("Only 1 year found — split into 2 years")

    # Format date as DD-MM-YYYY
    merged["Date"] = merged["Date"].dt.strftime("%d-%m-%Y")

    # Final column order
    out = merged[["Store", "Product", "Date", "Demand", "Holiday_Flag",
                   "Temperature", "Fuel_Price", "CPI", "Unemployment"]].copy()

    # Round floats
    for c in ["Temperature", "Fuel_Price", "CPI", "Unemployment"]:
        out[c] = out[c].round(2)

    out = out.sort_values(["Date", "Product"]).reset_index(drop=True)

    # Save
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    out.to_csv(output_path, index=False)

    # Summary
    out["_Date"] = pd.to_datetime(out["Date"], dayfirst=True)
    print("\n" + "=" * 60)
    print("COMBINED REAL DATASET")
    print("=" * 60)
    print(f"Output:   {output_path}")
    print(f"Rows:     {len(out)}")
    print(f"Products: {out['Product'].nunique()}")
    print(f"Dates:    {out['_Date'].min().date()} to {out['_Date'].max().date()}")
    for year in sorted(out["_Date"].dt.year.unique()):
        ydf = out[out["_Date"].dt.year == year]
        print(f"  {year}: {len(ydf)} rows, {ydf['_Date'].dt.month.nunique()} months")
    print(f"Demand:   {out['Demand'].min()} – {out['Demand'].max()} units")
    print(f"Mean:     {out['Demand'].mean():.0f} units/week/product")
    print("=" * 60)


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python build_real_dataset.py <walmart.csv> <demand.csv> [num_products]")
        print()
        print("Download:")
        print("  1. https://www.kaggle.com/competitions/walmart-recruiting-store-sales-forecasting")
        print("     → train.csv + features.csv (merge them, or use the combined walmart.csv)")
        print()
        print("  2. https://www.kaggle.com/competitions/demand-forecasting-kernels-only")
        print("     → train.csv (rename to demand.csv)")
        print()
        print("Example:")
        print("  python build_real_dataset.py walmart.csv demand.csv 15")
        sys.exit(1)

    walmart_path = sys.argv[1]
    demand_path = sys.argv[2]
    num_products = int(sys.argv[3]) if len(sys.argv) > 3 else 15

    build_dataset(walmart_path, demand_path, num_products)
