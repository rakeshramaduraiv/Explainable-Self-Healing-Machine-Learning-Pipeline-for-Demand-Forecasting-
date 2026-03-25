import pandas as pd
import numpy as np
import joblib
import os
from sklearn.preprocessing import LabelEncoder
from logger import get_logger

log = get_logger(__name__)


class FeatureEngineer:
    def __init__(self):
        self.feature_names = []
        self.encoders = {}
        self._group_cols = []       # columns used for groupby (Store+Product or just one)
        self._numeric_cols = []     # user-provided numeric columns
        self._categorical_cols = [] # user-provided categorical columns
        self._store_stats_full = None
        self._product_stats_full = None

    def save_state(self, path="models/feature_engineer.pkl"):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        state = {
            "encoders": self.encoders,
            "feature_names": self.feature_names,
            "_store_stats_full": self._store_stats_full,
            "_product_stats_full": self._product_stats_full,
            "_group_cols": self._group_cols,
            "_numeric_cols": self._numeric_cols,
            "_categorical_cols": self._categorical_cols,
        }
        joblib.dump(state, path)

    def load_state(self, path="models/feature_engineer.pkl"):
        if os.path.exists(path):
            state = joblib.load(path)
            self.encoders = state.get("encoders", {})
            self.feature_names = state.get("feature_names", [])
            self._store_stats_full = state.get("_store_stats_full")
            self._product_stats_full = state.get("_product_stats_full")
            self._group_cols = state.get("_group_cols", [])
            self._numeric_cols = state.get("_numeric_cols", [])
            self._categorical_cols = state.get("_categorical_cols", [])
            return True
        return False

    # ── Auto-detect columns ───────────────────────────────────────────────
    def _detect_columns(self, df):
        """Detect group columns and user-provided feature columns."""
        cols = set(df.columns)
        self._group_cols = []
        if "Store" in cols:
            self._group_cols.append("Store")
        if "Product" in cols:
            self._group_cols.append("Product")

        skip = {"Date", "Demand", "Store", "Product", "YearMonth"}
        self._numeric_cols = []
        self._categorical_cols = []
        for col in df.columns:
            if col in skip:
                continue
            if df[col].dtype in ["float64", "float32", "int64", "int32"]:
                self._numeric_cols.append(col)
            elif df[col].dtype == "object" and df[col].nunique() < 50:
                self._categorical_cols.append(col)

        log.info(f"Group cols: {self._group_cols}")
        log.info(f"Numeric user cols: {self._numeric_cols}")
        log.info(f"Categorical user cols: {self._categorical_cols}")

    # ── Temporal features (always created) - FULL FEATURES ────────────────────────────────────
    def create_temporal_features(self, df):
        df = df.copy()
        df["Month"]     = df["Date"].dt.month
        df["Quarter"]   = df["Date"].dt.quarter
        df["Year"]      = df["Date"].dt.year
        df["DayOfYear"] = df["Date"].dt.dayofyear
        df["WeekOfYear"] = df["Date"].dt.isocalendar().week
        df["Is_Q1"]     = (df["Quarter"] == 1).astype(int)
        df["Is_Q2"]     = (df["Quarter"] == 2).astype(int)
        df["Is_Q3"]     = (df["Quarter"] == 3).astype(int)
        df["Is_Q4"]     = (df["Quarter"] == 4).astype(int)
        
        # Full cyclical encoding
        df["Month_Sin"] = np.sin(2 * np.pi * df["Month"] / 12)
        df["Month_Cos"] = np.cos(2 * np.pi * df["Month"] / 12)
        df["Quarter_Sin"] = np.sin(2 * np.pi * df["Quarter"] / 4)
        df["Quarter_Cos"] = np.cos(2 * np.pi * df["Quarter"] / 4)
        df["Week_Sin"] = np.sin(2 * np.pi * df["WeekOfYear"] / 52)
        df["Week_Cos"] = np.cos(2 * np.pi * df["WeekOfYear"] / 52)
        
        # Comprehensive holiday and seasonal flags
        df["Near_Holiday"] = df["Month"].isin([11, 12]).astype(int)
        df["Is_Summer"] = df["Month"].isin([6, 7, 8]).astype(int)
        df["Is_Winter"] = df["Month"].isin([12, 1, 2]).astype(int)
        
        return df

    # ── Lag features (sliding window) - FULL FEATURES ─────────────────────────────────────
    def create_lag_features(self, df):
        group = self._group_cols if self._group_cols else None
        df = df.sort_values((self._group_cols or []) + ["Date"]).copy()

        # Comprehensive lag features
        for lag in [1, 2, 3, 4, 6, 8, 12]:  # Full range of lags
            col = f"Lag_{lag}"
            if group:
                df[col] = df.groupby(group)["Demand"].shift(lag)
                df[col] = df.groupby(group)[col].transform(lambda x: x.fillna(x.mean()).fillna(0))
            else:
                df[col] = df["Demand"].shift(lag)
                df[col] = df[col].fillna(df[col].mean()).fillna(0)

        return df

    # ── Rolling features (sliding window) - FULL FEATURES ─────────────────────────────────────
    def create_rolling_features(self, df):
        group = self._group_cols if self._group_cols else None
        df = df.sort_values((self._group_cols or []) + ["Date"]).copy()

        # Comprehensive rolling windows
        for w in [3, 4, 6, 8, 12]:  # Multiple window sizes
            if group:
                s = df.groupby(group)["Demand"].transform
                df[f"Rolling_Mean_{w}"] = s(lambda x: x.shift(1).rolling(w, min_periods=1).mean())
                df[f"Rolling_Std_{w}"] = s(lambda x: x.shift(1).rolling(w, min_periods=1).std().fillna(0))
                df[f"Rolling_Max_{w}"] = s(lambda x: x.shift(1).rolling(w, min_periods=1).max())
                df[f"Rolling_Min_{w}"] = s(lambda x: x.shift(1).rolling(w, min_periods=1).min())
            else:
                shifted = df["Demand"].shift(1)
                df[f"Rolling_Mean_{w}"] = shifted.rolling(w, min_periods=1).mean()
                df[f"Rolling_Std_{w}"] = shifted.rolling(w, min_periods=1).std().fillna(0)
                df[f"Rolling_Max_{w}"] = shifted.rolling(w, min_periods=1).max()
                df[f"Rolling_Min_{w}"] = shifted.rolling(w, min_periods=1).min()

        # Advanced momentum and volatility features
        df["Momentum_3"] = df["Lag_1"] / (df["Rolling_Mean_3"] + 1)
        df["Momentum_6"] = df["Lag_1"] / (df["Rolling_Mean_6"] + 1)
        df["Volatility_4"] = df["Rolling_Std_4"] / (df["Rolling_Mean_4"] + 1)
        df["Volatility_8"] = df["Rolling_Std_8"] / (df["Rolling_Mean_8"] + 1)
        return df

    # ── Store features (only if Store column exists) - OPTIMIZED ──────────────────────────
    def create_store_features(self, df, fit=True):
        if "Store" not in df.columns:
            return df
        
        # Ensure Store column is string type for consistent merging
        df["Store"] = df["Store"].astype(str)
        
        if fit:
            store_stats = df.groupby("Store")["Demand"].agg(
                Store_Mean="mean", Store_Std="std"
            ).reset_index()
            store_stats["Store_Std"] = store_stats["Store_Std"].fillna(0)
            # Ensure Store column in stats is also string
            store_stats["Store"] = store_stats["Store"].astype(str)
            self._store_stats_full = store_stats
        else:
            store_stats = self._store_stats_full if self._store_stats_full is not None else \
                df.groupby("Store")["Demand"].agg(
                    Store_Mean="mean", Store_Std="std"
                ).reset_index()
            store_stats["Store_Std"] = store_stats["Store_Std"].fillna(0)
            # Ensure Store column in stats is also string
            store_stats["Store"] = store_stats["Store"].astype(str)
        
        df = df.merge(store_stats, on="Store", how="left")
        df["Demand_vs_Store_Mean"] = df["Demand"] / (df["Store_Mean"] + 1)
        df["Store_CV"] = df["Store_Std"] / (df["Store_Mean"] + 1)
        return df

    # ── Product features (only if Product column exists) - OPTIMIZED ──────────────────────
    def create_product_features(self, df, fit=True):
        if "Product" not in df.columns:
            return df
        
        # Ensure Product column is string type for consistent merging
        df["Product"] = df["Product"].astype(str)
        
        if fit:
            product_stats = df.groupby("Product")["Demand"].agg(
                Product_Mean="mean", Product_Std="std"
            ).reset_index()
            product_stats["Product_Std"] = product_stats["Product_Std"].fillna(0)
            # Ensure Product column in stats is also string
            product_stats["Product"] = product_stats["Product"].astype(str)
            self._product_stats_full = product_stats
        else:
            product_stats = self._product_stats_full if self._product_stats_full is not None else \
                df.groupby("Product")["Demand"].agg(
                    Product_Mean="mean", Product_Std="std"
                ).reset_index()
            product_stats["Product_Std"] = product_stats["Product_Std"].fillna(0)
            # Ensure Product column in stats is also string
            product_stats["Product"] = product_stats["Product"].astype(str)
        
        df = df.merge(product_stats, on="Product", how="left")
        df["Demand_vs_Product_Mean"] = df["Demand"] / (df["Product_Mean"] + 1)
        df["Product_CV"] = df["Product_Std"] / (df["Product_Mean"] + 1)
        return df

    # ── Interaction features (dynamic — only uses columns that exist) - FULL FEATURES ─────
    def create_interaction_features(self, df):
        # Full interaction features for maximum model performance
        interactions = []
        
        # Numeric column interactions
        for i, col1 in enumerate(self._numeric_cols):
            for col2 in self._numeric_cols[i+1:]:
                if col1 != col2:
                    interaction_name = f"{col1}_x_{col2}"
                    df[interaction_name] = df[col1] * df[col2]
                    interactions.append(interaction_name)
        
        # Lag interactions with user features
        lag_cols = [c for c in df.columns if c.startswith("Lag_")]
        for lag_col in lag_cols[:3]:  # Top 3 lag features
            for num_col in self._numeric_cols[:2]:  # Top 2 numeric features
                interaction_name = f"{lag_col}_x_{num_col}"
                df[interaction_name] = df[lag_col] * df[num_col]
                interactions.append(interaction_name)
        
        # Rolling feature interactions
        rolling_cols = [c for c in df.columns if c.startswith("Rolling_Mean_")]
        for roll_col in rolling_cols[:2]:  # Top 2 rolling features
            for num_col in self._numeric_cols[:2]:  # Top 2 numeric features
                interaction_name = f"{roll_col}_x_{num_col}"
                df[interaction_name] = df[roll_col] * df[num_col]
                interactions.append(interaction_name)
        
        log.info(f"Created {len(interactions)} interaction features")
        return df

    # ── Encode categoricals - FULL ENCODING ───────────────────────────────────────────────
    def encode_categorical(self, df, fit=True):
        # Full categorical encoding for maximum model performance
        for col in self._categorical_cols:
            if col not in df.columns:
                continue
            
            encoder_key = f"encoder_{col}"
            if fit:
                if encoder_key not in self.encoders:
                    self.encoders[encoder_key] = LabelEncoder()
                # Handle unseen categories
                unique_vals = df[col].dropna().unique()
                self.encoders[encoder_key].fit(unique_vals)
                
            if encoder_key in self.encoders:
                # Transform with handling for unseen categories
                def safe_transform(x):
                    try:
                        return self.encoders[encoder_key].transform([x])[0]
                    except ValueError:
                        return -1  # Unknown category
                
                df[f"{col}_Encoded"] = df[col].fillna("Unknown").apply(safe_transform)
                
                # Create frequency encoding as well
                freq_map = df[col].value_counts().to_dict()
                df[f"{col}_Freq"] = df[col].map(freq_map).fillna(0)
        
        return df

    # ── Main pipeline ─────────────────────────────────────────────────────
    def run_feature_pipeline(self, df, fit=True):
        if fit:
            self._detect_columns(df)

        df = self.create_temporal_features(df)
        df = self.create_lag_features(df)
        df = self.create_rolling_features(df)
        df = self.create_store_features(df, fit=fit)
        df = self.create_product_features(df, fit=fit)
        df = self.create_interaction_features(df)
        df = self.encode_categorical(df, fit=fit)

        NON_FEATURES = {"Demand", "Date", "Store", "Product", "YearMonth"}
        feat_cols = [c for c in df.columns if c not in NON_FEATURES]
        df[feat_cols] = df[feat_cols].fillna(0)
        df = df.dropna(subset=["Demand"]).reset_index(drop=True)
        self.feature_names = feat_cols

        log.info(f"Feature pipeline: {len(feat_cols)} comprehensive features from {len(df)} rows (FULL DATASET)")
        return df, self.feature_names
