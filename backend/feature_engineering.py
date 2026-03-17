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

    # ── Temporal features (always created) ────────────────────────────────
    def create_temporal_features(self, df):
        df = df.copy()
        df["Year"]      = df["Date"].dt.year
        df["Month"]     = df["Date"].dt.month
        df["Week"]      = df["Date"].dt.isocalendar().week.astype(int)
        df["Quarter"]   = df["Date"].dt.quarter
        df["DayOfYear"] = df["Date"].dt.dayofyear

        df["Is_Year_End"]   = (df["Month"] == 12).astype(int)
        df["Is_Year_Start"] = (df["Month"] == 1).astype(int)
        df["Is_Q4"]         = (df["Quarter"] == 4).astype(int)

        # Cyclical encoding
        df["Week_Sin"]  = np.sin(2 * np.pi * df["Week"]  / 52)
        df["Week_Cos"]  = np.cos(2 * np.pi * df["Week"]  / 52)
        df["Month_Sin"] = np.sin(2 * np.pi * df["Month"] / 12)
        df["Month_Cos"] = np.cos(2 * np.pi * df["Month"] / 12)

        # Holiday proximity (universal — works for any dataset)
        for hw in [6, 47, 51]:
            df[f"Weeks_To_Holiday_{hw}"] = np.minimum(
                np.abs(df["Week"] - hw), 52 - np.abs(df["Week"] - hw)
            )
        df["Near_Holiday"] = (
            (df["Weeks_To_Holiday_6"]  <= 1) |
            (df["Weeks_To_Holiday_47"] <= 1) |
            (df["Weeks_To_Holiday_51"] <= 1)
        ).astype(int)

        # Season
        df["Season"] = df["Month"].map({
            12: "Winter", 1: "Winter", 2: "Winter",
            3: "Spring", 4: "Spring", 5: "Spring",
            6: "Summer", 7: "Summer", 8: "Summer",
            9: "Fall", 10: "Fall", 11: "Fall"
        })
        return df

    # ── Lag features (sliding window) ─────────────────────────────────────
    def create_lag_features(self, df):
        group = self._group_cols if self._group_cols else None
        df = df.sort_values((self._group_cols or []) + ["Date"]).copy()

        for lag in [1, 2, 3, 4, 8, 12, 26, 52]:
            col = f"Lag_{lag}"
            if group:
                df[col] = df.groupby(group)["Demand"].shift(lag)
                df[col] = df.groupby(group)[col].transform(lambda x: x.fillna(x.mean()).fillna(0))
            else:
                df[col] = df["Demand"].shift(lag)
                df[col] = df[col].fillna(df[col].mean()).fillna(0)

        df["Lag_52_ratio"] = df["Lag_52"] / (df["Lag_1"] + 1)
        return df

    # ── Rolling features (sliding window) ─────────────────────────────────
    def create_rolling_features(self, df):
        group = self._group_cols if self._group_cols else None
        df = df.sort_values((self._group_cols or []) + ["Date"]).copy()

        for w in [4, 8, 12, 26]:
            if group:
                s = df.groupby(group)["Demand"].transform
            else:
                s = df["Demand"].transform if hasattr(df["Demand"], "transform") else None

            if group:
                df[f"Rolling_Mean_{w}"] = s(lambda x: x.shift(1).rolling(w, min_periods=1).mean())
                df[f"Rolling_Std_{w}"]  = s(lambda x: x.shift(1).rolling(w, min_periods=1).std().fillna(0))
                df[f"Rolling_Max_{w}"]  = s(lambda x: x.shift(1).rolling(w, min_periods=1).max())
                df[f"Rolling_Min_{w}"]  = s(lambda x: x.shift(1).rolling(w, min_periods=1).min())
            else:
                shifted = df["Demand"].shift(1)
                df[f"Rolling_Mean_{w}"] = shifted.rolling(w, min_periods=1).mean()
                df[f"Rolling_Std_{w}"]  = shifted.rolling(w, min_periods=1).std().fillna(0)
                df[f"Rolling_Max_{w}"]  = shifted.rolling(w, min_periods=1).max()
                df[f"Rolling_Min_{w}"]  = shifted.rolling(w, min_periods=1).min()

        df["Momentum_4"]   = df["Lag_1"] / (df["Rolling_Mean_4"]  + 1)
        df["Momentum_12"]  = df["Lag_1"] / (df["Rolling_Mean_12"] + 1)
        df["Volatility_4"]  = df["Rolling_Std_4"]  / (df["Rolling_Mean_4"]  + 1)
        df["Volatility_12"] = df["Rolling_Std_12"] / (df["Rolling_Mean_12"] + 1)
        return df

    # ── Store features (only if Store column exists) ──────────────────────
    def create_store_features(self, df, fit=True):
        if "Store" not in df.columns:
            return df
        if fit:
            store_stats = df.groupby("Store")["Demand"].agg(
                Store_Mean="mean", Store_Median="median",
                Store_Std="std", Store_Max="max", Store_Min="min"
            ).reset_index()
            store_stats["Store_Std"] = store_stats["Store_Std"].fillna(0)
            self._store_stats_full = store_stats
        else:
            store_stats = self._store_stats_full if self._store_stats_full is not None else \
                df.groupby("Store")["Demand"].agg(
                    Store_Mean="mean", Store_Median="median",
                    Store_Std="std", Store_Max="max", Store_Min="min"
                ).reset_index()
            store_stats["Store_Std"] = store_stats["Store_Std"].fillna(0)
        df = df.merge(store_stats, on="Store", how="left")
        df["Demand_vs_Store_Mean"]   = df["Demand"] / (df["Store_Mean"]   + 1)
        df["Demand_vs_Store_Median"] = df["Demand"] / (df["Store_Median"] + 1)
        df["Store_CV"]               = df["Store_Std"] / (df["Store_Mean"] + 1)
        return df

    # ── Product features (only if Product column exists) ──────────────────
    def create_product_features(self, df, fit=True):
        if "Product" not in df.columns:
            return df
        if fit:
            product_stats = df.groupby("Product")["Demand"].agg(
                Product_Mean="mean", Product_Median="median",
                Product_Std="std", Product_Max="max", Product_Min="min"
            ).reset_index()
            product_stats["Product_Std"] = product_stats["Product_Std"].fillna(0)
            self._product_stats_full = product_stats
        else:
            product_stats = self._product_stats_full if self._product_stats_full is not None else \
                df.groupby("Product")["Demand"].agg(
                    Product_Mean="mean", Product_Median="median",
                    Product_Std="std", Product_Max="max", Product_Min="min"
                ).reset_index()
            product_stats["Product_Std"] = product_stats["Product_Std"].fillna(0)
        df = df.merge(product_stats, on="Product", how="left")
        df["Demand_vs_Product_Mean"]   = df["Demand"] / (df["Product_Mean"]   + 1)
        df["Demand_vs_Product_Median"] = df["Demand"] / (df["Product_Median"] + 1)
        df["Product_CV"]               = df["Product_Std"] / (df["Product_Mean"] + 1)
        return df

    # ── Interaction features (dynamic — only uses columns that exist) ─────
    def create_interaction_features(self, df):
        cols = set(df.columns)

        if "Store" in cols and "Holiday_Flag" in cols:
            df["Store_Holiday"] = df["Store"] * df["Holiday_Flag"]
        if "Product" in cols and "Holiday_Flag" in cols:
            df["Product_Holiday"] = df["Product"] * df["Holiday_Flag"]
        if "Store" in cols and "Product" in cols:
            df["Store_Product"] = df["Store"] * 1000 + df["Product"]
        if "Temperature" in cols and "Fuel_Price" in cols:
            df["Temp_Fuel"] = df["Temperature"] * df["Fuel_Price"]
        if "CPI" in cols and "Unemployment" in cols:
            df["Price_Index"] = df["CPI"] * df["Unemployment"]
            df["Unemployment_CPI"] = df["Unemployment"] / (df["CPI"] + 1)
        if "Fuel_Price" in cols and "Unemployment" in cols:
            df["Fuel_Unemployment"] = df["Fuel_Price"] * df["Unemployment"]
        if "CPI" in cols and "Fuel_Price" in cols:
            df["CPI_Fuel"] = df["CPI"] * df["Fuel_Price"]
        if "Temperature" in cols and "Holiday_Flag" in cols:
            df["Temp_Holiday"] = df["Temperature"] * df["Holiday_Flag"]
        if "Holiday_Flag" in cols and "Is_Q4" in cols:
            df["Holiday_Q4"] = df["Holiday_Flag"] * df["Is_Q4"]

        # Dynamic interactions between user numeric columns
        num_cols = [c for c in self._numeric_cols if c in cols]
        if len(num_cols) >= 2:
            # Create top pairwise interactions (limit to avoid explosion)
            pairs_created = 0
            for i in range(len(num_cols)):
                for j in range(i + 1, len(num_cols)):
                    if pairs_created >= 10:
                        break
                    a, b = num_cols[i], num_cols[j]
                    name = f"{a}_x_{b}"
                    df[name] = df[a] * df[b]
                    pairs_created += 1

        return df

    # ── Encode categoricals ───────────────────────────────────────────────
    def encode_categorical(self, df, fit=True):
        cats = ["Season"] + [c for c in self._categorical_cols if c in df.columns]
        for col in cats:
            if col not in df.columns:
                continue
            if fit:
                le = LabelEncoder()
                df[col] = le.fit_transform(df[col].astype(str))
                self.encoders[col] = le
            else:
                le = self.encoders.get(col)
                if le:
                    known = set(le.classes_)
                    df[col] = df[col].astype(str).apply(lambda x: x if x in known else le.classes_[0])
                    df[col] = le.transform(df[col])
                else:
                    le = LabelEncoder()
                    df[col] = le.fit_transform(df[col].astype(str))
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

        log.info(f"Feature pipeline: {len(feat_cols)} features from {len(df)} rows")
        return df, self.feature_names
