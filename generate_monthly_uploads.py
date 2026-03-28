"""
Generate 12 Monthly Synthetic Upload CSV Files
Based on M5 dataset analysis:
  - Categories : HOBBIES (mean=0.811), HOUSEHOLD (mean=1.053)
  - Zero sales : 68.9%
  - Day of week: Fri(0.886) Sat(1.111) Sun(1.058) highest
  - Monthly    : Jun(0.911) Aug(0.914) Oct(0.909) highest
  - SNAP days  : ~50-60 days per month in CA
  - Price range: HOBBIES_1(0.10-30.98) HOBBIES_2(0.05-9.97) HOUSEHOLD_1(0.88-29.97)
  - Start month: May 2016 (after training cutoff Apr 2016)
  - Format     : 14 columns + date + sales = 16 columns
"""

import pandas as pd
import numpy as np
import os

np.random.seed(42)

# ─────────────────────────────────────────────
# DATASET ANALYSIS RESULTS
# ─────────────────────────────────────────────

# Monthly seasonality multipliers (from analysis)
MONTH_MULTIPLIER = {
    1: 0.855, 2: 0.875, 3: 0.862, 4: 0.905,
    5: 0.850, 6: 0.911, 7: 0.898, 8: 0.914,
    9: 0.877, 10: 0.909, 11: 0.869, 12: 0.864
}

# Day of week multipliers (from analysis)
DOW_MULTIPLIER = {
    0: 0.846,  # Monday
    1: 0.771,  # Tuesday
    2: 0.751,  # Wednesday
    3: 0.752,  # Thursday
    4: 0.886,  # Friday
    5: 1.111,  # Saturday (highest)
    6: 1.058   # Sunday
}

# Category base demand (from analysis)
CAT_BASE = {
    "HOBBIES"   : 0.811,
    "HOUSEHOLD" : 1.053
}

# Price ranges by department (from analysis)
PRICE_RANGE = {
    "HOBBIES_1"   : (0.10, 30.98, 6.06),   # min, max, mean
    "HOBBIES_2"   : (0.05,  9.97, 2.76),
    "HOUSEHOLD_1" : (0.88, 29.97, 4.92)
}

# SNAP days per month in CA (from analysis)
SNAP_DAYS_PER_MONTH = {
    1: 50, 2: 60, 3: 60, 4: 60,
    5: 50, 6: 50, 7: 50, 8: 50,
    9: 50, 10: 50, 11: 50, 12: 50
}

# Events by month (from analysis)
EVENTS_BY_MONTH = {
    1:  ["None","None","None","SuperBowl","None"],
    2:  ["None","ValentinesDay","None","PresidentsDay","None"],
    3:  ["None","LentStart","StPatricksDay","None","None"],
    4:  ["None","None","Easter","None","None"],
    5:  ["None","MemorialDay","None","Mother's day","None"],
    6:  ["None","NBAFinalsStart","NBAFinalsEnd","None","None"],
    7:  ["None","IndependenceDay","None","None","None"],
    8:  ["None","None","None","None","None"],
    9:  ["None","LaborDay","None","None","None"],
    10: ["None","None","Halloween","None","None"],
    11: ["None","None","Veterans Day","Thanksgiving","None"],
    12: ["None","None","Christmas","NewYear","None"]
}

# Event boost multipliers
EVENT_BOOST = {
    "None"          : 1.0,
    "SuperBowl"     : 1.8,
    "ValentinesDay" : 1.3,
    "PresidentsDay" : 1.2,
    "LentStart"     : 1.1,
    "StPatricksDay" : 1.2,
    "Easter"        : 1.4,
    "MemorialDay"   : 1.3,
    "Mother's day"  : 1.3,
    "NBAFinalsStart": 1.2,
    "NBAFinalsEnd"  : 1.2,
    "IndependenceDay":1.5,
    "LaborDay"      : 1.3,
    "Halloween"     : 1.4,
    "Veterans Day"  : 1.2,
    "Thanksgiving"  : 2.0,
    "Christmas"     : 2.5,
    "NewYear"       : 1.5
}

# ─────────────────────────────────────────────
# LOAD EXISTING SKUs
# ─────────────────────────────────────────────
df       = pd.read_parquet("data/processed/features.parquet")
merged   = pd.read_parquet("data/processed/raw_merged.parquet")
all_ids  = df["id"].unique()  # use all SKUs for realistic drift detection
sku_means = df.groupby("id")["sales"].mean().to_dict()

# Walmart week number base (last known + increment)
BASE_WM_YR_WK = 11617  # May 2016

OUTPUT_DIR = "data/upload_months"
os.makedirs(OUTPUT_DIR, exist_ok=True)

MONTH_NAMES = {
    1:"January", 2:"February", 3:"March",    4:"April",
    5:"May",     6:"June",     7:"July",      8:"August",
    9:"September",10:"October",11:"November",12:"December"
}

# ─────────────────────────────────────────────
# GENERATE 12 MONTHLY FILES
# ─────────────────────────────────────────────
print("=" * 60)
print("DATASET ANALYSIS SUMMARY")
print("=" * 60)
print("Categories  : HOBBIES (mean=0.811), HOUSEHOLD (mean=1.053)")
print("Zero sales  : 68.9% of all days")
print("Max sales   : 294 units in a day")
print("Mean sales  : 0.882 units/day/SKU")
print("Peak days   : Saturday (1.111x), Sunday (1.058x), Friday (0.886x)")
print("Peak months : August (0.914x), June (0.911x), October (0.909x)")
print("SNAP days   : 50-60 days per month in California")
print("Price range : HOBBIES_1 $0.10-$30.98, HOUSEHOLD_1 $0.88-$29.97")
print()
print("Generating 12 monthly files for May 2016 - April 2017...")
print("=" * 60)

generated_files = []

for month_offset in range(12):
    # Calculate year and month
    base_month = 5  # start from May 2016
    base_year  = 2016
    total_month = base_month + month_offset
    year  = base_year + (total_month - 1) // 12
    month = ((total_month - 1) % 12) + 1

    month_name = MONTH_NAMES[month]
    filename   = f"{OUTPUT_DIR}/{month:02d}_{month_name}_{year}_upload.csv"

    # Date range for this month
    dates = pd.date_range(
        start=f"{year}-{month:02d}-01",
        end=pd.Period(f"{year}-{month:02d}").to_timestamp("D", how="end"),
        freq="D"
    )

    # Walmart week number — compute correctly from actual date
    wm_yr_wk = BASE_WM_YR_WK + (month_offset * 4) + (dates[0].isocalendar().week - pd.Timestamp(f"{base_year}-{base_month:02d}-01").isocalendar().week)

    # SNAP days for this month
    snap_days_count = SNAP_DAYS_PER_MONTH[month]
    snap_days = set(np.random.choice(
        range(1, len(dates) + 1),
        size=min(snap_days_count // 5, len(dates)),
        replace=False
    ))

    # Events for this month
    events = EVENTS_BY_MONTH[month]

    rows = []
    for sku_id in all_ids:
        parts    = sku_id.split("_")
        cat_id   = parts[0]
        dept_num = parts[1]
        item_num = parts[2]
        state    = parts[3]
        store_num= parts[4]

        item_id  = f"{cat_id}_{dept_num}_{item_num}"
        dept_id  = f"{cat_id}_{dept_num}"
        store_id = f"{state}_{store_num}"
        state_id = state

        # Base demand from historical mean
        base_demand = max(sku_means.get(sku_id, CAT_BASE.get(cat_id, 0.8)), 0.1)

        # Price for this SKU — use actual historical price if available
        hist_price = merged[merged["id"] == sku_id]["sell_price"].dropna()
        p_min, p_max, p_mean = PRICE_RANGE.get(dept_id, (1.0, 10.0, 5.0))
        if len(hist_price) > 0:
            p_mean = float(hist_price.iloc[-1])  # use last known price as base
        sell_price = round(np.clip(
            np.random.normal(p_mean, p_mean * 0.05),  # tighter variation
            p_min, p_max
        ), 2)

        for i, d in enumerate(dates):
            dow        = d.dayofweek
            day_num    = d.day

            # Get event for this week
            week_idx   = min((day_num - 1) // 7, len(events) - 1)
            event      = events[week_idx]
            event_boost= EVENT_BOOST.get(event, 1.0)

            # SNAP boost for FOODS (not applicable here but kept for structure)
            snap_ca    = 1 if day_num in snap_days else 0
            snap_boost = 1.2 if snap_ca == 1 and cat_id == "FOODS" else 1.0

            # Calculate demand
            lam = (
                base_demand
                * MONTH_MULTIPLIER[month]
                * DOW_MULTIPLIER[dow]
                * event_boost
                * snap_boost
            )

            # Poisson distribution (matches real retail sparse demand)
            sales = int(np.random.poisson(max(lam, 0.01)))

            rows.append({
                "item_id"   : item_id,
                "dept_id"   : dept_id,
                "cat_id"    : cat_id,
                "store_id"  : store_id,
                "state_id"  : state_id,
                "wm_yr_wk"  : wm_yr_wk,
                "snap_CA"   : snap_ca,
                "snap_TX"   : 0,
                "snap_WI"   : 0,
                "sell_price": sell_price,
                "dayofweek" : dow,
                "weekofyear": int(d.isocalendar().week),
                "month"     : month,
                "year"      : year,
                "date"      : d.strftime("%Y-%m-%d"),
                "sales"     : sales
            })

    month_df = pd.DataFrame(rows)
    month_df.to_csv(filename, index=False)
    generated_files.append((month_name, year, filename, len(month_df), month_df["sales"].mean()))

    print(f"  {month:02d}. {month_name} {year} | rows={len(month_df):,} | "
          f"days={len(dates)} | mean_sales={month_df['sales'].mean():.3f} | "
          f"saved: {filename.split('/')[-1]}")

# ─────────────────────────────────────────────
# FINAL SUMMARY
# ─────────────────────────────────────────────
print()
print("=" * 60)
print("ALL 12 FILES GENERATED")
print("=" * 60)
print(f"{'Month':<15} {'Year':<6} {'Rows':<8} {'Mean Sales':<12} {'File'}")
print("-" * 60)
for name, yr, fpath, rows, mean in generated_files:
    print(f"{name:<15} {yr:<6} {rows:<8,} {mean:<12.3f} {fpath.split('/')[-1]}")

print()
print("=" * 60)
print("COLUMN FORMAT IN EACH FILE (16 columns)")
print("=" * 60)
sample = pd.read_csv(generated_files[0][2])
print("Columns:", sample.columns.tolist())
print()
print("Sample rows:")
print(sample.head(5).to_string(index=False))
print()
print("=" * 60)
print("HOW TO USE")
print("=" * 60)
print("1. Open dashboard: streamlit run dashboards/app.py")
print("2. Select '14 Columns (full merged format)'")
print("3. Upload January file first")
print("4. Run drift check")
print("5. Retrain if needed")
print("6. Download next month prediction")
print("7. Repeat with February file next month")
print("=" * 60)
