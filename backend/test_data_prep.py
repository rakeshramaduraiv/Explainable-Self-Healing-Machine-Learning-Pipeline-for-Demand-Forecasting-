"""
Prepare monthly test CSV files from the dataset for platform verification.
Splits test months (post-training) into individual files for sequential upload testing.
"""
import os
import pandas as pd
from datetime import datetime

DATA_CSV   = "data/uploaded_data.csv"
OUTPUT_DIR = "test_data"

os.makedirs(OUTPUT_DIR, exist_ok=True)

df = pd.read_csv(DATA_CSV)
df["Date"] = pd.to_datetime(df["Date"], dayfirst=True)

cutoff = df["Date"].min() + pd.DateOffset(months=12)
test_df = df[df["Date"] >= cutoff].copy()

months = sorted(test_df["Date"].dt.to_period("M").unique())
print(f"Training cutoff : {cutoff.date()}")
print(f"Test months     : {len(months)}")
print("-" * 40)

for period in months:
    month_df = test_df[test_df["Date"].dt.to_period("M") == period].copy()
    fname = f"{str(period).replace('-', '_')}.csv"
    path  = os.path.join(OUTPUT_DIR, fname)
    month_df.to_csv(path, index=False)
    print(f"  Created: {fname}  ({len(month_df)} rows, {month_df['Store'].nunique()} stores)")

print(f"\n✅ {len(months)} monthly files saved to '{OUTPUT_DIR}/'")
print("\nUpload order for rolling-window test (sequential):")
for i, p in enumerate(months, 1):
    print(f"  {i:2d}. {str(p).replace('-', '_')}.csv")
