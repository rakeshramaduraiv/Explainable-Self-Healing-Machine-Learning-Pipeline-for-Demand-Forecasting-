"""
Run: venv\Scripts\python.exe debug_features.py
"""
import sys, os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

import joblib
import pandas as pd

MODEL_DIR     = os.path.join(os.path.dirname(os.path.abspath(__file__)), "models", "lightgbm")
PROCESSED_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "processed")

model = joblib.load(os.path.join(MODEL_DIR, "model.pkl"))
model_features = model.booster_.feature_name()
print(f"Model expects {len(model_features)} features:")
print(sorted(model_features))
print()

feat = pd.read_parquet(os.path.join(PROCESSED_DIR, "actual_month_features.parquet"))
_DROP = {"id","date","sales","item_id","dept_id","cat_id","store_id","state_id"}
data_features = [c for c in feat.columns if c not in _DROP and feat[c].dtype != object]
print(f"actual_month_features.parquet has {len(data_features)} features:")
print(sorted(data_features))
print()

print("MISSING from new data:", sorted(set(model_features) - set(data_features)))
print("EXTRA in new data:    ", sorted(set(data_features) - set(model_features)))
