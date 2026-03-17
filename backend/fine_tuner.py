import warnings
import numpy as np
import joblib
from pathlib import Path
from sklearn.ensemble import RandomForestRegressor, GradientBoostingRegressor
from logger import get_logger

try:
    from xgboost import XGBRegressor
    _HAS_XGB = True
except ImportError:
    _HAS_XGB = False

log = get_logger(__name__)

BASE = Path(__file__).parent.resolve()
MODELS = BASE / "models"


class FineTuner:
    def __init__(self, model, feature_names):
        self.model = model
        self.feature_names = feature_names
        self.improvement_threshold = 0.05  # 5% improvement required
        self.healed_model = None

    def decide_healing_action(self, drift_report, X_train, y_train, X_val, y_val, X_train_full=None, y_train_full=None):
        """
        Decide healing action based on drift severity:
        - none: Monitor only
        - mild/severe: Fine-tune
        """
        severity = drift_report.get("severity", "none")
        
        if severity == "none":
            return {"action": "monitor", "improvement": 0, "model_updated": False}
        
        return self._fine_tune(X_train, y_train, X_val, y_val)

    def _fine_tune(self, X_train, y_train, X_val, y_val):
        """Fine-tune: Add trees to existing model"""
        try:
            log.info("Fine-tuning: Adding trees to existing model...")
            X_tr = X_train.values if hasattr(X_train, 'values') else X_train
            X_v = X_val.values if hasattr(X_val, 'values') else X_val

            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                baseline_pred = self.model.predict(X_v)
            baseline_mae = np.mean(np.abs(y_val - baseline_pred))

            if isinstance(self.model, RandomForestRegressor):
                self.model.n_estimators += max(10, int(self.model.n_estimators * 0.2))
                self.model.fit(X_tr, y_train)
            elif isinstance(self.model, GradientBoostingRegressor):
                self.model.n_estimators += max(5, int(self.model.n_estimators * 0.15))
                self.model.fit(X_tr, y_train)
            elif _HAS_XGB and isinstance(self.model, XGBRegressor):
                self.model.n_estimators += max(10, int(self.model.n_estimators * 0.2))
                self.model.fit(X_tr, y_train)
            else:
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore")
                    self.model.fit(X_tr, y_train)

            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                new_pred = self.model.predict(X_v)
            new_mae = np.mean(np.abs(y_val - new_pred))
            improvement = (baseline_mae - new_mae) / (baseline_mae + 1e-9)

            if improvement >= self.improvement_threshold:
                log.info(f"Fine-tune successful: {improvement*100:.1f}% improvement")
                self.healed_model = self.model
                return {"action": "fine_tune", "improvement": improvement, "model_updated": True}
            else:
                log.info(f"Fine-tune improvement {improvement*100:.1f}% < threshold, rolling back")
                return {"action": "rollback", "improvement": 0, "model_updated": False}

        except Exception as e:
            log.error(f"Fine-tune failed: {e}")
            return {"action": "monitor", "improvement": 0, "model_updated": False}



    def save_healed_model(self):
        """Save the healed model"""
        if self.healed_model is not None:
            MODELS.mkdir(exist_ok=True)
            path = MODELS / "active_model.pkl"
            joblib.dump(self.healed_model, str(path))
            log.info(f"💾 Healed model saved to {path}")
