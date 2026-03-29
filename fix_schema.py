"""
Run: venv\Scripts\python.exe fix_schema.py
"""
import sys, os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

import joblib

MODEL_DIR   = os.path.join(os.path.dirname(os.path.abspath(__file__)), "models", "lightgbm")
SCHEMA_PATH = os.path.join(MODEL_DIR, "feature_schema.pkl")

model        = joblib.load(os.path.join(MODEL_DIR, "model.pkl"))
feature_cols = model.booster_.feature_name()

joblib.dump(feature_cols, SCHEMA_PATH)
print(f"✅ feature_schema.pkl synced from model → {len(feature_cols)} features")
print(sorted(feature_cols))
