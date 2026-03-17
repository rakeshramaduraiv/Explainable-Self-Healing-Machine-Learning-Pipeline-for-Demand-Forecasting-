"""
Generate Dataset for Self-Healing Product Demand Forecasting
--------------------------------------------------------------
Single e-commerce store, multiple product categories.
  - 2024 (12 months) → Training
  - 2025 (12 months) → Testing
  - First prediction: 2026-01
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import os

# Product catalog for a single e-commerce store
PRODUCTS = {
    1:  {"name": "Wireless Earbuds",     "base": 320,  "season": "holiday"},
    2:  {"name": "Phone Case",           "base": 580,  "season": "flat"},
    3:  {"name": "USB-C Cable",          "base": 710,  "season": "flat"},
    4:  {"name": "Bluetooth Speaker",    "base": 180,  "season": "summer"},
    5:  {"name": "Laptop Stand",         "base": 95,   "season": "back_to_school"},
    6:  {"name": "Screen Protector",     "base": 640,  "season": "flat"},
    7:  {"name": "Power Bank",           "base": 260,  "season": "summer"},
    8:  {"name": "Webcam HD",            "base": 110,  "season": "back_to_school"},
    9:  {"name": "Mechanical Keyboard",  "base": 75,   "season": "holiday"},
    10: {"name": "Mouse Pad XL",         "base": 420,  "season": "flat"},
    11: {"name": "HDMI Adapter",         "base": 350,  "season": "flat"},
    12: {"name": "Desk Lamp LED",        "base": 130,  "season": "back_to_school"},
    13: {"name": "Smartwatch Band",      "base": 480,  "season": "holiday"},
    14: {"name": "Portable SSD",         "base": 60,   "season": "holiday"},
    15: {"name": "Noise Cancel Headset", "base": 45,   "season": "holiday"},
}

# Seasonal profiles
SEASON_PROFILES = {
    "flat":           {1:1.0, 2:1.0, 3:1.0, 4:1.0, 5:1.0, 6:1.0, 7:1.0, 8:1.0, 9:1.0, 10:1.0, 11:1.05, 12:1.10},
    "holiday":        {1:0.80,2:0.75,3:0.80,4:0.85,5:0.90,6:0.90,7:0.85,8:0.90,9:0.95,10:1.10,11:1.40,12:1.70},
    "summer":         {1:0.70,2:0.75,3:0.85,4:0.95,5:1.15,6:1.35,7:1.40,8:1.30,9:1.05,10:0.85,11:0.75,12:0.80},
    "back_to_school": {1:0.80,2:0.80,3:0.85,4:0.85,5:0.90,6:1.00,7:1.20,8:1.45,9:1.35,10:1.00,11:0.90,12:0.95},
}


def generate_sample_dataset(
    start_year=2024,
    num_years=2,
    num_products=15,
    output_path="data/uploaded_data.csv"
):
    np.random.seed(42)
    rows = []
    holiday_weeks = [6, 7, 21, 35, 47, 48, 51, 52]

    for year in range(start_year, start_year + num_years):
        start_date = datetime(year, 1, 1)
        first_friday = start_date + timedelta(days=(4 - start_date.weekday()) % 7)
        week_num = 0
        current_date = first_friday

        while current_date.year == year:
            week_num += 1
            month = current_date.month
            is_holiday = 1 if week_num in holiday_weeks else 0

            for pid in range(1, num_products + 1):
                p = PRODUCTS[pid]
                profile = SEASON_PROFILES[p["season"]]
                demand = p["base"] * profile[month]

                # Holiday boost
                if is_holiday:
                    demand *= 1.12 + np.random.uniform(0, 0.08)

                # Year-over-year growth ~5%
                demand *= 1 + (year - start_year) * 0.05

                # Weekly noise
                demand *= np.random.uniform(0.82, 1.18)

                # Occasional promo spike (3% chance)
                if np.random.random() < 0.03:
                    demand *= np.random.uniform(1.5, 2.2)

                # Economic indicators
                temp = {1:35,2:38,3:50,4:60,5:70,6:80,7:85,8:83,9:75,10:60,11:45,12:35}[month] + np.random.uniform(-8, 8)
                fuel = 3.20 + (year - start_year) * 0.12 + (month - 1) * 0.015 + np.random.uniform(-0.15, 0.15)
                cpi = 230 + (year - start_year) * 4 + (month - 1) * 0.25 + np.random.uniform(-1.5, 1.5)
                unemp = 5.2 + np.random.uniform(-1.2, 1.2)

                rows.append({
                    "Store": 1,
                    "Product": pid,
                    "Date": current_date.strftime("%d-%m-%Y"),
                    "Demand": max(1, round(demand)),
                    "Holiday_Flag": is_holiday,
                    "Temperature": round(temp, 1),
                    "Fuel_Price": round(fuel, 2),
                    "CPI": round(cpi, 1),
                    "Unemployment": round(unemp, 1),
                })

            current_date += timedelta(days=7)

    df = pd.DataFrame(rows)
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    df.to_csv(output_path, index=False)

    df["Date"] = pd.to_datetime(df["Date"], dayfirst=True)
    print("=" * 60)
    print("E-COMMERCE PRODUCT DEMAND DATASET")
    print("=" * 60)
    print(f"Output:   {output_path}")
    print(f"Rows:     {len(df)}")
    print(f"Products: {df['Product'].nunique()}")
    print(f"Dates:    {df['Date'].min().date()} to {df['Date'].max().date()}")
    for year in sorted(df["Date"].dt.year.unique()):
        ydf = df[df["Date"].dt.year == year]
        print(f"  {year}: {len(ydf)} rows, {ydf['Date'].dt.month.nunique()} months")
    print(f"Demand:   {df['Demand'].min():,} – {df['Demand'].max():,} units")
    print(f"Mean:     {df['Demand'].mean():,.0f} units/week/product")
    print("=" * 60)
    return df


def generate_monthly_actuals(month_str, num_products=15, output_path=None):
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
            p = PRODUCTS[pid]
            profile = SEASON_PROFILES[p["season"]]
            demand = p["base"] * profile[month] * np.random.uniform(0.82, 1.18)
            rows.append({
                "Store": 1,
                "Product": pid,
                "Date": current_date.strftime("%d-%m-%Y"),
                "Demand": max(1, round(demand)),
                "Holiday_Flag": 0,
                "Temperature": round(50 + month * 3 + np.random.uniform(-8, 8), 1),
                "Fuel_Price": round(3.50 + np.random.uniform(-0.15, 0.15), 2),
                "CPI": round(240 + np.random.uniform(-1.5, 1.5), 1),
                "Unemployment": round(5.2 + np.random.uniform(-1, 1), 1),
            })
        current_date += timedelta(days=7)

    df = pd.DataFrame(rows)
    df.to_csv(output_path, index=False)
    print(f"Generated {month_str} actuals: {len(df)} rows -> {output_path}")
    return df


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "month":
        month = sys.argv[2] if len(sys.argv) > 2 else "2026-01"
        generate_monthly_actuals(month)
    else:
        generate_sample_dataset()
