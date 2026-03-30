"""
generate_monthly_uploads.py
Model trains on: 2015 Jan - 2018 Dec (all of train.csv)
Model predicts:  2019 Jan first
User uploads:    2019 Jan - 2019 Dec (12 files, one per month)

Since train.csv only has 2015-2018, we generate 2019 data
by taking 2018 patterns and shifting dates forward by 1 year
with slight realistic variation. This simulates what "actual 2019 data"
would look like for the user to upload month by month.
"""
import pandas as pd
import numpy as np
import os

ROOT = os.path.dirname(os.path.abspath(__file__))
DATA_PATH = os.path.join(ROOT, "data", "raw", "train.csv")
UPLOAD_DIR = os.path.join(ROOT, "data", "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)

# Clear old uploads
for f in os.listdir(UPLOAD_DIR):
    os.remove(os.path.join(UPLOAD_DIR, f))

print("Loading train.csv...")
df = pd.read_csv(DATA_PATH, parse_dates=["Order Date"], dayfirst=True)
print(f"Dataset: {df['Order Date'].min().date()} to {df['Order Date'].max().date()} ({len(df)} rows)")
print()

# Take 2018 data as base pattern for 2019
df_2018 = df[df["Order Date"].dt.year == 2018].copy()
print(f"2018 base data: {len(df_2018)} rows")
print()

# Shift 2018 dates to 2019 with slight variation
np.random.seed(42)
df_2019 = df_2018.copy()
df_2019["Order Date"] = df_2019["Order Date"] + pd.DateOffset(years=1)
df_2019["Ship Date"] = pd.to_datetime(df_2019["Ship Date"], dayfirst=True) + pd.DateOffset(years=1)

# Add realistic variation: +/- 15% on sales
df_2019["Sales"] = df_2019["Sales"] * (1 + np.random.uniform(-0.15, 0.15, len(df_2019)))
df_2019["Sales"] = df_2019["Sales"].round(2).clip(lower=0.5)

# Update Row IDs
df_2019["Row ID"] = range(len(df) + 1, len(df) + 1 + len(df_2019))

# Update Order IDs to 2019
df_2019["Order ID"] = df_2019["Order ID"].str.replace("2018", "2019")

print("Generating 12 monthly files for 2019...")
print("(User uploads these one by one after each prediction)")
print()

total_files = 0
for month_num in range(1, 13):
    month_data = df_2019[df_2019["Order Date"].dt.month == month_num]
    if len(month_data) == 0:
        continue

    month_name = month_data["Order Date"].dt.strftime("%Y-%m").iloc[0]
    filename = f"month_{month_num:02d}_{month_name}.csv"
    filepath = os.path.join(UPLOAD_DIR, filename)

    month_data.to_csv(filepath, index=False, date_format="%d/%m/%Y")
    total_files += 1
    sales = month_data["Sales"].sum()
    orders = month_data["Order ID"].nunique()
    print(f"  {filename}: {len(month_data)} rows, {orders} orders, ${sales:,.0f} sales")

print(f"\nDone! {total_files} files in {UPLOAD_DIR}")
print()
print("Pipeline flow:")
print("  Model trained on : 2015-01 to 2018-12 (train.csv)")
print("  Model predicts   : 2019-01 (January 2019)")
print("  User uploads     : month_01_2019-01.csv (actual Jan 2019)")
print("  System evaluates : predicted vs actual")
print("  System predicts  : 2019-02 (February 2019)")
print("  User uploads     : month_02_2019-02.csv (actual Feb 2019)")
print("  ... continues for all 12 months ...")
