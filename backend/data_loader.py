import pandas as pd
import numpy as np
import json
import os
from logger import get_logger

log = get_logger(__name__)

# These three are required for product-level demand forecasting
REQUIRED_COLS = {"Date", "Product", "Demand"}
# Aliases we auto-rename
ALIASES = {
    "weekly_sales": "Demand", "sales": "Demand", "units": "Demand",
    "quantity": "Demand", "target": "Demand", "revenue": "Demand",
    "date": "Date", "week": "Date", "order_date": "Date",
    "store": "Store", "store_id": "Store", "shop": "Store",
    "product": "Product", "item": "Product", "product_id": "Product",
    "item_id": "Product", "sku": "Product", "category": "Product",
    "holiday_flag": "Holiday_Flag", "is_holiday": "Holiday_Flag",
    "holiday": "Holiday_Flag", "isholiday": "Holiday_Flag",
    "temperature": "Temperature", "temp": "Temperature",
    "fuel_price": "Fuel_Price", "fuel": "Fuel_Price",
    "cpi": "CPI", "unemployment": "Unemployment",
}


class DataLoader:
    def __init__(self, filepath="data/uploaded_data.csv"):
        self.filepath = filepath
        self.df = None
        self.detected_columns = {}  # {role: col_name}

    def load_data(self):
        if not os.path.exists(self.filepath):
            raise FileNotFoundError(f"Data file not found: {self.filepath}")
        # Read raw text and strip quotes wrapping entire rows
        with open(self.filepath, "r", encoding="utf-8-sig") as f:
            raw = f.read()
        if raw.count('"') > len(raw.splitlines()):
            import re
            cleaned = re.sub(r'^"(.*)"$', r'\1', raw, flags=re.MULTILINE)
            with open(self.filepath, "w", encoding="utf-8") as f:
                f.write(cleaned)
        self.df = pd.read_csv(self.filepath, encoding="utf-8-sig")
        self.df.columns = self.df.columns.str.strip().str.replace('\ufeff', '')

        # Auto-rename known aliases
        rename_map = {}
        for col in self.df.columns:
            key = col.lower().replace(" ", "_")
            if key in ALIASES and ALIASES[key] not in self.df.columns:
                rename_map[col] = ALIASES[key]
        if rename_map:
            self.df = self.df.rename(columns=rename_map)
            log.info(f"Auto-renamed columns: {rename_map}")

        # Check minimum requirements
        missing = REQUIRED_COLS - set(self.df.columns)
        if missing:
            raise ValueError(
                f"Missing required columns: {missing}. "
                f"Need 'Date', 'Product', and 'Demand' (aliases: Sales/Weekly_Sales→Demand, Item/Category→Product). "
                f"Got: {list(self.df.columns)}"
            )

        # Parse dates
        self.df["Date"] = pd.to_datetime(self.df["Date"], dayfirst=True, errors="coerce")
        if self.df["Date"].isna().sum() > len(self.df) * 0.5:
            self.df["Date"] = pd.to_datetime(self.df["Date"], errors="coerce")
        self.df = self.df.dropna(subset=["Date"])

        # Ensure Demand is numeric
        self.df["Demand"] = pd.to_numeric(self.df["Demand"], errors="coerce")
        self.df = self.df.dropna(subset=["Demand"])

        # Auto-detect column roles
        self._detect_columns()

        # Sort by available group keys + Date
        sort_cols = []
        if "Store" in self.df.columns:
            sort_cols.append("Store")
        if "Product" in self.df.columns:
            sort_cols.append("Product")
        sort_cols.append("Date")
        self.df = self.df.sort_values(sort_cols).reset_index(drop=True)

        log.info(f"Loaded {len(self.df)} rows, {len(self.df.columns)} columns")
        log.info(f"Detected roles: {self.detected_columns}")
        return self.df

    def _detect_columns(self):
        """Auto-detect column roles from the data."""
        cols = set(self.df.columns)
        self.detected_columns = {
            "target": "Demand",
            "date": "Date",
            "has_store": "Store" in cols,
            "has_product": "Product" in cols,
            "has_holiday": "Holiday_Flag" in cols,
            "numeric_features": [],
            "categorical_features": [],
        }

        skip = {"Date", "Demand", "Store", "Product"}
        for col in self.df.columns:
            if col in skip:
                continue
            if self.df[col].dtype in ["float64", "float32", "int64", "int32"]:
                nunique = self.df[col].nunique()
                if nunique <= 10 and nunique < len(self.df) * 0.01:
                    self.detected_columns["categorical_features"].append(col)
                else:
                    self.detected_columns["numeric_features"].append(col)
            elif self.df[col].dtype == "object":
                if self.df[col].nunique() < 50:
                    self.detected_columns["categorical_features"].append(col)

        log.info(f"Numeric features: {self.detected_columns['numeric_features']}")
        log.info(f"Categorical features: {self.detected_columns['categorical_features']}")

    def inspect_data(self):
        cols = set(self.df.columns)
        info = {
            "rows": int(len(self.df)),
            "columns": list(self.df.columns),
            "date_range": [str(self.df["Date"].min()), str(self.df["Date"].max())],
            "stores": int(self.df["Store"].nunique()) if "Store" in cols else 0,
            "products": int(self.df["Product"].nunique()) if "Product" in cols else 0,
            "missing_values": int(self.df.isnull().sum().sum()),
            "demand_stats": {
                "mean": float(self.df["Demand"].mean()),
                "min": float(self.df["Demand"].min()),
                "max": float(self.df["Demand"].max()),
            },
            "detected_columns": self.detected_columns,
            "user_features": self.detected_columns.get("numeric_features", [])
                           + self.detected_columns.get("categorical_features", []),
        }
        os.makedirs("logs", exist_ok=True)
        with open("logs/data_inspection.json", "w") as f:
            json.dump(info, f, indent=2)
        log.info(f"Stores: {info['stores']} | Products: {info['products']} | Missing: {info['missing_values']}")
        return info

    def split_by_year(self):
        years = sorted(self.df["Date"].dt.year.unique())
        if len(years) < 2:
            raise ValueError(
                f"Need at least 2 years of data. Found only: {years}. "
                f"Upload 24 months of data (e.g., 2024 + 2025)."
            )

        train_year = years[0]
        test_year = years[1]

        train_df = self.df[self.df["Date"].dt.year == train_year].copy()
        test_df = self.df[self.df["Date"].dt.year == test_year].copy()

        if len(train_df) == 0:
            raise ValueError(f"No data for training year {train_year}")
        if len(test_df) == 0:
            raise ValueError(f"No data for testing year {test_year}")

        train_months = train_df["Date"].dt.month.nunique()
        test_months = test_df["Date"].dt.month.nunique()

        split_info = {
            "train_year": int(train_year),
            "test_year": int(test_year),
            "train_rows": int(len(train_df)),
            "test_rows": int(len(test_df)),
            "train_months": int(train_months),
            "test_months": int(test_months),
        }
        os.makedirs("logs", exist_ok=True)
        with open("logs/data_split.json", "w") as f:
            json.dump(split_info, f, indent=2)

        log.info(f"Train: {train_year} ({len(train_df)} rows, {train_months} months)")
        log.info(f"Test:  {test_year} ({len(test_df)} rows, {test_months} months)")

        return train_df, test_df

    def split_train_test(self, train_months=12):
        cutoff = self.df["Date"].min() + pd.DateOffset(months=train_months)
        train_df = self.df[self.df["Date"] < cutoff].copy()
        test_df = self.df[self.df["Date"] >= cutoff].copy()
        if len(train_df) == 0:
            raise ValueError("Train split is empty — check train_months or data date range.")
        split_info = {
            "train_rows": int(len(train_df)),
            "test_rows": int(len(test_df)),
            "cutoff_date": str(cutoff.date()),
        }
        with open("logs/data_split.json", "w") as f:
            json.dump(split_info, f, indent=2)
        log.info(f"Train: {len(train_df)} | Test: {len(test_df)} | Cutoff: {cutoff.date()}")
        return train_df, test_df
