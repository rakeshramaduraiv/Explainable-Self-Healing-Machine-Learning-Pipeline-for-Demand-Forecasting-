import warnings
import numpy as np
import joblib
from datetime import datetime
from sklearn.ensemble import RandomForestRegressor, GradientBoostingRegressor
from sklearn.metrics import mean_absolute_error, r2_score
from logger import get_logger

log = get_logger(__name__)


class FineTuner:
    """
    Three-tier healing strategy based on drift severity:
    1. Low Drift (KS < 0.05): Continue monitoring, no action
    2. Mild Drift (KS 0.05-0.15): Fine-tune with warm start (add trees)
    3. Severe Drift (KS > 0.2): Full retrain on 12-month rolling window
    """

    def __init__(self, base_model, feature_names):
        self.base_model = base_model
        self.feature_names = feature_names
        self.healing_history = []

    def _validate_improvement(self, old_mae, new_mae, threshold=0.05):
        """Check if new model improves by at least threshold (5%)"""
        improvement = (old_mae - new_mae) / (old_mae + 1e-9)
        return improvement >= threshold, improvement

    def monitor_only(self, drift_report):
        """Tier 1: No action, continue monitoring"""
        log.info("Tier 1 (Monitor): No drift action required")
        return {
            "action": "monitor",
            "severity": drift_report["severity"],
            "reason": "Low drift detected",
            "model_updated": False,
            "improvement": 0.0,
        }

    def fine_tune_warm_start(self, X_current, y_current, X_val, y_val, drift_report):
        """
        Tier 2: Fine-tune with warm start
        Add trees proportional to drift magnitude to existing model
        """
        log.info("Tier 2 (Fine-tune): Warm start with additional trees")

        # Calculate drift magnitude (0-1 scale)
        ks_max = max(
            [v.get("statistic", 0) for v in drift_report.get("ks_results", {}).values()],
            default=0.1,
        )
        drift_magnitude = min(ks_max / 0.2, 1.0)  # Normalize to 0-1

        # Determine trees to add (10-50 trees based on drift)
        trees_to_add = int(10 + drift_magnitude * 40)

        try:
            # Clone base model and add trees
            if isinstance(self.base_model, RandomForestRegressor):
                new_model = RandomForestRegressor(
                    n_estimators=self.base_model.n_estimators + trees_to_add,
                    max_depth=self.base_model.max_depth,
                    min_samples_split=self.base_model.min_samples_split,
                    min_samples_leaf=self.base_model.min_samples_leaf,
                    max_features=self.base_model.max_features,
                    random_state=42,
                    n_jobs=-1,
                    warm_start=True,
                )
                # Warm start: fit on combined data
                X_combined = np.vstack([X_current, X_val])
                y_combined = np.hstack([y_current, y_val])
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore")
                    new_model.fit(X_combined, y_combined)

            elif isinstance(self.base_model, GradientBoostingRegressor):
                new_model = GradientBoostingRegressor(
                    n_estimators=self.base_model.n_estimators + trees_to_add,
                    learning_rate=self.base_model.learning_rate,
                    max_depth=self.base_model.max_depth,
                    subsample=self.base_model.subsample,
                    min_samples_leaf=self.base_model.min_samples_leaf,
                    random_state=42,
                )
                X_combined = np.vstack([X_current, X_val])
                y_combined = np.hstack([y_current, y_val])
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore")
                    new_model.fit(X_combined, y_combined)
            else:
                log.warning("Model type not supported for warm start, skipping fine-tune")
                return {
                    "action": "monitor",
                    "severity": drift_report["severity"],
                    "reason": "Model type not supported for warm start",
                    "model_updated": False,
                    "improvement": 0.0,
                }

            # Validate on holdout
            old_mae = mean_absolute_error(y_val, self.base_model.predict(X_val))
            new_mae = mean_absolute_error(y_val, new_model.predict(X_val))
            improved, improvement = self._validate_improvement(old_mae, new_mae)

            if improved:
                log.info(
                    f"Fine-tune successful: MAE {old_mae:.0f} → {new_mae:.0f} "
                    f"({improvement*100:.1f}% improvement)"
                )
                self.base_model = new_model
                return {
                    "action": "fine_tune",
                    "severity": drift_report["severity"],
                    "trees_added": trees_to_add,
                    "old_mae": round(old_mae, 2),
                    "new_mae": round(new_mae, 2),
                    "improvement": round(improvement, 4),
                    "model_updated": True,
                }
            else:
                log.info(
                    f"Fine-tune did not improve: MAE {old_mae:.0f} → {new_mae:.0f} "
                    f"({improvement*100:.1f}% change). Rollback."
                )
                return {
                    "action": "rollback",
                    "severity": drift_report["severity"],
                    "reason": f"Fine-tune improvement {improvement*100:.1f}% < 5% threshold",
                    "model_updated": False,
                    "improvement": improvement,
                }

        except Exception as e:
            log.error(f"Fine-tune failed: {e}")
            return {
                "action": "rollback",
                "severity": drift_report["severity"],
                "reason": f"Fine-tune error: {str(e)}",
                "model_updated": False,
                "improvement": 0.0,
            }

    def full_retrain(self, X_train, y_train, X_val, y_val, drift_report):
        """
        Tier 3: Full retrain on 12-month rolling window
        Complete retraining with hyperparameter tuning
        """
        log.info("Tier 3 (Retrain): Full model retraining on rolling window")

        try:
            if isinstance(self.base_model, RandomForestRegressor):
                new_model = RandomForestRegressor(
                    n_estimators=500,
                    max_depth=30,
                    min_samples_split=5,
                    min_samples_leaf=2,
                    max_features=0.7,
                    random_state=42,
                    n_jobs=-1,
                )
            elif isinstance(self.base_model, GradientBoostingRegressor):
                new_model = GradientBoostingRegressor(
                    n_estimators=300,
                    learning_rate=0.03,
                    max_depth=5,
                    subsample=0.8,
                    min_samples_leaf=2,
                    random_state=42,
                )
            else:
                log.warning("Model type not supported for retrain")
                return {
                    "action": "monitor",
                    "severity": drift_report["severity"],
                    "reason": "Model type not supported for retrain",
                    "model_updated": False,
                    "improvement": 0.0,
                }

            # Retrain on combined data
            X_combined = np.vstack([X_train, X_val])
            y_combined = np.hstack([y_train, y_val])

            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                new_model.fit(X_combined, y_combined)

            # Validate on holdout (use validation set as test)
            old_mae = mean_absolute_error(y_val, self.base_model.predict(X_val))
            new_mae = mean_absolute_error(y_val, new_model.predict(X_val))
            improved, improvement = self._validate_improvement(old_mae, new_mae)

            if improved:
                log.info(
                    f"Retrain successful: MAE {old_mae:.0f} → {new_mae:.0f} "
                    f"({improvement*100:.1f}% improvement)"
                )
                self.base_model = new_model
                return {
                    "action": "retrain",
                    "severity": drift_report["severity"],
                    "train_samples": len(X_combined),
                    "old_mae": round(old_mae, 2),
                    "new_mae": round(new_mae, 2),
                    "improvement": round(improvement, 4),
                    "model_updated": True,
                }
            else:
                log.info(
                    f"Retrain did not improve: MAE {old_mae:.0f} → {new_mae:.0f} "
                    f"({improvement*100:.1f}% change). Rollback."
                )
                return {
                    "action": "rollback",
                    "severity": drift_report["severity"],
                    "reason": f"Retrain improvement {improvement*100:.1f}% < 5% threshold",
                    "model_updated": False,
                    "improvement": improvement,
                }

        except Exception as e:
            log.error(f"Retrain failed: {e}")
            return {
                "action": "rollback",
                "severity": drift_report["severity"],
                "reason": f"Retrain error: {str(e)}",
                "model_updated": False,
                "improvement": 0.0,
            }

    def decide_healing_action(self, drift_report, X_current, y_current, X_val, y_val, X_train=None, y_train=None):
        """
        Decide which healing action to take based on drift severity
        Returns action dict and updated model
        """
        severity = drift_report.get("severity", "none")
        ks_max = max(
            [v.get("statistic", 0) for v in drift_report.get("ks_results", {}).values()],
            default=0.0,
        )

        action_result = None

        if severity == "none" or ks_max < 0.05:
            # Tier 1: Monitor only
            action_result = self.monitor_only(drift_report)

        elif severity == "mild" or (0.05 <= ks_max < 0.2):
            # Tier 2: Fine-tune with warm start
            action_result = self.fine_tune_warm_start(X_current, y_current, X_val, y_val, drift_report)

        elif severity == "severe" or ks_max >= 0.2:
            # Tier 3: Full retrain
            if X_train is not None and y_train is not None:
                action_result = self.full_retrain(X_train, y_train, X_val, y_val, drift_report)
            else:
                log.warning("Training data not available for full retrain, attempting fine-tune instead")
                action_result = self.fine_tune_warm_start(X_current, y_current, X_val, y_val, drift_report)

        action_result["timestamp"] = datetime.now().isoformat()
        self.healing_history.append(action_result)

        return action_result

    def get_healing_history(self):
        """Return all healing actions taken"""
        return self.healing_history

    def save_healed_model(self, path="models/active_model.pkl"):
        """Save the (possibly updated) model"""
        joblib.dump(self.base_model, path)
        log.info(f"Healed model saved to {path}")
        return path
