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
        self.best_params = None
        self.metrics     = {}
        self.version     = None
        self.version_history = []

    def tune_hyperparameters(self, X_train, y_train):
        X_arr    = X_train.values if hasattr(X_train, "values") else X_train
        n_splits = min(5, max(3, len(X_arr) // 5000))
        tscv     = TimeSeriesSplit(n_splits=n_splits)

        if _HAS_XGB:
            param_dist = {
                "n_estimators":     [300, 500, 700],
                "max_depth":        [4, 6, 8],
                "learning_rate":    [0.01, 0.05, 0.1],
                "subsample":        [0.7, 0.8, 0.9],
                "colsample_bytree": [0.6, 0.7, 0.8],
                "min_child_weight": [3, 5, 10],
                "reg_alpha":        [0.0, 0.5, 1.0],
                "reg_lambda":       [1.0, 2.0, 5.0],
            }
            estimator = XGBRegressor(random_state=42, n_jobs=-1, verbosity=0)
        else:
            param_dist = {
                "n_estimators":     [100, 200, 300],
                "max_depth":        [6, 10, None],
                "min_samples_leaf": [2, 3, 5],
                "max_features":     ["sqrt", 0.5, 0.7],
            }
            estimator = GradientBoostingRegressor(random_state=42)

        search = RandomizedSearchCV(
            estimator, param_dist, n_iter=10,
            cv=tscv, scoring="neg_mean_absolute_error",
            random_state=42, n_jobs=-1
        )
        log.info(f"Tuning {estimator.__class__.__name__} — {n_splits}-fold CV, 10 iterations...")
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            search.fit(X_arr, y_train)
        self.best_params = search.best_params_
        log.info(f"Best params (CV MAE={-search.best_score_:,.2f}): {self.best_params}")
        return self.best_params

    def train(self, X_train, y_train):
        if len(X_train) < 20:
            raise ValueError(f"Training set too small ({len(X_train)} rows).")
        self._feature_names_in = list(X_train.columns) if hasattr(X_train, "columns") else None
        X_arr = X_train.values if hasattr(X_train, "values") else X_train
        y_arr = np.asarray(y_train)

        if _HAS_XGB:
            log.info(f"Training XGBoost with tuned params: {self.best_params}")
            model = XGBRegressor(**self.best_params, random_state=42, n_jobs=-1, verbosity=0)
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                model.fit(X_arr, y_arr)
            self._model_name = "XGB"
        else:
            log.info(f"Training GradientBoosting with tuned params: {self.best_params}")
            model = GradientBoostingRegressor(**self.best_params, random_state=42)
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                model.fit(X_arr, y_arr)
            self._model_name = "GB"

        # RF for confidence intervals
        rf = RandomForestRegressor(n_estimators=100, max_depth=10, random_state=42, n_jobs=-1)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            rf.fit(X_arr, y_arr)

        self.model = model
        self._rf   = rf
        if self._feature_names_in:
            self.model._feature_names_in = self._feature_names_in
        log.info(f"{self._model_name} MAE:{mean_absolute_error(y_arr, model.predict(X_arr)):,.1f}")
        return self.model

    def evaluate(self, X, y, split="train"):
        preds    = self.model.predict(X)
        y_arr    = np.asarray(y)
        rmse     = round(float(np.sqrt(mean_squared_error(y_arr, preds))))
        mae      = round(float(mean_absolute_error(y_arr, preds)))
        r2       = round(float(r2_score(y_arr, preds)) * 100)
        mask     = y_arr != 0
        mape     = round(float(np.mean(np.abs((y_arr[mask] - preds[mask]) / y_arr[mask])) * 100)) if mask.any() else 0
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
        z     = {0.90: 1.645, 0.95: 1.96, 0.99: 2.576}.get(confidence, 1.96)
        rf    = getattr(self, "_rf", self.model)
        X_arr = X.values if hasattr(X, "values") else X
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            tree_preds = np.array([t.predict(X_arr) for t in rf.estimators_])
        mean_pred = np.mean(tree_preds, axis=0)
        std_pred  = np.std(tree_preds,  axis=0)
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
