import os
import pandas as pd
import numpy as np
from datetime import datetime
from data_loader import DataLoader
from feature_engineering import FeatureEngineer
from model_trainer import ModelTrainer
from drift_detector import DriftDetector
from fine_tuner import FineTuner
from healing_status import HealingStatusIndicator
from log_book import LogBook
from database import DriftDatabase
from logger import get_logger

log = get_logger(__name__)


class Phase1Config:
    train_months = 12
    data_path = "data/uploaded_data.csv"
    min_month_rows = 2
    min_train_rows = 20


class Phase1Pipeline:
    def __init__(self):
        self.config = Phase1Config()
        self.loader = DataLoader(self.config.data_path)
        self.engineer = FeatureEngineer()
        self.trainer = ModelTrainer()
        self.detector = DriftDetector()
        self.fine_tuner = None
        self.status_indicator = HealingStatusIndicator()
        self.logbook = LogBook()
        self.db = DriftDatabase()
        self.train_df = self.test_df = None
        self.feature_names = []
        self.drift_reports = []
        self.healing_actions = []
        self.summary = {}

    def _step(self, n, label, fn):
        t0 = datetime.now()
        log.info(f"[{n}/7] {label}")
        fn()
        log.info(f"[{n}/7] {label} done in {(datetime.now()-t0).seconds}s")

    def step1_load_data(self):
        self.loader.load_data()
        self.loader.inspect_data()

    def step2_split_data(self):
        """Split: Year 1 = Training, Year 2 = Testing."""
        self.train_df, self.test_df = self.loader.split_by_year()
        train_year = self.train_df["Date"].dt.year.iloc[0]
        test_year = self.test_df["Date"].dt.year.iloc[0]
        log.info(f"Train year: {train_year} | Test year: {test_year}")

    def step3_feature_engineering(self):
        self.train_df, self.feature_names = self.engineer.run_feature_pipeline(self.train_df, fit=True)
        self.test_df, _ = self.engineer.run_feature_pipeline(self.test_df, fit=False)
        # Save engineer state for sequential predictor
        self.engineer.save_state("models/feature_engineer.pkl")
        log.info(f"Features: {len(self.feature_names)} | Train rows: {len(self.train_df)} | Test rows: {len(self.test_df)}")

    def step4_train_model(self):
        X_train = self.train_df[self.feature_names]
        y_train = self.train_df["Demand"]
        if len(X_train) < 20:
            raise ValueError(f"Training set too small: {len(X_train)} rows. Check feature engineering dropna.")
        self.trainer.tune_hyperparameters(X_train, y_train)
        self.trainer.train(X_train, y_train)
        self.trainer.evaluate(X_train, y_train, split="train")
        self.trainer.save_model()
        self.trainer.save_metrics()
        rf = getattr(self.trainer, "_rf", self.trainer.model)
        if hasattr(rf, "feature_importances_"):
            self.detector.set_feature_importance(rf, self.feature_names)
        ci = self.trainer.evaluate_with_intervals(X_train, y_train.values)
        self.summary["confidence_intervals"] = {"coverage": ci["coverage"], "avg_width": ci["avg_interval_width"]}
        train_preds = self.trainer.model.predict(X_train)
        self.detector.set_baseline(X_train, errors=(y_train.values - train_preds))
        self.logbook.log_training(self.trainer.metrics, self.trainer.best_params or {}, len(self.feature_names))
        self.db.save_model_version(self.trainer.version or "v1", self.trainer.metrics,
                                   self.feature_names, "models/active_model.pkl")
        if hasattr(rf, "feature_importances_"):
            self.db.save_feature_importance(self.trainer.version or "v1",
                dict(zip(self.feature_names, rf.feature_importances_)))

    def step5_simulate_months(self):
        self.test_df["YearMonth"] = self.test_df["Date"].dt.to_period("M")
        months = sorted(self.test_df["YearMonth"].unique())
        log.info(f"Simulating {len(months)} months...")
        os.makedirs("processed", exist_ok=True)
        
        # Initialize fine-tuner after model training
        if self.fine_tuner is None:
            self.fine_tuner = FineTuner(self.trainer.model, self.feature_names)
        
        for month in months:
            month_df = self.test_df[self.test_df["YearMonth"] == month]
            if len(month_df) < self.config.min_month_rows:
                log.warning(f"Skipping {month}: only {len(month_df)} rows")
                continue
            X = month_df[self.feature_names]
            y = month_df["Demand"].values
            stores = month_df["Store"].values if "Store" in month_df.columns else None
            products = month_df["Product"].values if "Product" in month_df.columns else None
            preds = self.trainer.model.predict(X)
            _, lower, upper = self.trainer.predict_with_confidence(X)
            self.logbook.log_batch_predictions(str(month), preds.tolist(), y.tolist(), stores, products)
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            out = pd.DataFrame({
                "Store":        stores if stores is not None else range(len(y)),
                "Product":      products if products is not None else range(len(y)),
                "Date":         month_df["Date"].dt.strftime("%Y-%m-%d").values,
                "Demand":       y,
                "Predicted":    preds.round(2),
                "CI_Lower":     lower.round(2),
                "CI_Upper":     upper.round(2),
                "Abs_Error":    np.abs(y - preds).round(2),
                "Error_Pct":    (np.abs(y - preds) / (np.abs(y) + 1e-9) * 100).round(2),
            })
            out.to_csv(f"processed/predictions_{month}_{ts}.csv", index=False)
            report = self.detector.comprehensive_detection(X, y - preds)
            report["month"] = str(month)
            self.drift_reports.append(report)
            self.logbook.log_drift_detection(str(month), report)
            self.db.save_drift_log(str(month), report)
            
            # Apply healing action based on drift severity
            severity = report.get("severity", "none")
            if severity == "none":
                self.status_indicator.start_monitoring(month)
                action = {"action": "monitor", "improvement": 0, "model_updated": False}
                log.info(f"  {month}: MONITOR (low drift)")
            elif severity in ["mild", "severe"]:
                self.status_indicator.start_fine_tune(month)
                split_idx = max(1, len(X) // 2)
                X_train_ft, X_val_ft = X.iloc[:split_idx], X.iloc[split_idx:]
                y_train_ft, y_val_ft = y[:split_idx], y[split_idx:]
                action = self.fine_tuner.decide_healing_action(
                    report, X_train_ft, y_train_ft, X_val_ft, y_val_ft,
                    X_train_full=self.train_df[self.feature_names].values,
                    y_train_full=self.train_df["Demand"].values
                )
                self.status_indicator.fine_tune_complete(action.get("improvement", 0), action["model_updated"])
                log.info(f"  {month}: FINE-TUNE | Improvement: {action.get('improvement', 0)*100:.1f}%")
            self.healing_actions.append(action)
            self.logbook.log_healing_action(str(month), action)

    def step6_generate_summary(self):
        severities = [r["severity"] for r in self.drift_reports]
        if "severe" in severities:
            final_severity, recommendation = "severe", "Severe drift detected: Fine-tuning applied"
        elif "mild" in severities:
            final_severity, recommendation = "mild", "Mild drift detected: Fine-tuning applied"
        else:
            final_severity, recommendation = "none", "No action needed: Model is stable"
        
        # Healing statistics
        healing_stats = {
            "total_actions": len(self.healing_actions),
            "monitor_only": sum(1 for a in self.healing_actions if a["action"] == "monitor"),
            "fine_tuned": sum(1 for a in self.healing_actions if a["action"] == "fine_tune"),
            "rollbacks": sum(1 for a in self.healing_actions if a["action"] == "rollback"),
        }
        avg_improvement = np.mean([a.get("improvement", 0) for a in self.healing_actions]) if self.healing_actions else 0.0
        
        self.summary.update({
            "timestamp": datetime.now().isoformat(),
            "final_severity": final_severity,
            "recommendation": recommendation,
            "months_monitored": len(self.drift_reports),
            "severity_counts": {s: severities.count(s) for s in ["severe", "mild", "none"]},
            "healing_stats": healing_stats,
            "avg_improvement": round(avg_improvement, 4),
            "train_metrics": self.trainer.metrics.get("train", {}),
            "feature_names": self.feature_names,
        })
        log.info(f"Final Severity: {final_severity.upper()} | {recommendation}")
        log.info(f"Healing Summary: {healing_stats}")
        return self.summary

    def step7_save_results(self):
        self.logbook.log_phase1_completion(self.summary)
        # Save healed model if any healing actions were taken
        if self.healing_actions and any(a["model_updated"] for a in self.healing_actions):
            self.fine_tuner.save_healed_model()
            log.info(f"Healed model saved after {len(self.healing_actions)} healing actions")
        log.info("All results saved")

    def step8_first_prediction(self):
        """After train+test, predict the first future month."""
        try:
            from sequential_predictor import SequentialPredictor
            sp = SequentialPredictor()
            # Data goes through the last test month
            last_date = self.test_df["Date"].max()
            last_month = last_date.to_period("M").strftime("%Y-%m")
            result = sp.predict_next_month(data_through_month=last_month)
            # Save train/test boundaries in state
            sp.state["train_end"] = self.train_df["Date"].max().strftime("%Y-%m")
            sp.state["test_end"] = last_month
            sp._save_state()
            log.info(f"First prediction: {result['prediction_month']} ({result['count']} rows)")
        except Exception as e:
            log.warning(f"First prediction skipped: {e}")

    def run_phase1(self):
        log.info("=" * 60)
        log.info("PHASE 1: SELF-HEALING DEMAND FORECASTING SYSTEM")
        log.info("=" * 60)
        start = datetime.now()
        steps = [
            (1, "Loading data",          self.step1_load_data),
            (2, "Splitting data",         self.step2_split_data),
            (3, "Feature engineering",    self.step3_feature_engineering),
            (4, "Training model",         self.step4_train_model),
            (5, "Simulating months",      self.step5_simulate_months),
            (6, "Generating summary",     self.step6_generate_summary),
            (7, "Saving results",         self.step7_save_results),
            (8, "First future prediction", self.step8_first_prediction),
        ]
        for n, label, fn in steps:
            try:
                self._step(n, label, fn)
            except Exception as e:
                log.error(f"Step {n} ({label}) failed: {e}")
                raise
        elapsed = (datetime.now() - start).seconds
        log.info(f"PHASE 1 COMPLETE in {elapsed}s")
        return self.summary
