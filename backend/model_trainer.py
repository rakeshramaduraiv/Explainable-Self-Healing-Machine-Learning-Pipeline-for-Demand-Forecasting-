import warnings, json, os
import numpy as np
import joblib
from datetime import datetime
from sklearn.ensemble import RandomForestRegressor, GradientBoostingRegressor
from sklearn.model_selection import RandomizedSearchCV, TimeSeriesSplit
from sklearn.metrics import mean_squared_error, mean_absolute_error, r2_score
from logger import get_logger

log = get_logger(__name__)

try:
    from xgboost import XGBRegressor
    _HAS_XGB = True
except ImportError:
    _HAS_XGB = False
    log.warning("XGBoost not installed — falling back to GradientBoosting")


class ModelTrainer:
    def __init__(self):
        self.model       = None
        self.best_params = {}
        self.metrics     = {}
        self.version     = ""
        self.version_history = []
        self._model_name = "XGB"

    def tune_hyperparameters(self, X_train, y_train):
        # EFFICIENT FULL DATASET: Optimized hyperparameter search on complete data
        X_arr = X_train.values if hasattr(X_train, "values") else X_train
        log.info(f"🎯 FULL DATASET TRAINING: Hyperparameter tuning on {len(X_arr):,} samples")
        
        if _HAS_XGB:
            # Speed-focused parameter grid
            param_dist = {
                "n_estimators": [100, 150],  # Reduced options
                "max_depth": [6, 8],         # Reduced options
                "learning_rate": [0.1, 0.15], # Reduced options
                "subsample": [0.8],           # Single best value
                "colsample_bytree": [0.8],    # Single best value
                "min_child_weight": [3],      # Single best value
                "reg_alpha": [0.0],           # Single best value
                "reg_lambda": [1.0]           # Single best value
            }
            estimator = XGBRegressor(random_state=42, n_jobs=-1, verbosity=0, 
                                   tree_method='hist', max_bin=256)  # Faster binning
        else:
            param_dist = {
                "n_estimators": [100, 150],   # Reduced options
                "max_depth": [6, 8],          # Reduced options
                "min_samples_leaf": [2],      # Single best value
                "max_features": ["sqrt"]      # Single best value
            }
            estimator = GradientBoostingRegressor(random_state=42)

        # SPEED OPTIMIZED: Use a representative sample for tuning to save time
        # For 500k+ rows, 50k is usually enough to find good hyperparameters
        tune_size = min(len(X_arr), 50_000)
        indices = np.random.choice(len(X_arr), tune_size, replace=False)
        X_tune, y_tune = X_arr[indices], y_train.iloc[indices] if hasattr(y_train, "iloc") else y_train[indices]

        cv = TimeSeriesSplit(n_splits=2)
        # n_iter=5 is plenty for this small grid
        search = RandomizedSearchCV(
            estimator, param_dist, n_iter=5, cv=cv,
            scoring='neg_mean_absolute_error', n_jobs=-1, random_state=42,
            verbose=1
        )
        
        log.info(f"🎯 SPEED TUNING: Tuning on {tune_size:,} samples (5 iterations)")
        search.fit(X_tune, y_tune)
        
        self.best_params = search.best_params_
        log.info(f"🎯 BEST PARAMETERS FOUND: {self.best_params}")
        log.info(f"🎯 Best CV Score: {-search.best_score_:.2f} MAE")
        return self.best_params

    def train(self, X_train, y_train):
        if len(X_train) < 20:
            raise ValueError(f"Training set too small ({len(X_train)} rows).")
        self._feature_names_in = list(X_train.columns) if hasattr(X_train, "columns") else None
        X_arr = X_train.values if hasattr(X_train, "values") else X_train
        y_arr = np.asarray(y_train)

        if _HAS_XGB:
            self._model_name = "XGB"  # Set model name first
            log.info(f"⚡ FULL DATASET TRAINING: {self._model_name} on {len(X_arr):,} samples with optimal params")
            model = XGBRegressor(**self.best_params, random_state=42, n_jobs=-1, verbosity=0, 
                               tree_method='hist', max_bin=256)  # Optimized for large datasets
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                model.fit(X_arr, y_arr)
        else:
            self._model_name = "GB"  # Set model name first
            log.info(f"⚡ FULL DATASET TRAINING: {self._model_name} on {len(X_arr):,} samples with optimal params")
            model = GradientBoostingRegressor(**self.best_params, random_state=42)
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                model.fit(X_arr, y_arr)

        # Speed-optimized Random Forest (used for confidence intervals)
        # Training RF on 500k+ samples is a massive bottleneck.
        # We use a 100k sample for RF to provide reliable intervals without blocking for 10+ minutes.
        rf_sample_size = min(len(X_arr), 100_000)
        rf_indices = np.random.choice(len(X_arr), rf_sample_size, replace=False)
        X_rf, y_rf = X_arr[rf_indices], y_arr[rf_indices]
        
        rf = RandomForestRegressor(n_estimators=30, max_depth=8, random_state=42, n_jobs=-1)
        log.info(f"🌲 Training Random Forest Confidence Model (30 trees) on {rf_sample_size:,} samples")
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            rf.fit(X_rf, y_rf)

        self.model = model
        self._rf   = rf
        if self._feature_names_in:
            self.model._feature_names_in = self._feature_names_in
        log.info(f"🎯 {self._model_name} FULL TRAINING completed - MAE:{mean_absolute_error(y_arr, model.predict(X_arr)):,.1f}")
        return self.model

    def evaluate(self, X, y, split="train"):
        if self.model is None:
            log.warning("Evaluate called but no model trained.")
            return {}
        preds    = self.model.predict(X)
        y_arr    = np.asarray(y)
        rmse     = round(float(np.sqrt(mean_squared_error(y_arr, preds))))
        mae      = round(float(mean_absolute_error(y_arr, preds)))
        r2       = round(float(r2_score(y_arr, preds)) * 100)
        mask     = (y_arr != 0)
        mape     = round(float(np.mean(np.abs((y_arr[mask] - preds[mask]) / y_arr[mask])) * 100)) if np.any(mask) else 0
        wmape    = round(float(np.sum(np.abs(y_arr - preds)) / (np.sum(np.abs(y_arr)) + 1e-9) * 100))
        accuracy = 100 - mape
        self.metrics[split] = {
            "RMSE": rmse, "MAE": mae, "R2": r2,
            "MAPE": mape, "WMAPE": wmape, "Accuracy": accuracy,
            "model": getattr(self, "_model_name", "XGB")
        }
        log.info(f"{split} → RMSE:{rmse} MAE:{mae} R²:{r2}% MAPE:{mape}% Accuracy:{accuracy}%")
        return self.metrics[split]

    def predict_with_confidence(self, X, confidence=0.95):
        rf = getattr(self, "_rf", None)
        X_arr = X.values if hasattr(X, "values") else X
        mean_pred = self.model.predict(X_arr)
        if rf is not None and hasattr(rf, "estimators_"):
            tree_preds = np.array([t.predict(X_arr) for t in rf.estimators_])
            std_pred = np.std(tree_preds, axis=0)
        else:
            std_pred = np.abs(mean_pred) * 0.1
        z = 1.96
        lower = np.maximum(mean_pred - z * std_pred, 0)
        upper = mean_pred + z * std_pred
        return mean_pred, lower, upper

    def evaluate_with_intervals(self, X, y):
        mean_pred, lower, upper = self.predict_with_confidence(X)
        coverage  = float(((y >= lower) & (y <= upper)).mean())
        avg_width = float((upper - lower).mean())
        log.info(f"CI Coverage:{coverage:.2%} | Avg Width:{avg_width:,.0f}")
        return {"coverage": coverage, "avg_interval_width": avg_width,
                "lower": lower.tolist(), "upper": upper.tolist()}

    def save_model(self, path="models/active_model.pkl"):
        os.makedirs("models", exist_ok=True)
        os.makedirs("logs",   exist_ok=True)
        self.version = datetime.now().strftime("v1_%Y%m%d_%H%M%S")
        joblib.dump(self.model, path)
        joblib.dump(getattr(self, "_rf", self.model), "models/baseline_model_rf.pkl")
        joblib.dump(self.model, f"models/model_{self.version}.pkl")
        self.version_history.append(self.version)
        meta = {"version": self.version, "saved_at": datetime.now().isoformat(),
                "params": self.best_params or {}, "metrics": self.metrics,
                "model_type": getattr(self, "_model_name", "XGB")}
        with open(f"logs/model_{self.version}_meta.json", "w") as f:
            json.dump(meta, f, indent=2)
        log.info(f"Model saved: {path} | Version:{self.version} | Type:{meta['model_type']}")

    def save_metrics(self, path="logs/baseline_metrics.json"):
        with open(path, "w") as f:
            json.dump(self.metrics, f, indent=2)
        log.info(f"Metrics saved: {path}")
