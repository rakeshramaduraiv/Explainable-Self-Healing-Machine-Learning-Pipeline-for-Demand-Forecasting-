"""
Sequential Monthly Predictor (Dynamic)
---------------------------------------
Manages the rolling monthly prediction cycle.
Works with ANY CSV that has Date + Demand (+ optional columns).
Auto-fills missing economic/feature columns from last known values.
"""

import os
import json
import pandas as pd
import numpy as np
import joblib
from datetime import datetime
from pathlib import Path
from feature_engineering import FeatureEngineer
from logger import get_logger

log = get_logger(__name__)

BASE = Path(__file__).parent.resolve()
MODELS = BASE / "models"
LOGS = BASE / "logs"
PROCESSED = BASE / "processed"
DATA = BASE / "data"
UPLOADS = BASE / "uploads"
PREDICTIONS = BASE / "predictions"

for d in [MODELS, LOGS, PROCESSED, DATA, UPLOADS, PREDICTIONS]:
    d.mkdir(exist_ok=True)


class SequentialPredictor:
    def __init__(self):
        self.model = None
        self.feature_names = []
        self.engineer = FeatureEngineer()
        self.state_file = LOGS / "predictor_state.json"
        self._load_model()
        self._load_engineer()
        self._load_state()

    def _load_model(self):
        model_path = MODELS / "active_model.pkl"
        if not model_path.exists():
            log.warning("No trained model found")
            return
        self.model = joblib.load(str(model_path))
        summary_path = LOGS / "phase1_summary.json"
        if summary_path.exists():
            with open(summary_path) as f:
                self.feature_names = json.load(f).get("feature_names", [])
        log.info(f"Loaded model with {len(self.feature_names)} features")

    def _load_engineer(self):
        eng_path = str(MODELS / "feature_engineer.pkl")
        if self.engineer.load_state(eng_path):
            log.info("Loaded feature engineer state")
        else:
            log.warning("No saved feature engineer state")

    def _load_state(self):
        if self.state_file.exists():
            with open(self.state_file) as f:
                self.state = json.load(f)
        else:
            self.state = {
                "last_prediction_month": None,
                "last_upload_month": None,
                "train_end": None,
                "test_end": None,
            }

    def _save_state(self):
        self.state["updated_at"] = datetime.now().isoformat()
        LOGS.mkdir(exist_ok=True)
        with open(self.state_file, "w") as f:
            json.dump(self.state, f, indent=2)

    @staticmethod
    def _next_month(ym: str) -> str:
        d = pd.Timestamp(ym + "-01") + pd.DateOffset(months=1)
        return d.strftime("%Y-%m")

    @staticmethod
    def _prev_month(ym: str) -> str:
        d = pd.Timestamp(ym + "-01") - pd.DateOffset(months=1)
        return d.strftime("%Y-%m")

    # ── CSV reading ───────────────────────────────────────────────────────
    @staticmethod
    def _safe_read_csv(path) -> pd.DataFrame:
        df = pd.read_csv(path, encoding="utf-8-sig")
        df.columns = df.columns.str.strip().str.replace('\ufeff', '')
        if len(df.columns) == 1 and ',' in df.columns[0]:
            import io
            raw = open(path, 'r', encoding='utf-8-sig').read().replace('"', '')
            df = pd.read_csv(io.StringIO(raw))
            df.columns = df.columns.str.strip()
        return df

    # ── Load all data ─────────────────────────────────────────────────────
    def _load_all_data(self) -> pd.DataFrame:
        frames = []
        base = DATA / "uploaded_data.csv"
        if base.exists():
            df = self._safe_read_csv(base)
            df["Date"] = pd.to_datetime(df["Date"], dayfirst=True)
            frames.append(df)

        for f in sorted(UPLOADS.glob("*_actual.csv")):
            udf = self._safe_read_csv(f)
            udf["Date"] = pd.to_datetime(udf["Date"], dayfirst=True)
            frames.append(udf)

        if not frames:
            raise ValueError("No data available")

        combined = pd.concat(frames, ignore_index=True)
        # Deduplicate on whatever group columns exist + Date
        dedup_cols = ["Date"]
        if "Store" in combined.columns:
            dedup_cols.insert(0, "Store")
        if "Product" in combined.columns:
            dedup_cols.insert(-1, "Product")
        combined = combined.drop_duplicates(subset=dedup_cols, keep="last")
        sort_cols = [c for c in ["Store", "Product"] if c in combined.columns] + ["Date"]
        combined = combined.sort_values(sort_cols).reset_index(drop=True)
        return combined

    # ── Feature engineering for prediction ────────────────────────────────
    def _build_features(self, all_data: pd.DataFrame, target_month: str):
        df = all_data.copy()
        is_future = df["Demand"].isna()
        df.loc[is_future, "Demand"] = 0

        # ULTRA SPEED: Skip complex feature engineering for uploads
        log.info("⚡ ULTRA SPEED: Using minimal feature engineering for faster processing")
        df, feat_cols = self.engineer.run_feature_pipeline(df, fit=False)
        feat_cols = self.feature_names if self.feature_names else feat_cols

        ym = df["Date"].dt.to_period("M").astype(str)
        target_rows = df[ym == target_month].copy()

        if target_rows.empty:
            raise ValueError(f"No data rows found for {target_month}")

        for c in feat_cols:
            if c not in target_rows.columns:
                target_rows[c] = 0
        target_rows[feat_cols] = target_rows[feat_cols].fillna(0)

        return target_rows, feat_cols

    # ── Dynamic scaffold for future month ─────────────────────────────────
    def _create_future_scaffold(self, all_data: pd.DataFrame, target_month: str):
        """Create placeholder rows for a future month using whatever columns exist."""
        cols = set(all_data.columns)
        has_store = "Store" in cols
        has_product = "Product" in cols

        stores = sorted(all_data["Store"].unique()) if has_store else [1]
        products = sorted(all_data["Product"].unique()) if has_product else [1]

        ym = pd.Timestamp(target_month + "-01")
        weeks = pd.date_range(ym, ym + pd.DateOffset(months=1) - pd.Timedelta(days=1), freq="W-FRI")
        if len(weeks) == 0:
            weeks = [ym + pd.Timedelta(days=d) for d in [0, 7, 14, 21]]

        # Get last known values for all numeric columns
        last_vals = all_data.sort_values("Date").iloc[-1]

        rows = []
        for store in stores:
            for product in products:
                for dt in weeks:
                    row = {"Date": dt, "Demand": np.nan}
                    if has_store:
                        row["Store"] = store
                    if has_product:
                        row["Product"] = product

                    # Auto-fill all other columns from last known values
                    for col in all_data.columns:
                        if col in row or col in ("Date", "Demand", "Store", "Product"):
                            continue
                        val = last_vals.get(col)
                        if val is not None and not (isinstance(val, float) and np.isnan(val)):
                            row[col] = val
                        else:
                            row[col] = 0

                    rows.append(row)

        return pd.DataFrame(rows)

    # ── Core: predict next month ──────────────────────────────────────────
    def predict_next_month(self, data_through_month: str = None) -> dict:
        if self.model is None:
            raise ValueError("No trained model. Run the pipeline first.")

        all_data = self._load_all_data()

        if data_through_month is None:
            last_date = all_data["Date"].max()
            data_through_month = last_date.to_period("M").strftime("%Y-%m")

        target_month = self._next_month(data_through_month)

        ym = all_data["Date"].dt.to_period("M").astype(str)
        if target_month not in ym.values:
            scaffold = self._create_future_scaffold(all_data, target_month)
            all_data = pd.concat([all_data, scaffold], ignore_index=True)
            sort_cols = [c for c in ["Store", "Product"] if c in all_data.columns] + ["Date"]
            all_data = all_data.sort_values(sort_cols).reset_index(drop=True)

        target_rows, feat_cols = self._build_features(all_data, target_month)
        # Align to model's expected features
        if self.feature_names:
            feat_cols = self.feature_names
            for c in feat_cols:
                if c not in target_rows.columns:
                    target_rows[c] = 0
            target_rows[feat_cols] = target_rows[feat_cols].fillna(0)
        X = target_rows[feat_cols].values
        predictions = self.model.predict(X)

        # Confidence intervals
        ci_lower, ci_upper = predictions * 0.85, predictions * 1.15
        rf_path = MODELS / "baseline_model_rf.pkl"
        if rf_path.exists():
            try:
                rf = joblib.load(str(rf_path))
                if hasattr(rf, "estimators_"):
                    tree_preds = np.array([t.predict(X) for t in rf.estimators_])
                    std_pred = np.std(tree_preds, axis=0)
                    ci_lower = np.maximum(predictions - 1.96 * std_pred, 0)
                    ci_upper = predictions + 1.96 * std_pred
            except Exception:
                pass

        result_df = pd.DataFrame({
            "Date": target_rows["Date"].dt.strftime("%Y-%m-%d").values,
            "Predicted_Demand": predictions.round(2),
            "CI_Lower": ci_lower.round(2),
            "CI_Upper": ci_upper.round(2),
        })

        # Add group columns if they exist
        if "Store" in target_rows.columns:
            result_df.insert(0, "Store", target_rows["Store"].values)
        if "Product" in target_rows.columns:
            idx = 1 if "Store" in result_df.columns else 0
            result_df.insert(idx, "Product", target_rows["Product"].values)

        # Save
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        pred_path = PREDICTIONS / f"{target_month}_predictions.csv"
        result_df.to_csv(pred_path, index=False)
        result_df.to_csv(PREDICTIONS / f"{target_month}_predictions_{ts}.csv", index=False)

        # Group summary
        group_summary = {}
        if "Product" in result_df.columns:
            ps = result_df.groupby("Product")["Predicted_Demand"].mean().round(2)
            group_summary = {int(k): float(v) for k, v in ps.items()}

        self.state["last_prediction_month"] = target_month
        self.state["data_through"] = data_through_month
        self._save_state()

        log.info(f"Predicted {target_month}: {len(result_df)} rows, mean={predictions.mean():,.0f} units")

        return {
            "prediction_month": target_month,
            "based_on_data_through": data_through_month,
            "count": len(result_df),
            "mean_predicted": round(float(predictions.mean()), 2),
            "product_summary": group_summary,
            "predictions": result_df.to_dict(orient="records"),
            "timestamp": datetime.now().isoformat(),
        }

    # ── Process user upload of actuals ────────────────────────────────────
    def process_actuals_upload(self, df: pd.DataFrame) -> dict:
        df.columns = df.columns.str.strip().str.replace('\ufeff', '')

        # Enhanced column detection and renaming
        rename = {}
        for c in df.columns:
            cl = c.lower().replace(" ", "_").replace("-", "_")
            # More flexible demand column detection
            if cl in ("sales", "weekly_sales", "units", "quantity", "demand", "actual", "actual_demand") and "Demand" not in df.columns:
                rename[c] = "Demand"
            # More flexible date column detection  
            if cl in ("date", "week", "order_date", "time", "timestamp", "period") and "Date" not in df.columns:
                rename[c] = "Date"
            # More flexible product column detection
            if cl in ("item", "product_id", "item_id", "sku", "category", "product") and "Product" not in df.columns:
                rename[c] = "Product"
            # Store column detection
            if cl in ("store", "store_id", "location", "shop") and "Store" not in df.columns:
                rename[c] = "Store"
        
        if rename:
            df = df.rename(columns=rename)
            log.info(f"Renamed columns: {rename}")

        # Check required columns - ALL THREE REQUIRED for main pipeline
        required = ["Date", "Product", "Demand"]
        missing = [c for c in required if c not in df.columns]
        if missing:
            available = list(df.columns)
            raise ValueError(f"Missing required columns: {missing}. Available columns: {available}. The model needs Date, Product, and Demand to work properly.")

        # ULTRA SPEED: Sample large uploads
        if len(df) > 10000:
            log.warning(f"⚡ ULTRA SPEED: Sampling {len(df)} rows to 10K for faster processing")
            df = df.sample(10000, random_state=42).reset_index(drop=True)
            log.info(f"Sampled to {len(df)} rows for ultra speed processing")

        try:
            df["Date"] = pd.to_datetime(df["Date"], dayfirst=True, errors='coerce')
            if df["Date"].isna().any():
                # Try different date formats
                df["Date"] = pd.to_datetime(df["Date"], format='%Y-%m-%d', errors='coerce')
                if df["Date"].isna().any():
                    df["Date"] = pd.to_datetime(df["Date"], format='%m/%d/%Y', errors='coerce')
        except Exception as e:
            raise ValueError(f"Could not parse Date column. Try DD-MM-YYYY, YYYY-MM-DD, or MM/DD/YYYY format. Error: {e}")
        
        if df["Date"].isna().any():
            raise ValueError("Some dates could not be parsed. Check date format.")
        
        # Validate demand column is numeric
        try:
            df["Demand"] = pd.to_numeric(df["Demand"], errors='coerce')
            if df["Demand"].isna().any():
                raise ValueError("Demand column contains non-numeric values")
        except Exception as e:
            raise ValueError(f"Could not convert Demand to numeric: {e}")
        
        # Validate Product column
        if df["Product"].isna().any():
            raise ValueError("Product column contains missing values")
            
        upload_month = df["Date"].dt.to_period("M").iloc[0].strftime("%Y-%m")

        # Save actuals
        actual_path = UPLOADS / f"{upload_month}_actual.csv"
        save_df = df.copy()
        save_df["Date"] = save_df["Date"].dt.strftime("%d-%m-%Y")
        save_df.to_csv(actual_path, index=False)

        # ULTRA SPEED: Skip auto-fill for faster processing
        log.info("⚡ ULTRA SPEED: Skipping auto-fill for faster processing")

        # Compare with predictions if they exist
        comparison = None
        pred_path = PREDICTIONS / f"{upload_month}_predictions.csv"
        if pred_path.exists():
            pred_df = pd.read_csv(pred_path)
            pred_df["Date"] = pd.to_datetime(pred_df["Date"])

            # Determine merge keys
            merge_keys = []
            if "Store" in df.columns and "Store" in pred_df.columns:
                merge_keys.append("Store")
            if "Product" in df.columns and "Product" in pred_df.columns:
                merge_keys.append("Product")

            if merge_keys:
                actual_agg = df.groupby(merge_keys)["Demand"].mean().reset_index()
                actual_agg.columns = merge_keys + ["Actual"]
                pred_agg = pred_df.groupby(merge_keys)["Predicted_Demand"].mean().reset_index()
                pred_agg.columns = merge_keys + ["Predicted"]
                merged = actual_agg.merge(pred_agg, on=merge_keys, how="inner")
            else:
                actual_mean = df["Demand"].mean()
                pred_mean = pred_df["Predicted_Demand"].mean()
                merged = pd.DataFrame([{"Actual": actual_mean, "Predicted": pred_mean}])

            if not merged.empty:
                merged["Error"] = (merged["Actual"] - merged["Predicted"]).abs()
                merged["Error_Pct"] = (merged["Error"] / (merged["Actual"].abs() + 1e-9) * 100).round(2)

                mae = float(merged["Error"].mean())
                rmse = float(np.sqrt((merged["Error"] ** 2).mean()))
                mape = float(merged["Error_Pct"].mean())

                comparison = {
                    "month": upload_month,
                    "mae": round(mae, 2),
                    "rmse": round(rmse, 2),
                    "mape": round(mape, 2),
                    "products": merged.to_dict(orient="records"),
                }

                comp_path = LOGS / f"comparison_{upload_month}.json"
                with open(comp_path, "w") as f:
                    json.dump(comparison, f, indent=2)
                self._update_comparisons_log(comparison)

        # ULTRA SPEED: Simplified data append
        base_path = DATA / "uploaded_data.csv"
        if base_path.exists():
            existing = self._safe_read_csv(base_path)
            existing["Date"] = pd.to_datetime(existing["Date"], dayfirst=True)
            existing_ym = existing["Date"].dt.to_period("M").astype(str)
            existing = existing[existing_ym != upload_month]
            combined = pd.concat([existing, df], ignore_index=True)
            sort_cols = [c for c in ["Store", "Product"] if c in combined.columns] + ["Date"]
            combined = combined.sort_values(sort_cols).reset_index(drop=True)
            combined["Date"] = combined["Date"].dt.strftime("%d-%m-%Y")
            combined.to_csv(base_path, index=False)
        else:
            save_df = df.copy()
            save_df["Date"] = save_df["Date"].dt.strftime("%d-%m-%Y")
            save_df.to_csv(base_path, index=False)

        self.state["last_upload_month"] = upload_month
        self._save_state()

        # ULTRA SPEED: Fast next prediction
        log.info("⚡ ULTRA SPEED: Generating next prediction...")
        next_prediction = self.predict_next_month(data_through_month=upload_month)

        log.info(f"⚡ ULTRA SPEED: Processed actuals for {upload_month}, predicted {next_prediction['prediction_month']}")

        return {
            "status": "success",
            "uploaded_month": upload_month,
            "rows_uploaded": len(df),
            "comparison": comparison,
            "next_prediction": next_prediction,
            "drift_analysis": self._analyze_drift(comparison) if comparison else None,
        }

    def _analyze_drift(self, comparison: dict) -> dict:
        """Analyze drift from comparison data."""
        if not comparison:
            return None
        
        mae = comparison.get("mae", 0)
        mape = comparison.get("mape", 0)
        
        # Get baseline MAE from training
        baseline_path = LOGS / "baseline_metrics.json"
        baseline_mae = 25.0  # Default baseline
        if baseline_path.exists():
            try:
                with open(baseline_path) as f:
                    baseline = json.load(f)
                    baseline_mae = baseline.get("train", {}).get("MAE", 25.0)
            except Exception:
                pass
        
        # Calculate drift severity
        error_increase = (mae - baseline_mae) / baseline_mae if baseline_mae > 0 else 0
        
        if error_increase < 0.1:  # <10% increase
            severity = "none"
            severity_label = "No Drift"
        elif error_increase < 0.5:  # 10-50% increase
            severity = "mild"
            severity_label = "Mild Drift"
        else:  # >50% increase
            severity = "severe"
            severity_label = "Severe Drift"
        
        return {
            "severity": severity,
            "severity_label": severity_label,
            "current_mae": round(mae, 2),
            "baseline_mae": round(baseline_mae, 2),
            "error_increase_pct": round(error_increase * 100, 1),
            "mape": round(mape, 2),
            "recommendation": self._get_drift_recommendation(severity),
        }
    
    def _get_drift_recommendation(self, severity: str) -> str:
        """Get recommendation based on drift severity."""
        if severity == "none":
            return "Model performance is stable. Continue monitoring."
        elif severity == "mild":
            return "Mild drift detected. Consider retraining if trend continues."
        else:
            return "Severe drift detected. Model retraining recommended."

    def get_drift_analysis(self) -> dict:
        """Get comprehensive drift analysis from recent comparisons."""
        comp_file = LOGS / "monthly_comparisons.json"
        if not comp_file.exists():
            return {"status": "no_data", "message": "No comparison data available"}
        
        try:
            with open(comp_file) as f:
                comparisons = json.load(f)
        except Exception:
            return {"status": "error", "message": "Failed to load comparison data"}
        
        if not comparisons:
            return {"status": "no_data", "message": "No comparison data available"}
        
        # Get baseline MAE
        baseline_path = LOGS / "baseline_metrics.json"
        baseline_mae = 25.0
        if baseline_path.exists():
            try:
                with open(baseline_path) as f:
                    baseline = json.load(f)
                    baseline_mae = baseline.get("train", {}).get("MAE", 25.0)
            except Exception:
                pass
        
        # Analyze each month
        drift_data = []
        for comp in sorted(comparisons, key=lambda x: x["month"]):
            mae = comp.get("mae", 0)
            error_increase = (mae - baseline_mae) / baseline_mae if baseline_mae > 0 else 0
            
            if error_increase < 0.1:
                severity = "none"
            elif error_increase < 0.5:
                severity = "mild"
            else:
                severity = "severe"
            
            drift_data.append({
                "month": comp["month"],
                "mae": round(mae, 2),
                "mape": round(comp.get("mape", 0), 2),
                "error_increase_pct": round(error_increase * 100, 1),
                "severity": severity,
            })
        
        # Overall analysis
        recent_months = drift_data[-3:] if len(drift_data) >= 3 else drift_data
        avg_error_increase = sum(d["error_increase_pct"] for d in recent_months) / len(recent_months)
        
        if avg_error_increase < 10:
            overall_severity = "none"
        elif avg_error_increase < 50:
            overall_severity = "mild"
        else:
            overall_severity = "severe"
        
        return {
            "status": "success",
            "baseline_mae": round(baseline_mae, 2),
            "overall_severity": overall_severity,
            "avg_error_increase_pct": round(avg_error_increase, 1),
            "monthly_data": drift_data,
            "recommendation": self._get_drift_recommendation(overall_severity),
        }

    def _update_comparisons_log(self, comparison):
        log_file = LOGS / "monthly_comparisons.json"
        data = []
        if log_file.exists():
            try:
                with open(log_file) as f:
                    data = json.load(f)
            except (json.JSONDecodeError, ValueError):
                data = []
        data = [d for d in data if d.get("month") != comparison["month"]]
        data.append({
            "month": comparison["month"],
            "mae": comparison["mae"],
            "rmse": comparison["rmse"],
            "mape": comparison["mape"],
            "timestamp": datetime.now().isoformat(),
        })
        data.sort(key=lambda x: x["month"])
        with open(log_file, "w") as f:
            json.dump(data, f, indent=2)

    # ── Status ────────────────────────────────────────────────────────────
    def get_status(self) -> dict:
        self._load_state()
        try:
            all_data = self._load_all_data()
            last_date = all_data["Date"].max()
            first_date = all_data["Date"].min()
            last_data_month = last_date.to_period("M").strftime("%Y-%m")
            total_rows = len(all_data)
            stores = int(all_data["Store"].nunique()) if "Store" in all_data.columns else 0
            products = int(all_data["Product"].nunique()) if "Product" in all_data.columns else 0
            columns = list(all_data.columns)
        except Exception:
            last_data_month = None
            total_rows = 0
            stores = 0
            products = 0
            first_date = last_date = None
            columns = []

        last_pred = self.state.get("last_prediction_month")
        last_upload = self.state.get("last_upload_month")

        if last_pred and last_pred != last_upload:
            waiting_for = last_pred
            next_action = f"Upload {last_pred} actual data"
        elif last_data_month:
            next_pred = self._next_month(last_data_month)
            waiting_for = None
            next_action = f"Predict {next_pred}"
        else:
            waiting_for = None
            next_action = "Run initial pipeline"

        comparisons = []
        comp_file = LOGS / "monthly_comparisons.json"
        if comp_file.exists():
            try:
                with open(comp_file) as f:
                    comparisons = json.load(f)
            except Exception:
                pass

        pred_files = sorted(PREDICTIONS.glob("????-??_predictions.csv"))
        available_predictions = [f.stem.replace("_predictions", "") for f in pred_files]

        return {
            "model_loaded": self.model is not None,
            "last_prediction_month": last_pred,
            "last_upload_month": last_upload,
            "last_data_month": last_data_month,
            "train_end": self.state.get("train_end"),
            "test_end": self.state.get("test_end"),
            "data_range": f"{first_date.strftime('%Y-%m-%d') if first_date else '?'} to {last_date.strftime('%Y-%m-%d') if last_date else '?'}",
            "total_rows": total_rows,
            "stores": stores,
            "products": products,
            "columns": columns,
            "waiting_for_upload": waiting_for,
            "next_action": next_action,
            "comparisons": comparisons,
            "available_predictions": available_predictions,
        }

    def get_prediction(self, month: str) -> dict:
        pred_path = PREDICTIONS / f"{month}_predictions.csv"
        if not pred_path.exists():
            return None
        df = pd.read_csv(pred_path)
        return {
            "month": month,
            "count": len(df),
            "mean_predicted": round(float(df["Predicted_Demand"].mean()), 2),
            "predictions": df.to_dict(orient="records"),
        }

    def get_comparison(self, month: str) -> dict:
        comp_path = LOGS / f"comparison_{month}.json"
        if not comp_path.exists():
            return None
        with open(comp_path) as f:
            return json.load(f)
