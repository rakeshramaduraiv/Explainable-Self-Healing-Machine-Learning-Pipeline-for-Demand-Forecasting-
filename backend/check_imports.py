import sys
try:
    import fastapi
    import pandas as pd
    import numpy as np
    import joblib
    import xgboost
    import scipy
    from sklearn.ensemble import RandomForestRegressor
    print("SUCCESS: All core libraries imported.")
except ImportError as e:
    print(f"FAILURE: {e}")
    sys.exit(1)
