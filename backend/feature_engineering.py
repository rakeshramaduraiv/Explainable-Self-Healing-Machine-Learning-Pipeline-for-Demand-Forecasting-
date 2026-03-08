import pandas as pd
import numpy as np
from sklearn.preprocessing import LabelEncoder


class FeatureEngineer:
    def __init__(self):
        self.feature_names = []
        self.encoders = {}

    def create_temporal_features(self, df):
        df = df.copy()
        df["Year"]         = df["Date"].dt.year
        df["Month"]        = df["Date"].dt.month
        df["Week"]         = df["Date"].dt.isocalendar().week.astype(int)
        df["Quarter"]      = df["Date"].dt.quarter
        df["DayOfYear"]    = df["Date"].dt.dayofyear
        df["Season"]       = df["Month"].map({
            12:"Winter",1:"Winter",2:"Winter",
            3:"Spring",4:"Spring",5:"Spring",
            6:"Summer",7:"Summer",8:"Summer",
            9:"Fall",10:"Fall",11:"Fall"
        })
        df["Is_Year_End"]   = (df["Month"] == 12).astype(int)
        df["Is_Year_Start"] = (df["Month"] == 1).astype(int)
        df["Is_Q4"]         = (df["Quarter"] == 4).astype(int)
        # Cyclical encoding
        df["Week_Sin"]  = np.sin(2 * np.pi * df["Week"]  / 52)
        df["Week_Cos"]  = np.cos(2 * np.pi * df["Week"]  / 52)
        df["Month_Sin"] = np.sin(2 * np.pi * df["Month"] / 12)
        df["Month_Cos"] = np.cos(2 * np.pi * df["Month"] / 12)
        # Holiday proximity: SuperBowl=6, Thanksgiving=47, Christmas=51
        for hw in [6, 47, 51]:
            df[f"Weeks_To_Holiday_{hw}"] = np.minimum(
                np.abs(df["Week"] - hw), 52 - np.abs(df["Week"] - hw)
            )
        # Is holiday week (within 1 week of major holiday)
        df["Near_Holiday"] = (
            (df["Weeks_To_Holiday_6"]  <= 1) |
            (df["Weeks_To_Holiday_47"] <= 1) |
            (df["Weeks_To_Holiday_51"] <= 1)
        ).astype(int)
        return df

    def create_lag_features(self, df):
        df = df.sort_values(["Store", "Date"])
        for lag in [1, 2, 3, 4, 8, 12, 26, 52]:
            col = f"Lag_{lag}"
            df[col] = df.groupby("Store")["Weekly_Sales"].shift(lag)
            df[col] = df.groupby("Store")[col].transform(lambda x: x.fillna(x.mean()).fillna(0))
        # Year-over-year lag
        df["Lag_52_ratio"] = df["Lag_52"] / (df["Lag_1"] + 1)
        return df

    def create_rolling_features(self, df):
        df = df.sort_values(["Store", "Date"])
        for w in [4, 8, 12, 26]:
            s = df.groupby("Store")["Weekly_Sales"].transform
            df[f"Rolling_Mean_{w}"] = s(lambda x: x.shift(1).rolling(w, min_periods=1).mean())
            df[f"Rolling_Std_{w}"]  = s(lambda x: x.shift(1).rolling(w, min_periods=1).std().fillna(0))
            df[f"Rolling_Max_{w}"]  = s(lambda x: x.shift(1).rolling(w, min_periods=1).max())
            df[f"Rolling_Min_{w}"]  = s(lambda x: x.shift(1).rolling(w, min_periods=1).min())
        # Momentum: current lag vs rolling mean
        df["Momentum_4"]  = df["Lag_1"] / (df["Rolling_Mean_4"]  + 1)
        df["Momentum_12"] = df["Lag_1"] / (df["Rolling_Mean_12"] + 1)
        # Volatility ratio
        df["Volatility_4"]  = df["Rolling_Std_4"]  / (df["Rolling_Mean_4"]  + 1)
        df["Volatility_12"] = df["Rolling_Std_12"] / (df["Rolling_Mean_12"] + 1)
        return df

    def create_store_features(self, df):
        store_stats = df.groupby("Store")["Weekly_Sales"].agg(
            Store_Mean="mean", Store_Median="median",
            Store_Std="std",   Store_Max="max", Store_Min="min"
        ).reset_index()
        df = df.merge(store_stats, on="Store", how="left")
        df["Sales_vs_Store_Mean"]   = df["Weekly_Sales"] / (df["Store_Mean"]   + 1)
        df["Sales_vs_Store_Median"] = df["Weekly_Sales"] / (df["Store_Median"] + 1)
        df["Store_CV"]              = df["Store_Std"]    / (df["Store_Mean"]   + 1)
        return df

    def create_interaction_features(self, df):
        df["Store_Holiday"]      = df["Store"] * df["Holiday_Flag"]
        df["Temp_Fuel"]          = df["Temperature"] * df["Fuel_Price"]
        df["Price_Index"]        = df["CPI"] * df["Unemployment"]
        df["Fuel_Unemployment"]  = df["Fuel_Price"] * df["Unemployment"]
        df["CPI_Fuel"]           = df["CPI"] * df["Fuel_Price"]
        df["Temp_Holiday"]       = df["Temperature"] * df["Holiday_Flag"]
        df["Holiday_Q4"]         = df["Holiday_Flag"] * df.get("Is_Q4", 0)
        df["Unemployment_CPI"]   = df["Unemployment"] / (df["CPI"] + 1)
        return df

    def encode_categorical(self, df, fit=True):
        for col in ["Season"]:
            if col in df.columns:
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
        return df

    def run_feature_pipeline(self, df, fit=True):
        df = self.create_temporal_features(df)
        df = self.create_lag_features(df)
        df = self.create_rolling_features(df)
        if fit:
            df = self.create_store_features(df)
            self._store_stats = df[["Store","Store_Mean","Store_Median","Store_Std","Store_Max","Store_Min","Store_CV"]].drop_duplicates()
        else:
            if hasattr(self, "_store_stats"):
                df = df.merge(self._store_stats, on="Store", how="left")
                df["Sales_vs_Store_Mean"]   = df["Weekly_Sales"] / (df["Store_Mean"]   + 1)
                df["Sales_vs_Store_Median"] = df["Weekly_Sales"] / (df["Store_Median"] + 1)
        df = self.create_interaction_features(df)
        df = self.encode_categorical(df, fit=fit)
        NON_FEATURES = {"Weekly_Sales", "Date", "Store", "YearMonth"}
        feat_cols = [c for c in df.columns if c not in NON_FEATURES]
        df[feat_cols] = df[feat_cols].fillna(0)
        df = df.dropna(subset=["Weekly_Sales"]).reset_index(drop=True)
        self.feature_names = feat_cols
        return df, self.feature_names
