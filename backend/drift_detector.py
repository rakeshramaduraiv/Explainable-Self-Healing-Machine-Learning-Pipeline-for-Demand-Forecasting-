import warnings
import numpy as np
from scipy.stats import ks_2samp, wasserstein_distance
from scipy.spatial.distance import jensenshannon
from logger import get_logger

log = get_logger(__name__)


class DriftDetector:
    def __init__(self):
        self.baseline_distributions = {}
        self.baseline_errors = None
        self.feature_importance = {}        # {feature: importance_score}
        self.importance_percentiles = {}    # {high/medium/low: threshold}

    # ── Improvement 1: Dynamic Thresholds ────────────────────────────────────
    def set_feature_importance(self, model, feature_names):
        importances = model.feature_importances_
        self.feature_importance = dict(zip(feature_names, importances))
        vals = list(importances)
        self.importance_percentiles = {
            "high":   np.percentile(vals, 80),
            "medium": np.percentile(vals, 50),
            "low":    np.percentile(vals, 20),
        }
        log.info(f"Dynamic thresholds set for {len(feature_names)} features")

    def _importance_category(self, feature):
        if not self.feature_importance or feature not in self.feature_importance:
            return "medium"
        imp = self.feature_importance[feature]
        if imp >= self.importance_percentiles.get("high", 0.01):
            return "high"
        if imp <= self.importance_percentiles.get("low", 0.001):
            return "low"
        return "medium"

    def _dynamic_threshold(self, feature, base):
        factor = {"high": 0.7, "medium": 1.0, "low": 1.3}[self._importance_category(feature)]
        return base * factor

    # ── Core drift methods ────────────────────────────────────────────────────
    def set_baseline(self, X_baseline, errors=None):
        for col in X_baseline.columns:
            self.baseline_distributions[col] = X_baseline[col].dropna().values
        if errors is not None:
            self.baseline_errors = np.array(errors)
        log.info(f"Baseline set: {len(self.baseline_distributions)} features")

    def ks_test_drift(self, X_current):
        results = {}
        for col, baseline in self.baseline_distributions.items():
            if col not in X_current.columns:
                continue
            current = X_current[col].dropna().values
            if len(current) < 5:
                continue
            stat, p_value = ks_2samp(baseline, current)
            mild_t   = self._dynamic_threshold(col, 0.05)
            severe_t = self._dynamic_threshold(col, 0.15)
            severity = "none" if stat < mild_t else ("mild" if stat < severe_t else "severe")
            results[col] = {
                "statistic": float(stat), "p_value": float(p_value),
                "severity": severity,
                "threshold_mild": round(mild_t, 3), "threshold_severe": round(severe_t, 3),
                "importance_category": self._importance_category(col),
            }
        return results

    def psi_analysis(self, X_current, bins=10):
        results = {}
        for col, baseline in self.baseline_distributions.items():
            if col not in X_current.columns:
                continue
            current = X_current[col].dropna().values
            if len(current) < 5:
                continue
            psi = self._compute_psi(baseline, current, bins)
            mild_t   = self._dynamic_threshold(col, 0.1)
            severe_t = self._dynamic_threshold(col, 0.25)
            severity = "none" if psi < mild_t else ("mild" if psi < severe_t else "severe")
            results[col] = {"psi": float(psi), "severity": severity}
        return results

    def _compute_psi(self, baseline, current, bins=10):
        lo = min(baseline.min(), current.min())
        hi = max(baseline.max(), current.max())
        if lo == hi:
            return 0.0
        breakpoints = np.linspace(lo, hi, bins + 1)
        b_pct = np.histogram(baseline, bins=breakpoints)[0] / len(baseline)
        c_pct = np.histogram(current, bins=breakpoints)[0] / len(current)
        b_pct = np.where(b_pct == 0, 1e-6, b_pct)
        c_pct = np.where(c_pct == 0, 1e-6, c_pct)
        return float(abs(np.sum((c_pct - b_pct) * np.log(c_pct / b_pct))))

    # ── Improvement 5: Additional drift methods ───────────────────────────────
    def wasserstein_drift(self, X_current, top_n=10):
        results = {}
        cols = list(self.baseline_distributions.keys())[:top_n]
        for col in cols:
            if col not in X_current.columns:
                continue
            current = X_current[col].dropna().values
            if len(current) < 5:
                continue
            dist = float(wasserstein_distance(self.baseline_distributions[col], current))
            results[col] = {"wasserstein": round(dist, 4)}
        return results

    def js_divergence_drift(self, X_current, top_n=10, bins=20):
        results = {}
        cols = list(self.baseline_distributions.keys())[:top_n]
        for col in cols:
            if col not in X_current.columns:
                continue
            baseline = self.baseline_distributions[col]
            current  = X_current[col].dropna().values
            if len(current) < 5:
                continue
            lo = min(baseline.min(), current.min())
            hi = max(baseline.max(), current.max())
            if lo == hi:
                results[col] = {"js_divergence": 0.0}
                continue
            edges = np.linspace(lo, hi, bins + 1)
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                p = np.histogram(baseline, bins=edges)[0].astype(float) + 1e-10
                q = np.histogram(current,  bins=edges)[0].astype(float) + 1e-10
            p /= p.sum(); q /= q.sum()
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                js = float(jensenshannon(p, q))
            results[col] = {"js_divergence": round(js if np.isfinite(js) else 0.0, 4)}
        return results

    def track_error_trend(self, current_errors):
        if len(current_errors) == 0:
            return {"error_increase": 0.0, "drift": False}
        current_mean = float(np.mean(np.abs(current_errors)))
        if self.baseline_errors is None or len(self.baseline_errors) == 0:
            return {"error_increase": 0.0, "drift": False}
        baseline_mean = float(np.mean(np.abs(self.baseline_errors)))
        increase = (current_mean - baseline_mean) / (baseline_mean + 1e-9)
        return {
            "baseline_error": round(baseline_mean, 2),
            "current_error": round(current_mean, 2),
            "error_increase": round(float(increase), 4),
            "drift": bool(increase > 0.10)
        }

    def comprehensive_detection(self, X_current, current_errors):
        ks  = self.ks_test_drift(X_current)
        psi = self.psi_analysis(X_current)
        error_trend  = self.track_error_trend(current_errors)
        wasserstein  = self.wasserstein_drift(X_current)
        js_div       = self.js_divergence_drift(X_current)

        severe_count = sum(1 for v in ks.values()  if v["severity"] == "severe")
        severe_count += sum(1 for v in psi.values() if v["severity"] == "severe")
        mild_count   = sum(1 for v in ks.values()  if v["severity"] == "mild")
        total = len(ks)

        if severe_count > 0 or error_trend["drift"]:
            severity = "severe"
        elif total > 0 and mild_count > (total * 0.3):
            severity = "mild"
        else:
            severity = "none"

        return {
            "severity": severity,
            "severe_features": severe_count,
            "mild_features": mild_count,
            "total_features": total,
            "error_trend": error_trend,
            "wasserstein": wasserstein,
            "js_divergence": js_div,
        }
