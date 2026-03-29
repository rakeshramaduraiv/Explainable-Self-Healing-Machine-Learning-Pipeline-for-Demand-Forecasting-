"""
Run: venv\Scripts\python.exe debug_schema.py
"""
import sys, os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

import joblib
import pandas as pd

PROCESSED_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "processed")
MODEL_DIR     = os.path.join(os.path.dirname(os.path.abspath(__file__)), "models", "lightgbm")
SCHEMA_PATH   = os.path.join(MODEL_DIR, "feature_schema.pkl")

# Load saved schema
schema_cols = joblib.load(SCHEMA_PATH)
print(f"Schema has {len(schema_cols)} features:")
print(sorted(schema_cols))
print()

# Load features.parquet and check what cols it has
feat = pd.read_parquet(os.path.join(PROCESSED_DIR, "features.parquet"))
drop = {"id", "date", "sales", "item_id", "dept_id", "cat_id", "store_id", "state_id"}
feat_cols = [c for c in feat.columns if c not in drop and feat[c].dtype != object]
print(f"features.parquet has {len(feat_cols)} non-drop numeric cols:")
print(sorted(feat_cols))
print()

# Diff
schema_set = set(schema_cols)
feat_set   = set(feat_cols)
print("In schema but NOT in features.parquet:", schema_set - feat_set)
print("In features.parquet but NOT in schema:", feat_set - schema_set)
