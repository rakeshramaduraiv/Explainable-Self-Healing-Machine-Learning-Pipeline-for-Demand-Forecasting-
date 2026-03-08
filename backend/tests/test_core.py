import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import pytest
import numpy as np
import pandas as pd
from drift_detector import DriftDetector
from feature_engineering import FeatureEngineer
from data_loader import DataLoader


# ── DriftDetector ──────────────────────────────────────────────────────────────
class TestDriftDetector:
    def setup_method(self):
        self.det = DriftDetector()
        rng = np.random.default_rng(42)
        self.baseline = pd.DataFrame({
            "f1": rng.normal(0, 1, 500),
            "f2": rng.normal(10, 2, 500),
        })
        self.current_same    = pd.DataFrame({"f1": rng.normal(0, 1, 200), "f2": rng.normal(10, 2, 200)})
        self.current_shifted = pd.DataFrame({"f1": rng.normal(5, 1, 200), "f2": rng.normal(10, 2, 200)})

    def test_set_baseline(self):
        self.det.set_baseline(self.baseline)
        assert "f1" in self.det.baseline_distributions
        assert "f2" in self.det.baseline_distributions

    def test_no_drift_on_same_distribution(self):
        self.det.set_baseline(self.baseline)
        result = self.det.ks_test_drift(self.current_same)
        assert result["f1"]["severity"] in ("none", "mild")

    def test_drift_detected_on_shifted_distribution(self):
        self.det.set_baseline(self.baseline)
        result = self.det.ks_test_drift(self.current_shifted)
        assert result["f1"]["severity"] == "severe"

    def test_psi_returns_scores(self):
        self.det.set_baseline(self.baseline)
        result = self.det.psi_analysis(self.current_shifted)
        assert "f1" in result
        assert "psi" in result["f1"]

    def test_error_trend_no_baseline(self):
        result = self.det.track_error_trend(np.array([100, 200, 150]))
        assert result["error_increase"] == 0.0

    def test_comprehensive_detection_returns_severity(self):
        self.det.set_baseline(self.baseline, errors=np.zeros(500))
        result = self.det.comprehensive_detection(self.current_shifted, np.ones(200) * 100)
        assert result["severity"] in ("none", "mild", "severe")
        assert "severe_features" in result
        assert "mild_features" in result

    def test_ks_skips_columns_not_in_current(self):
        self.det.set_baseline(self.baseline)
        result = self.det.ks_test_drift(pd.DataFrame({"f1": np.random.normal(0, 1, 50)}))
        assert "f1" in result
        assert "f2" not in result

    def test_psi_constant_feature_no_crash(self):
        """PSI should not crash when a feature has zero variance."""
        df_const = pd.DataFrame({"f1": np.ones(200), "f2": np.random.normal(10, 2, 200)})
        self.det.set_baseline(df_const)
        result = self.det.psi_analysis(df_const)
        assert "f1" in result

    def test_comprehensive_total_features_present(self):
        self.det.set_baseline(self.baseline, errors=np.zeros(500))
        result = self.det.comprehensive_detection(self.current_shifted, np.ones(200))
        assert "total_features" in result
        assert result["total_features"] >= 0


# ── FeatureEngineer ────────────────────────────────────────────────────────────
class TestFeatureEngineer:
    def setup_method(self):
        self.eng = FeatureEngineer()
        rng = np.random.default_rng(42)
        dates = pd.date_range("2010-02-05", periods=100, freq="7D")
        self.df = pd.DataFrame({
            "Store": np.tile([1, 2], 50),
            "Date": np.tile(dates, 1)[:100],
            "Weekly_Sales": rng.uniform(50000, 200000, 100),
            "Holiday_Flag": rng.integers(0, 2, 100),
            "Temperature": rng.uniform(20, 90, 100),
            "Fuel_Price": rng.uniform(2.5, 4.5, 100),
            "CPI": rng.uniform(210, 230, 100),
            "Unemployment": rng.uniform(6, 10, 100),
        })

    def test_temporal_features_created(self):
        result = self.eng.create_temporal_features(self.df.copy())
        for col in ["Year", "Month", "Week", "Quarter", "Season"]:
            assert col in result.columns

    def test_lag_features_created(self):
        result = self.eng.create_lag_features(self.df.copy())
        for lag in [1, 2, 4]:
            assert f"Lag_{lag}" in result.columns

    def test_rolling_features_created(self):
        result = self.eng.create_rolling_features(self.df.copy())
        assert "Rolling_Mean_4" in result.columns
        assert "Rolling_Std_4" in result.columns

    def test_pipeline_returns_features(self):
        proc, feats = self.eng.run_feature_pipeline(self.df.copy(), fit=True)
        assert len(feats) > 0
        assert "Weekly_Sales" in proc.columns
        assert "Date" in proc.columns

    def test_pipeline_fit_false_uses_saved_stats(self):
        self.eng.run_feature_pipeline(self.df.copy(), fit=True)
        proc2, feats2 = self.eng.run_feature_pipeline(self.df.copy(), fit=False)
        assert len(feats2) > 0

    def test_feature_names_exclude_non_features(self):
        """Store, Date, Weekly_Sales must not appear in feature_names."""
        _, feats = self.eng.run_feature_pipeline(self.df.copy(), fit=True)
        for col in ["Store", "Date", "Weekly_Sales", "YearMonth"]:
            assert col not in feats, f"{col} should not be in feature_names"

    def test_no_nan_in_feature_columns(self):
        proc, feats = self.eng.run_feature_pipeline(self.df.copy(), fit=True)
        assert proc[feats].isnull().sum().sum() == 0

    def test_pipeline_preserves_all_rows(self):
        """Lag fill strategy must not drop rows."""
        proc, _ = self.eng.run_feature_pipeline(self.df.copy(), fit=True)
        assert len(proc) == len(self.df)


# ── DataLoader ─────────────────────────────────────────────────────────────────
class TestDataLoader:
    def setup_method(self):
        self.loader = DataLoader("data/uploaded_data.csv")

    def test_load_data_returns_dataframe(self):
        df = self.loader.load_data()
        assert isinstance(df, pd.DataFrame)
        assert len(df) > 0

    def test_required_columns_present(self):
        df = self.loader.load_data()
        for col in ["Store", "Date", "Weekly_Sales", "Holiday_Flag",
                    "Temperature", "Fuel_Price", "CPI", "Unemployment"]:
            assert col in df.columns

    def test_date_parsed_correctly(self):
        df = self.loader.load_data()
        assert pd.api.types.is_datetime64_any_dtype(df["Date"])

    def test_split_train_test_chronological(self):
        self.loader.load_data()
        train, test = self.loader.split_train_test(train_months=12)
        assert train["Date"].max() < test["Date"].min()
        assert len(train) > 0
        assert len(test) > 0

    def test_split_no_overlap(self):
        self.loader.load_data()
        train, test = self.loader.split_train_test(train_months=12)
        train_dates = set(train["Date"].dt.date)
        test_dates  = set(test["Date"].dt.date)
        assert len(train_dates & test_dates) == 0

    def test_missing_file_raises(self):
        loader = DataLoader("data/nonexistent_file.csv")
        with pytest.raises(FileNotFoundError):
            loader.load_data()

    def test_sorted_by_store_and_date(self):
        df = self.loader.load_data()
        for store, grp in df.groupby("Store"):
            assert grp["Date"].is_monotonic_increasing, f"Store {store} dates not sorted"
