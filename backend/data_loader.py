import pandas as pd
import json
import os
from logger import get_logger

log = get_logger(__name__)

REQUIRED_COLS = {"Store", "Date", "Weekly_Sales", "Holiday_Flag",
                 "Temperature", "Fuel_Price", "CPI", "Unemployment"}


class DataLoader:
    def __init__(self, filepath="data/uploaded_data.csv"):
        self.filepath = filepath
        self.df = None

    def load_data(self):
        if not os.path.exists(self.filepath):
            raise FileNotFoundError(f"Data file not found: {self.filepath}")
        self.df = pd.read_csv(self.filepath)
        missing = REQUIRED_COLS - set(self.df.columns)
        if missing:
            raise ValueError(f"Missing required columns: {missing}")
        self.df["Date"] = pd.to_datetime(self.df["Date"], dayfirst=True)
        self.df = self.df.sort_values(["Store", "Date"]).reset_index(drop=True)
        log.info(f"Loaded {len(self.df)} rows, {len(self.df.columns)} columns")
        return self.df

    def inspect_data(self):
        info = {
            "rows": int(len(self.df)),
            "columns": list(self.df.columns),
            "date_range": [str(self.df["Date"].min()), str(self.df["Date"].max())],
            "stores": int(self.df["Store"].nunique()),
            "missing_values": int(self.df.isnull().sum().sum()),
            "weekly_sales_stats": {
                "mean": float(self.df["Weekly_Sales"].mean()),
                "min": float(self.df["Weekly_Sales"].min()),
                "max": float(self.df["Weekly_Sales"].max()),
            },
        }
        os.makedirs("logs", exist_ok=True)
        with open("logs/data_inspection.json", "w") as f:
            json.dump(info, f, indent=2)
        log.info(f"Stores: {info['stores']} | Missing: {info['missing_values']}")
        return info

    def split_train_test(self, train_months=12):
        cutoff = self.df["Date"].min() + pd.DateOffset(months=train_months)
        train_df = self.df[self.df["Date"] < cutoff].copy()
        test_df  = self.df[self.df["Date"] >= cutoff].copy()
        if len(train_df) == 0:
            raise ValueError("Train split is empty — check train_months or data date range.")
        split_info = {
            "train_rows": int(len(train_df)),
            "test_rows":  int(len(test_df)),
            "cutoff_date": str(cutoff.date()),
        }
        with open("logs/data_split.json", "w") as f:
            json.dump(split_info, f, indent=2)
        log.info(f"Train: {len(train_df)} | Test: {len(test_df)} | Cutoff: {cutoff.date()}")
        return train_df, test_df
