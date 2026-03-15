import numpy as np
import joblib
from pathlib import Path
from sklearn.ensemble import RandomForestRegressor, GradientBoostingRegressor
from logger import get_logger

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
        - Low drift (KS < 0.05): Monitor only
        - Mild drift (KS 0.05-0.15): Fine-tune
        - Severe drift (KS > 0.15): Retrain
        """
        severity = drift_report.get("severity", "none")
        ks_stat = drift_report.get("ks_statistic", 0)
        
        if severity == "none" or ks_stat < 0.05:
            return {"action": "monitor", "improvement": 0, "model_updated": False}
        
        elif severity == "mild" or (0.05 <= ks_stat < 0.15):
            return self._fine_tune(X_train, y_train, X_val, y_val)
        
        elif severity == "severe" or ks_stat >= 0.15:
            return self._retrain(X_train, y_train, X_val, y_val, X_train_full, y_train_full)
        
        return {"action": "monitor", "improvement": 0, "model_updated": False}

    def _fine_tune(self, X_train, y_train, X_val, y_val):
        """Fine-tune: Add trees to existing model"""
        try:
            log.info("🔧 Fine-tuning: Adding trees to existing model...")
            
            # Get baseline validation error
            baseline_pred = self.model.predict(X_val)
            baseline_mae = np.mean(np.abs(y_val - baseline_pred))
            
            # Clone model and add trees
            if isinstance(self.model, RandomForestRegressor):
                n_estimators_add = max(10, int(self.model.n_estimators * 0.2))  # Add 20%
                self.model.n_estimators += n_estimators_add
                self.model.fit(X_train, y_train)
            elif isinstance(self.model, GradientBoostingRegressor):
                n_estimators_add = max(5, int(self.model.n_estimators * 0.15))  # Add 15%
                self.model.n_estimators += n_estimators_add
                self.model.fit(X_train, y_train)
            else:
                self.model.fit(X_train, y_train)
            
            # Validate improvement
            new_pred = self.model.predict(X_val)
            new_mae = np.mean(np.abs(y_val - new_pred))
            improvement = (baseline_mae - new_mae) / (baseline_mae + 1e-9)
            
            if improvement >= self.improvement_threshold:
                log.info(f"✅ Fine-tune successful: {improvement*100:.1f}% improvement")
                self.healed_model = self.model
                return {"action": "fine_tune", "improvement": improvement, "model_updated": True}
            else:
                log.info(f"⚠️ Fine-tune improvement {improvement*100:.1f}% < threshold, rolling back")
                return {"action": "rollback", "improvement": 0, "model_updated": False}
        
        except Exception as e:
            log.error(f"❌ Fine-tune failed: {e}")
            return {"action": "monitor", "improvement": 0, "model_updated": False}

    def _retrain(self, X_train, y_train, X_val, y_val, X_train_full=None, y_train_full=None):
        """Retrain: Create new model with optimized hyperparameters"""
        try:
            log.info("🔄 Retraining: Creating new model...")
            
            # Get baseline validation error
            baseline_pred = self.model.predict(X_val)
            baseline_mae = np.mean(np.abs(y_val - baseline_pred))
            
            # Create new model with optimized params
            if isinstance(self.model, RandomForestRegressor):
                new_model = RandomForestRegressor(
                    n_estimators=500,
                    max_depth=15,
                    min_samples_split=5,
                    min_samples_leaf=2,
                    random_state=42,
                    n_jobs=-1
                )
            elif isinstance(self.model, GradientBoostingRegressor):
                new_model = GradientBoostingRegressor(
                    n_estimators=300,
                    learning_rate=0.05,
                    max_depth=5,
                    min_samples_split=5,
                    min_samples_leaf=2,
                    random_state=42
                )
            else:
                new_model = self.model.__class__(**self.model.get_params())
            
            # Train on combined data if available
            if X_train_full is not None and y_train_full is not None:
                new_model.fit(X_train_full, y_train_full)
            else:
                new_model.fit(X_train, y_train)
            
            # Validate improvement
            new_pred = new_model.predict(X_val)
            new_mae = np.mean(np.abs(y_val - new_pred))
            improvement = (baseline_mae - new_mae) / (baseline_mae + 1e-9)
            
            if improvement >= self.improvement_threshold:
                log.info(f"✅ Retrain successful: {improvement*100:.1f}% improvement")
                self.model = new_model
                self.healed_model = new_model
                return {"action": "retrain", "improvement": improvement, "model_updated": True}
            else:
                log.info(f"⚠️ Retrain improvement {improvement*100:.1f}% < threshold, keeping old model")
                return {"action": "monitor", "improvement": 0, "model_updated": False}
        
        except Exception as e:
            log.error(f"❌ Retrain failed: {e}")
            return {"action": "monitor", "improvement": 0, "model_updated": False}

    def save_healed_model(self):
        """Save the healed model"""
        if self.healed_model is not None:
            MODELS.mkdir(exist_ok=True)
            path = MODELS / "active_model.pkl"
            joblib.dump(self.healed_model, str(path))
            log.info(f"💾 Healed model saved to {path}")
