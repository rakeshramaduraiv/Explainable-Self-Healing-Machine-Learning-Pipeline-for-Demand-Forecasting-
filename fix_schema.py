"""
Run: venv\Scripts\python.exe fix_schema.py
"""
import sys, os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

import joblib
import pandas as pd

PROCESSED_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "processed")
MODEL_DIR     = os.path.join(os.path.dirname(os.path.abspath(__file__)), "models", "lightgbm")
SCHEMA_PATH   = os.path.join(MODEL_DIR, "feature_schema.pkl")

DROP = {"id", "date", "sales", "item_id", "dept_id", "cat_id", "store_id", "state_id"}

feat = pd.read_parquet(os.path.join(PROCESSED_DIR, "features.parquet"))
feat_cols = [c for c in feat.columns if c not in DROP and feat[c].dtype != object]

joblib.dump(feat_cols, SCHEMA_PATH)
print(f"✅ feature_schema.pkl updated → {len(feat_cols)} features")
print(sorted(feat_cols))
