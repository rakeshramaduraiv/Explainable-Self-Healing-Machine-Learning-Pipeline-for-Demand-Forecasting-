import warnings, json, os
import numpy as np
import joblib
from datetime import datetime
from sklearn.ensemble import RandomForestRegressor, GradientBoostingRegressor, StackingRegressor
from sklearn.linear_model import Ridge
from sklearn.model_selection import RandomizedSearchCV, TimeSeriesSplit
from sklearn.metrics import mean_squared_error, mean_absolute_error, r2_score
from logger import get_logger

log = get_logger(__name__)

try:
    from xgboost import XGBRegressor
    _HAS_XGB = True
except ImportError:
    _HAS_XGB = False
    log.warning("XGBoost not installed — falling back to RF+GB ensemble")


class ModelTrainer:
    def __init__(self):
        self.model       = None
        self.best_params = None
        self.metrics     = {}
        self.version     = None
        self.version_history = []

    def tune_hyperparameters(self, X_train, y_train):
        param_dist = {
            "n_estimators":          [200, 300, 500],
            "max_depth":             [None, 20, 30],
            "min_samples_split":     [2, 5],
            "min_samples_leaf":      [1, 2],
            "max_features":          ["sqrt", 0.5, 0.7],
            "min_impurity_decrease": [0.0, 1e-4],
        }
        n_splits = min(5, max(2, len(X_train) // 50))
        tscv = TimeSeriesSplit(n_splits=n_splits)
        search = RandomizedSearchCV(
            RandomForestRegressor(random_state=42, n_jobs=-1),
            param_dist, n_iter=min(20, len(X_train) // 20 + 5),
            cv=tscv, scoring="neg_mean_absolute_error",
            random_state=42, n_jobs=-1
        )
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            search.fit(X_train, y_train)
        self.best_params = search.best_params_
        log.info(f"Best RF params: {self.best_params}")
        return self.best_params

    def train(self, X_train, y_train):
        if len(X_train) < 20:
            raise ValueError(
                f"Training set too small ({len(X_train)} rows). "
                "Upload a dataset with more rows or a wider date range."
            )
        params = {k: v for k, v in (self.best_params or {}).items()
                  if k in RandomForestRegressor().get_params()}
        rf = RandomForestRegressor(**params, random_state=42, n_jobs=-1)
        gb = GradientBoostingRegressor(
            n_estimators=300, max_depth=5, learning_rate=0.03,
            subsample=0.8, min_samples_leaf=2,
            max_features=0.7, random_state=42
        )

        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            rf.fit(X_train, y_train)
            gb.fit(X_train, y_train)

        rf_mae = mean_absolute_error(y_train, rf.predict(X_train))
        gb_mae = mean_absolute_error(y_train, gb.predict(X_train))

        if _HAS_XGB and len(X_train) >= 100:
            xgb = XGBRegressor(
                n_estimators=300, max_depth=6, learning_rate=0.03,
                subsample=0.8, colsample_bytree=0.7,
                min_child_weight=3, reg_alpha=0.1, reg_lambda=1.0,
                random_state=42, n_jobs=-1, verbosity=0
            )
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                xgb.fit(X_train, y_train)
            xgb_mae = mean_absolute_error(y_train, xgb.predict(X_train))

            # Stacking: RF + GB + XGB → Ridge meta-learner
            # Need at least 2 splits, and each fold needs enough samples
            n_splits_stack = max(2, min(5, len(X_train) // 100))
            stack = StackingRegressor(
                estimators=[("rf", rf), ("gb", gb), ("xgb", xgb)],
                final_estimator=Ridge(alpha=1.0),
                cv=n_splits_stack,  # Use integer for simple KFold
                n_jobs=-1
            )
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                stack.fit(X_train, y_train)
            stack_mae = mean_absolute_error(y_train, stack.predict(X_train))

            best_mae   = min(rf_mae, gb_mae, xgb_mae, stack_mae)
            model_name = {rf_mae:"RF", gb_mae:"GB", xgb_mae:"XGB", stack_mae:"Stack"}[best_mae]
            self.model = {"RF":rf,"GB":gb,"XGB":xgb,"Stack":stack}[model_name]
            log.info(f"RF:{rf_mae:,.0f} GB:{gb_mae:,.0f} XGB:{xgb_mae:,.0f} Stack:{stack_mae:,.0f} → {model_name}")
        else:
            use_gb = gb_mae < rf_mae and len(X_train) > 500
            self.model = gb if use_gb else rf
            model_name = "GB" if use_gb else "RF"
            log.info(f"RF:{rf_mae:,.0f} GB:{gb_mae:,.0f} → {model_name} | Rows:{len(X_train)}")

        self._rf = rf  # always keep RF for confidence intervals
        self._model_name = model_name
        return self.model

    def evaluate(self, X, y, split="train"):
        preds = self.model.predict(X)
        y_arr = np.asarray(y)
        rmse  = round(float(np.sqrt(mean_squared_error(y_arr, preds))))
        mae   = round(float(mean_absolute_error(y_arr, preds)))
        r2    = round(float(r2_score(y_arr, preds)) * 100)  # as percentage integer
        mask  = y_arr != 0
        mape  = round(float(np.mean(np.abs((y_arr[mask] - preds[mask]) / y_arr[mask])) * 100)) if mask.any() else 0
        wmape = round(float(np.sum(np.abs(y_arr - preds)) / (np.sum(np.abs(y_arr)) + 1e-9) * 100))
        accuracy = 100 - mape  # prediction accuracy percentage
        self.metrics[split] = {
            "RMSE": rmse,
            "MAE": mae,
            "R2": r2,
            "MAPE": mape,
            "WMAPE": wmape,
            "Accuracy": accuracy,
            "model": getattr(self, "_model_name", "RF")
        }
        log.info(f"{split} → RMSE:{rmse} MAE:{mae} R²:{r2}% MAPE:{mape}% Accuracy:{accuracy}%")
        return self.metrics[split]

    def predict_with_confidence(self, X, confidence=0.95):
        z  = {0.90:1.645, 0.95:1.96, 0.99:2.576}.get(confidence, 1.96)
        rf = getattr(self, "_rf", self.model)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            tree_preds = np.array([t.predict(X) for t in rf.estimators_])
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
        return {"coverage":coverage,"avg_interval_width":avg_width,
                "lower":lower.tolist(),"upper":upper.tolist()}

    def save_model(self, path="models/active_model.pkl"):
        os.makedirs("models", exist_ok=True)
        os.makedirs("logs",   exist_ok=True)
        self.version = datetime.now().strftime("v1_%Y%m%d_%H%M%S")
        joblib.dump(self.model, path)
        joblib.dump(getattr(self, "_rf", self.model), "models/baseline_model_rf.pkl")
        joblib.dump(self.model, f"models/model_{self.version}.pkl")
        self.version_history.append(self.version)
        meta = {"version":self.version,"saved_at":datetime.now().isoformat(),
                "params":self.best_params or {},"metrics":self.metrics,
                "model_type": getattr(self, "_model_name", "RF")}
        with open(f"logs/model_{self.version}_meta.json","w") as f:
            json.dump(meta, f, indent=2)
        log.info(f"Model saved: {path} | Version:{self.version} | Type:{meta['model_type']}")

    def save_metrics(self, path="logs/baseline_metrics.json"):
        with open(path,"w") as f:
            json.dump(self.metrics, f, indent=2)
        log.info(f"Metrics saved: {path}")
