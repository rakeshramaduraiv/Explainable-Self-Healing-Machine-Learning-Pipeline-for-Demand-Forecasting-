"""
Synthetic Data Generator
Generates both 3-column and 14-column upload formats
"""
import pandas as pd
import numpy as np

MONTH       = "2016-05"
NUM_SKUS    = 20
SEED        = 42
np.random.seed(SEED)

# ─────────────────────────────────────────────
# Load existing data for reference
# ─────────────────────────────────────────────
df        = pd.read_parquet("data/processed/features.parquet")
merged    = pd.read_parquet("data/processed/raw_merged.parquet")
all_ids   = df["id"].unique()[:NUM_SKUS]
sku_means = df.groupby("id")["sales"].mean().to_dict()

dates = pd.date_range(
    start=f"{MONTH}-01",
    end=pd.Period(MONTH).to_timestamp("D", how="end"),
    freq="D"
)

# ─────────────────────────────────────────────
# SNAP lookup from calendar
# ─────────────────────────────────────────────
snap_lookup = merged[["date","wm_yr_wk","snap_CA","snap_TX","snap_WI"]].drop_duplicates("date").set_index("date")
price_lookup = merged[["item_id","store_id","wm_yr_wk","sell_price"]].dropna()

# ─────────────────────────────────────────────
# FORMAT 1 — 3 Column Upload
# ─────────────────────────────────────────────
rows_3 = []
for sku_id in all_ids:
    base = max(sku_means.get(sku_id, 0.5), 0.1)
    for d in dates:
        lam   = base * (1.3 if d.dayofweek >= 5 else 1.0)
        rows_3.append({
            "id"   : sku_id,
            "date" : d.strftime("%Y-%m-%d"),
            "sales": int(np.random.poisson(lam))
        })

df_3col = pd.DataFrame(rows_3)
df_3col.to_csv("data/processed/upload_3col.csv", index=False)

# ─────────────────────────────────────────────
# FORMAT 2 — 14 Column Upload
# ─────────────────────────────────────────────
rows_14 = []
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

    base = max(sku_means.get(sku_id, 0.5), 0.1)

    for d in dates:
        lam   = base * (1.3 if d.dayofweek >= 5 else 1.0)
        sales = int(np.random.poisson(lam))

        # Get SNAP and wm_yr_wk from lookup
        snap_row = snap_lookup.loc[snap_lookup.index == d]
        snap_CA  = int(snap_row["snap_CA"].values[0]) if len(snap_row) > 0 else 0
        snap_TX  = int(snap_row["snap_TX"].values[0]) if len(snap_row) > 0 else 0
        snap_WI  = int(snap_row["snap_WI"].values[0]) if len(snap_row) > 0 else 0
        wm_yr_wk = int(snap_row["wm_yr_wk"].values[0]) if len(snap_row) > 0 else 99999

        # Get sell_price from lookup
        price_row = price_lookup[
            (price_lookup["item_id"]  == item_id) &
            (price_lookup["store_id"] == store_id) &
            (price_lookup["wm_yr_wk"] == wm_yr_wk)
        ]
        sell_price = round(float(price_row["sell_price"].values[0]), 2) if len(price_row) > 0 else 0.0

        rows_14.append({
            "item_id"   : item_id,
            "dept_id"   : dept_id,
            "cat_id"    : cat_id,
            "store_id"  : store_id,
            "state_id"  : state_id,
            "wm_yr_wk"  : wm_yr_wk,
            "snap_CA"   : snap_CA,
            "snap_TX"   : snap_TX,
            "snap_WI"   : snap_WI,
            "sell_price": sell_price,
            "dayofweek" : d.dayofweek,
            "weekofyear": d.isocalendar().week,
            "month"     : d.month,
            "year"      : d.year,
            "date"      : d.strftime("%Y-%m-%d"),
            "sales"     : sales
        })

df_14col = pd.DataFrame(rows_14)
df_14col.to_csv("data/processed/upload_14col.csv", index=False)

# ─────────────────────────────────────────────
# Print Summary
# ─────────────────────────────────────────────
sep = "=" * 60

print(sep)
print("FORMAT 1 — 3 COLUMN UPLOAD (upload_3col.csv)")
print(sep)
print("Columns :", df_3col.columns.tolist())
print("Shape   :", df_3col.shape)
print()
print(df_3col.head(5).to_string(index=False))

print()
print(sep)
print("FORMAT 2 — 14 COLUMN UPLOAD (upload_14col.csv)")
print(sep)
print("Columns :", df_14col.columns.tolist())
print("Shape   :", df_14col.shape)
print()
print(df_14col.head(5).to_string(index=False))

print()
print(sep)
print("COLUMN RULES FOR 14-COLUMN FORMAT")
print(sep)
rules = [
    ("item_id",    "string",  "HOBBIES_1_001",  "CAT_DEPT_ITEMNUM"),
    ("dept_id",    "string",  "HOBBIES_1",      "CAT_DEPTNUM"),
    ("cat_id",     "string",  "HOBBIES",        "HOBBIES / FOODS / HOUSEHOLD"),
    ("store_id",   "string",  "CA_1",           "CA_1..CA_4, TX_1..TX_3, WI_1..WI_3"),
    ("state_id",   "string",  "CA",             "CA / TX / WI"),
    ("wm_yr_wk",   "integer", "11617",          "Walmart week number"),
    ("snap_CA",    "integer", "0 or 1",         "1 = SNAP benefit day in California"),
    ("snap_TX",    "integer", "0 or 1",         "1 = SNAP benefit day in Texas"),
    ("snap_WI",    "integer", "0 or 1",         "1 = SNAP benefit day in Wisconsin"),
    ("sell_price", "float",   "4.38",           "positive decimal"),
    ("dayofweek",  "integer", "0-6",            "0=Mon 1=Tue 2=Wed 3=Thu 4=Fri 5=Sat 6=Sun"),
    ("weekofyear", "integer", "1-52",           "week number in year"),
    ("month",      "integer", "1-12",           "1=Jan to 12=Dec"),
    ("year",       "integer", "2016",           "4 digit year"),
    ("date",       "string",  "2016-05-01",     "YYYY-MM-DD format"),
    ("sales",      "integer", "0,1,2,3...",     "actual units sold, >= 0"),
]
print(f"{'Column':<12} {'Type':<10} {'Example':<15} {'Rule'}")
print("-" * 60)
for col, typ, ex, rule in rules:
    print(f"{col:<12} {typ:<10} {ex:<15} {rule}")

print()
print(sep)
print("FILES SAVED")
print(sep)
print("3-column  : data/processed/upload_3col.csv")
print("14-column : data/processed/upload_14col.csv")
print(sep)
