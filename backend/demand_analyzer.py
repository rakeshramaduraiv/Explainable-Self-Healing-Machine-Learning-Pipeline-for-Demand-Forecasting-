import pandas as pd
import numpy as np
import os
from logger import get_logger

log = get_logger(__name__)


class DemandAnalyzer:
    def __init__(self):
        self.df = None
        self.metrics = {}
        
    def load_data(self, filepath="data/uploaded_data.csv"):
        if not os.path.exists(filepath):
            raise FileNotFoundError(f"Data file not found: {filepath}")
        self.df = pd.read_csv(filepath)
        if "Weekly_Sales" not in self.df.columns or "Date" not in self.df.columns:
            raise ValueError("CSV must contain 'Date' and 'Weekly_Sales' columns")
        self.df["Date"] = pd.to_datetime(self.df["Date"], dayfirst=False, infer_datetime_format=True)
        self.df = self.df.sort_values("Date").reset_index(drop=True)
        self.df["Weekly_Sales"] = pd.to_numeric(self.df["Weekly_Sales"], errors="coerce")
        self.df = self.df.dropna(subset=["Weekly_Sales"])
        log.info(f"Loaded {len(self.df)} rows for demand analysis")
        return self.df
    
    def calculate_demand_metrics(self):
        """Calculate key demand statistics"""
        # Monthly aggregation
        monthly = self.df.groupby(self.df["Date"].dt.to_period("M"))["Weekly_Sales"].sum()
        
        self.metrics = {
            "avg_weekly_demand": float(self.df["Weekly_Sales"].mean()),
            "total_demand": float(self.df["Weekly_Sales"].sum()),
            "peak_demand_month": str(monthly.idxmax()),
            "lowest_demand_month": str(monthly.idxmin()),
            "demand_growth_rate": self._calculate_growth_rate(monthly)
        }
        
        log.info(f"Demand metrics calculated: avg={self.metrics['avg_weekly_demand']:,.0f}")
        return self.metrics
    
    def _calculate_growth_rate(self, monthly_data):
        if len(monthly_data) < 2:
            return 0.0
        recent   = monthly_data.iloc[-1]
        previous = monthly_data.iloc[-2]
        if previous == 0 or not np.isfinite(previous):
            return 0.0
        rate = float(((recent - previous) / abs(previous)) * 100)
        return rate if np.isfinite(rate) else 0.0
    
    def get_demand_trend_data(self):
        """Get data for demand trend chart"""
        return self.df[["Date", "Weekly_Sales"]].copy()
    
    def get_monthly_demand_data(self):
        """Get data for monthly demand chart"""
        monthly = self.df.groupby(self.df["Date"].dt.to_period("M"))["Weekly_Sales"].sum().reset_index()
        monthly["Date"] = monthly["Date"].astype(str)
        return monthly
    
    def get_store_demand_data(self):
        """Get data for store-level demand chart"""
        if "Store" not in self.df.columns:
            return pd.DataFrame()
        
        store_demand = self.df.groupby("Store")["Weekly_Sales"].sum().reset_index()
        store_demand = store_demand.sort_values("Weekly_Sales", ascending=False)
        store_demand["Store"] = "Store " + store_demand["Store"].astype(str)
        return store_demand