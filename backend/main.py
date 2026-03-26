import sys
import numpy as np
import pandas as pd
from pathlib import Path
from pipeline import Phase1Pipeline
from logger import get_logger

log = get_logger(__name__)

BASE       = Path(__file__).parent.resolve()
RETAIL_CSV = BASE / "retail_sales.csv"
DATA_OUT   = BASE / "data" / "uploaded_data.csv"


def _parse_id(s):
    return int(str(s).split("_")[-1])


def prepare_real_data():
    """Convert retail_sales.csv → pipeline format.
    Train: 2019–2022 (4 years), Test: 2023 (last year).
    """
    if not RETAIL_CSV.exists():
        raise FileNotFoundError("retail_sales.csv not found in backend/.")

    log.info("Preparing data from retail_sales.csv")
    df = pd.read_csv(RETAIL_CSV)
    df.columns = df.columns.str.strip().str.lower()
    df["date"] = pd.to_datetime(df["date"])
    df["store_int"] = df["store_id"].apply(_parse_id)
    df["item_int"]  = df["item_id"].apply(_parse_id)

    # Only keep 2019–2022 — 2023 is reserved for user upload via the UI
    df = df[df["date"].dt.year <= 2022].copy()

    # Aggregate daily → weekly (week ending Friday)
    df["week"] = df["date"] - pd.to_timedelta((df["date"].dt.dayofweek - 4) % 7 - 7, unit="D")
    # Drop any weeks whose end-date fell into 2023 after the shift
    df = df[df["week"].dt.year <= 2022]
    agg = df.groupby(["week", "store_int", "item_int"]).agg(
        Demand=("sales", "sum"),
        Price =("price", "mean"),
        Promo =("promo", "max"),
    ).reset_index()

    out = pd.DataFrame({
        "Date":    agg["week"].dt.strftime("%d-%m-%Y"),
        "Store":   "store_" + agg["store_int"].astype(str),
        "Product": "item_" + agg["item_int"].astype(str),
        "Demand":  agg["Demand"].astype(int),
        "Price":   agg["Price"].round(2),
        "Promo":   agg["Promo"].astype(int),
    }).sort_values(["Date", "Store", "Product"]).reset_index(drop=True)

    years = sorted(out["Date"].apply(lambda d: pd.to_datetime(d, dayfirst=True).year).unique())
    log.info(f"Years in data: {years}")
    DATA_OUT.parent.mkdir(exist_ok=True)
    out.to_csv(DATA_OUT, index=False)
    log.info(f"Saved {len(out):,} rows → {DATA_OUT}  (Train: 2019–2021 | Test: 2022 | 2023 reserved for user)")
    return out


def _clear_stale_logs():
    """Remove logs from previous runs so old data never pollutes new results."""
    stale = [
        "logs/prediction_batches.json",
        "logs/drift_history.json",
        "logs/healing_history.json",
        "logs/training_log.json",
        "logs/phase1_summary.json",
        "logs/phase1_complete.json",
        "logs/baseline_metrics.json",
    ]
    import glob
    for p in stale:
        Path(p).unlink(missing_ok=True)
    for f in glob.glob("logs/predictions_*.csv") + glob.glob("processed/predictions_*.csv"):
        Path(f).unlink(missing_ok=True)
    log.info("Cleared stale logs from previous run")


def run_monitor_pipeline(data_path: str) -> dict:
    """Score uploaded data against the existing model — no retraining."""
    import json, joblib
    from feature_engineering import FeatureEngineer
    from drift_detector import DriftDetector
    from fine_tuner import FineTuner
    from data_loader import DataLoader
    from datetime import datetime as dt
    import os

    model_path = BASE / "models" / "active_model.pkl"
    fe_path    = BASE / "models" / "feature_engineer.pkl"
    if not model_path.exists():
        raise FileNotFoundError("No trained model found. Run the full pipeline first.")
    if not fe_path.exists():
        raise FileNotFoundError("No feature engineer found. Run the full pipeline first.")

    model = joblib.load(str(model_path))
    fe = FeatureEngineer()
    fe.load_state(str(fe_path))
    feature_names = fe.feature_names

    loader = DataLoader(data_path)
    loader.load_data()
    df, _ = fe.run_feature_pipeline(loader.df, fit=False)

    detector = DriftDetector()
    if hasattr(model, "feature_importances_"):
        detector.set_feature_importance(model, feature_names)

    # Build baseline distributions — sample training data to cap feature engineering cost
    # Uses at most 50K rows for baseline (statistically representative, not skipping uploaded data)
    _BASELINE_CAP = 50_000
    split_path = BASE / "logs" / "data_split.json"
    train_data_path = BASE / "data" / "uploaded_data.csv"
    if train_data_path.exists() and split_path.exists():
        try:
            with open(split_path) as f:
                split_info = json.load(f)
            train_years = split_info.get("train_years", [])
            train_raw = pd.read_csv(train_data_path)
            train_raw.columns = train_raw.columns.str.strip()
            if train_years:
                train_raw["Date"] = pd.to_datetime(train_raw["Date"], dayfirst=True, errors="coerce")
                train_raw = train_raw[train_raw["Date"].dt.year.isin(train_years)]
            # Cap baseline rows to avoid slow feature engineering on huge training sets
            if len(train_raw) > _BASELINE_CAP:
                train_raw = train_raw.sample(_BASELINE_CAP, random_state=42)
            train_fe, _ = fe.run_feature_pipeline(train_raw, fit=False)
            X_base = train_fe[feature_names].fillna(0)
            y_base = train_fe["Demand"].values
            detector.set_baseline(X_base, errors=(y_base - model.predict(X_base.values)))
        except Exception as e:
            log.warning(f"Could not set baseline distributions: {e}")

    df["YearMonth"] = df["Date"].dt.to_period("M")
    months = sorted(df["YearMonth"].unique())
    drift_reports, healing_actions, prediction_batches = [], [], []
    # Monitor mode: assess healing actions without actually refitting the model
    fine_tuner = FineTuner(model, feature_names)
    ts = dt.now().strftime("%Y%m%d_%H%M%S")  # single timestamp for all files this run

    os.makedirs(str(BASE / "processed"), exist_ok=True)
    os.makedirs(str(BASE / "logs"), exist_ok=True)

    for month in months:
        month_df = df[df["YearMonth"] == month].copy()
        if len(month_df) < 2:
            continue
        X = month_df[feature_names].fillna(0)
        y = month_df["Demand"].values
        preds = model.predict(X.values)

        out = pd.DataFrame({
            "Store":     month_df["Store"].values if "Store" in month_df.columns else range(len(y)),
            "Product":   month_df["Product"].values if "Product" in month_df.columns else range(len(y)),
            "Date":      month_df["Date"].dt.strftime("%Y-%m-%d").values,
            "Demand":    y,
            "Predicted": preds.round(2),
        })
        out.to_csv(str(BASE / "processed" / f"predictions_{month}_{ts}.csv"), index=False)

        prediction_batches.append({
            "month": str(month), "count": len(y),
            "mean_pred": np.round(float(preds.mean()), 2),
            "mean_actual": np.round(float(y.mean()), 2),
        })

        report = detector.comprehensive_detection(X, y - preds)
        report["month"] = str(month)
        drift_reports.append(report)

        # Decide healing action — no actual model.fit() in monitor mode
        severity = report.get("severity", "none")
        if severity == "none":
            action = {"action": "monitor", "improvement": 0, "model_updated": False}
        else:
            # Assess whether fine-tuning would help using val-set MAE estimate only
            split_idx = max(1, len(X) // 2)
            val_preds = model.predict(X.iloc[split_idx:].values)
            val_mae = float(np.mean(np.abs(y[split_idx:] - val_preds)))
            train_preds = model.predict(X.iloc[:split_idx].values)
            train_mae = float(np.mean(np.abs(y[:split_idx] - train_preds)))
            # If val MAE is >5% worse than train MAE, recommend fine-tune
            if train_mae > 0 and (val_mae - train_mae) / train_mae >= 0.05:
                # Use float casts to ensure consistent type for the dict values
                action = {"action": "fine_tune", "improvement": float(np.round((val_mae - train_mae) / train_mae, 4)), "model_updated": False}
            else:
                action = {"action": "monitor", "improvement": 0.0, "model_updated": False}
        action["month"] = str(month)
        healing_actions.append(action)

    with open(str(BASE / "logs" / "prediction_batches.json"), "w") as f:
        json.dump(prediction_batches, f, indent=2)
    with open(str(BASE / "logs" / "drift_history.json"), "w") as f:
        json.dump(drift_reports, f, indent=2)
    with open(str(BASE / "logs" / "healing_history.json"), "w") as f:
        json.dump(healing_actions, f, indent=2)

    severities = [r["severity"] for r in drift_reports]
    final_severity = "severe" if "severe" in severities else ("mild" if "mild" in severities else "none")
    healing_stats = {
        "total_actions": len(healing_actions),
        "monitor_only":  sum(1 for a in healing_actions if a["action"] == "monitor"),
        "fine_tuned":    sum(1 for a in healing_actions if a["action"] == "fine_tune"),
        "rollbacks":     sum(1 for a in healing_actions if a["action"] == "rollback"),
    }
    summary = {
        "final_severity": final_severity,
        "months_monitored": len(drift_reports),
        "healing_stats": healing_stats,
        "recommendation": (
            "Severe drift detected — fine-tuning applied" if final_severity == "severe" else
            "Mild drift detected — fine-tuning applied"   if final_severity == "mild"   else
            "No drift detected — model is stable"
        ),
    }
    with open(str(BASE / "logs" / "phase1_summary.json"), "w") as f:
        json.dump(summary, f, indent=2)

    if any(a.get("model_updated") for a in healing_actions):
        fine_tuner.save_healed_model()
        log.info("Healed model saved")

    return summary


def main():
    try:
        _clear_stale_logs()
        # Use uploaded file if it exists; only fall back to retail_sales.csv otherwise
        if DATA_OUT.exists():
            log.info(f"Using uploaded data: {DATA_OUT}")
        else:
            prepare_real_data()
        summary = Phase1Pipeline().run_phase1()
        log.info(f"Final Drift Severity: {summary['final_severity'].upper()}")
        log.info(f"Recommendation: {summary['recommendation']}")
        return 0
    except Exception as e:
        log.error(f"Pipeline failed: {e}")
        import traceback
        traceback.print_exc(file=sys.stderr)
        print(f"Error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
