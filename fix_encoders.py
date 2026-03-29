"""
Run this once to generate encoders.pkl from existing raw_merged.parquet.
Usage: python fix_encoders.py
"""
import sys, os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

import pandas as pd
import joblib
from sklearn.preprocessing import LabelEncoder

PROCESSED_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "processed")
ENCODER_PATH  = os.path.join(PROCESSED_DIR, "encoders.pkl")
CAT_COLS      = ["item_id", "dept_id", "cat_id", "store_id", "state_id"]

raw_path = os.path.join(PROCESSED_DIR, "raw_merged.parquet")
print(f"Loading {raw_path} ...")
raw = pd.read_parquet(raw_path, columns=[c for c in CAT_COLS])

encoders = {}
for col in CAT_COLS:
    le = LabelEncoder()
    le.fit(raw[col].astype(str).unique())
    encoders[col] = le
    print(f"  {col}: {len(le.classes_)} classes")

joblib.dump(encoders, ENCODER_PATH)
print(f"\n✅ encoders.pkl saved → {ENCODER_PATH}")
