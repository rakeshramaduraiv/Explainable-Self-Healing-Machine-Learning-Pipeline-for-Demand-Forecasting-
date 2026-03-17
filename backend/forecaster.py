"""
Future Month Forecaster
-----------------------
Handles the rolling prediction workflow:
1. Train on historical data (12 months)
2. Test on next period (12 months) 
3. Predict NEXT month (no actuals available)
4. User uploads actual month data → predict following month
"""

import os
import json
import pandas as pd
import numpy as np
import joblib
from datetime import datetime
from pathlib import Path
from logger import get_logger

log = get_logger(__name__)

BASE = Path(__file__).parent.resolve()
MODELS = BASE / "models"
LOGS = BASE / "logs"
PROCESSED = BASE / "processed"


class FutureForecaster:
    def __init__(self):
        self.model = None
        self.feature_names = []
        self.last_known_date = None
        self.store_stats = None
        self._load_model()
    
    def _load_model(self):
        """Load the trained model and feature names"""
        model_path = MODELS / "active_model.pkl"
        summary_path = LOGS / "phase1_summary.json"
        
        if not model_path.exists():
            raise FileNotFoundError("No trained model found. Run the training pipeline first.")
        
        self.model = joblib.load(str(model_path))
        
        if summary_path.exists():
            with open(summary_path) as f:
                summary = json.load(f)
                self.feature_names = summary.get("feature_names", [])
        
        log.info(f"Loaded model with {len(self.feature_names)} features")
    
    def _get_last_known_data(self, data_path="data/uploaded_data.csv"):
        """Get the most recent data for lag/rolling feature computation"""
        if not os.path.exists(data_path):
            return None
        
        df = pd.read_csv(data_path)
        df["Date"] = pd.to_datetime(df["Date"], dayfirst=True)
        df = df.sort_values(["Store", "Date"])
        
        # Store statistics from historical data
        self.store_stats = df.groupby("Store")["Demand"].agg(
            Store_Mean="mean", Store_Median="median",
            Store_Std="std", Store_Max="max", Store_Min="min"
        ).reset_index()
        self.store_stats["Store_Std"] = self.store_stats["Store_Std"].fillna(0)
        
        self.last_known_date = df["Date"].max()
        log.info(f"Last known date: {self.last_known_date}")
        
        return df
    
    def _create_future_features(self, future_df, historical_df):
        """
        Create features for future prediction.
        Uses historical data for lag/rolling features.
        """
        future_df = future_df.copy()
        future_df["Date"] = pd.to_datetime(future_df["Date"], dayfirst=True)
        
        # Combine historical + future for feature engineering
        # Mark future rows
        future_df["_is_future"] = True
        historical_df["_is_future"] = False
        
        # For future rows, we don't have Demand yet - use placeholder
        if "Demand" not in future_df.columns:
            future_df["Demand"] = np.nan
        
        combined = pd.concat([historical_df, future_df], ignore_index=True)
        combined = combined.sort_values(["Store", "Date"]).reset_index(drop=True)
        
        # Temporal features
        combined["Year"] = combined["Date"].dt.year
        combined["Month"] = combined["Date"].dt.month
        combined["Week"] = combined["Date"].dt.isocalendar().week.astype(int)
        combined["Quarter"] = combined["Date"].dt.quarter
        combined["DayOfYear"] = combined["Date"].dt.dayofyear
        combined["Season"] = combined["Month"].map({
            12: 0, 1: 0, 2: 0,  # Winter
            3: 1, 4: 1, 5: 1,   # Spring
            6: 2, 7: 2, 8: 2,   # Summer
            9: 3, 10: 3, 11: 3  # Fall
        })
        combined["Is_Year_End"] = (combined["Month"] == 12).astype(int)
        combined["Is_Year_Start"] = (combined["Month"] == 1).astype(int)
        combined["Is_Q4"] = (combined["Quarter"] == 4).astype(int)
        
        # Cyclical encoding
        combined["Week_Sin"] = np.sin(2 * np.pi * combined["Week"] / 52)
        combined["Week_Cos"] = np.cos(2 * np.pi * combined["Week"] / 52)
        combined["Month_Sin"] = np.sin(2 * np.pi * combined["Month"] / 12)
        combined["Month_Cos"] = np.cos(2 * np.pi * combined["Month"] / 12)
        
        # Holiday proximity
        for hw in [6, 47, 51]:
            combined[f"Weeks_To_Holiday_{hw}"] = np.minimum(
                np.abs(combined["Week"] - hw), 52 - np.abs(combined["Week"] - hw)
            )
        combined["Near_Holiday"] = (
            (combined["Weeks_To_Holiday_6"] <= 1) |
            (combined["Weeks_To_Holiday_47"] <= 1) |
            (combined["Weeks_To_Holiday_51"] <= 1)
        ).astype(int)
        
        # Lag features (from historical data)
        for lag in [1, 2, 3, 4, 8, 12, 26, 52]:
            col = f"Lag_{lag}"
            combined[col] = combined.groupby("Store")["Demand"].shift(lag)
            combined[col] = combined.groupby("Store")[col].transform(
                lambda x: x.fillna(x.mean()).fillna(0)
            )
        combined["Lag_52_ratio"] = combined["Lag_52"] / (combined["Lag_1"] + 1)
        
        # Rolling features
        for w in [4, 8, 12, 26]:
            s = combined.groupby("Store")["Demand"].transform
            combined[f"Rolling_Mean_{w}"] = s(lambda x: x.shift(1).rolling(w, min_periods=1).mean())
            combined[f"Rolling_Std_{w}"] = s(lambda x: x.shift(1).rolling(w, min_periods=1).std().fillna(0))
            combined[f"Rolling_Max_{w}"] = s(lambda x: x.shift(1).rolling(w, min_periods=1).max())
            combined[f"Rolling_Min_{w}"] = s(lambda x: x.shift(1).rolling(w, min_periods=1).min())
        
        combined["Momentum_4"] = combined["Lag_1"] / (combined["Rolling_Mean_4"] + 1)
        combined["Momentum_12"] = combined["Lag_1"] / (combined["Rolling_Mean_12"] + 1)
        combined["Volatility_4"] = combined["Rolling_Std_4"] / (combined["Rolling_Mean_4"] + 1)
        combined["Volatility_12"] = combined["Rolling_Std_12"] / (combined["Rolling_Mean_12"] + 1)
        
        # Store features (from historical stats)
        if self.store_stats is not None:
            combined = combined.merge(self.store_stats, on="Store", how="left")
            # For future rows, use lag values for ratio features
            combined["Sales_vs_Store_Mean"] = combined["Lag_1"] / (combined["Store_Mean"] + 1)
            combined["Sales_vs_Store_Median"] = combined["Lag_1"] / (combined["Store_Median"] + 1)
            combined["Store_CV"] = combined["Store_Std"] / (combined["Store_Mean"] + 1)
        
        # Interaction features
        combined["Store_Holiday"] = combined["Store"] * combined["Holiday_Flag"]
        combined["Temp_Fuel"] = combined["Temperature"] * combined["Fuel_Price"]
        combined["Price_Index"] = combined["CPI"] * combined["Unemployment"]
        combined["Fuel_Unemployment"] = combined["Fuel_Price"] * combined["Unemployment"]
        combined["CPI_Fuel"] = combined["CPI"] * combined["Fuel_Price"]
        combined["Temp_Holiday"] = combined["Temperature"] * combined["Holiday_Flag"]
        combined["Holiday_Q4"] = combined["Holiday_Flag"] * combined["Is_Q4"]
        combined["Unemployment_CPI"] = combined["Unemployment"] / (combined["CPI"] + 1)
        
        # Extract only future rows
        future_processed = combined[combined["_is_future"] == True].copy()
        future_processed = future_processed.drop(columns=["_is_future"])
        
        # Fill missing features
        for f in self.feature_names:
            if f not in future_processed.columns:
                future_processed[f] = 0
        
        future_processed = future_processed.fillna(0)
        
        return future_processed
    
    def predict_next_month(self, future_data_df):
        """
        Predict sales for the next month.
        
        Args:
            future_data_df: DataFrame with columns:
                Store, Date, Holiday_Flag, Temperature, Fuel_Price, CPI, Unemployment
                (NO Demand - that's what we're predicting!)
        
        Returns:
            DataFrame with predictions
        """
        # Load historical data for lag features
        historical_df = self._get_last_known_data()
        if historical_df is None:
            raise ValueError("No historical data found. Upload training data first.")
        
        # Create features
        processed = self._create_future_features(future_data_df, historical_df)
        
        # Ensure feature order matches training
        X = processed[self.feature_names]
        
        # Predict
        predictions = self.model.predict(X)
        
        # Get confidence intervals if available
        rf = joblib.load(str(MODELS / "baseline_model_rf.pkl")) if (MODELS / "baseline_model_rf.pkl").exists() else None
        if rf and hasattr(rf, "estimators_"):
            tree_preds = np.array([t.predict(X) for t in rf.estimators_])
            std_pred = np.std(tree_preds, axis=0)
            ci_lower = np.maximum(predictions - 1.96 * std_pred, 0)
            ci_upper = predictions + 1.96 * std_pred
        else:
            ci_lower = predictions * 0.9
            ci_upper = predictions * 1.1
        
        # Build result
        result = pd.DataFrame({
            "Store": processed["Store"].values,
            "Date": processed["Date"].dt.strftime("%Y-%m-%d").values,
            "Predicted_Sales": predictions.round(2),
            "CI_Lower": ci_lower.round(2),
            "CI_Upper": ci_upper.round(2),
        })
        
        # Save forecast
        PROCESSED.mkdir(exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        forecast_month = processed["Date"].dt.to_period("M").iloc[0]
        result.to_csv(PROCESSED / f"forecast_{forecast_month}_{ts}.csv", index=False)
        
        log.info(f"Generated forecast for {forecast_month}: {len(result)} predictions")
        
        return result
    
    def update_with_actuals(self, actual_data_df):
        """
        User uploads actual data for a month.
        This updates the historical data and enables prediction for the next month.
        
        Args:
            actual_data_df: DataFrame with ALL columns including Demand
        
        Returns:
            dict with update status and next predictable month
        """
        required = {"Store", "Product", "Date", "Demand", "Holiday_Flag", 
                    "Temperature", "Fuel_Price", "CPI", "Unemployment"}
        missing = required - set(actual_data_df.columns)
        if missing:
            raise ValueError(f"Missing required columns: {missing}")
        
        actual_data_df["Date"] = pd.to_datetime(actual_data_df["Date"], dayfirst=True)
        uploaded_month = actual_data_df["Date"].dt.to_period("M").iloc[0]
        
        # Load existing data
        data_path = BASE / "data" / "uploaded_data.csv"
        if data_path.exists():
            existing = pd.read_csv(data_path)
            existing["Date"] = pd.to_datetime(existing["Date"], dayfirst=True)
            
            # Remove any existing data for this month (replace with new actuals)
            existing = existing[existing["Date"].dt.to_period("M") != uploaded_month]
            
            # Append new data
            combined = pd.concat([existing, actual_data_df], ignore_index=True)
            combined = combined.sort_values(["Store", "Date"]).reset_index(drop=True)
        else:
            combined = actual_data_df.sort_values(["Store", "Date"]).reset_index(drop=True)
        
        # Save updated data
        combined.to_csv(data_path, index=False)
        
        # Calculate next predictable month
        next_month = uploaded_month + 1
        
        log.info(f"Updated data with {len(actual_data_df)} rows for {uploaded_month}")
        log.info(f"Next predictable month: {next_month}")
        
        return {
            "status": "success",
            "uploaded_month": str(uploaded_month),
            "rows_added": len(actual_data_df),
            "total_rows": len(combined),
            "next_predictable_month": str(next_month),
            "message": f"Data updated. You can now predict {next_month}."
        }


def get_forecaster():
    """Factory function to get forecaster instance"""
    return FutureForecaster()
