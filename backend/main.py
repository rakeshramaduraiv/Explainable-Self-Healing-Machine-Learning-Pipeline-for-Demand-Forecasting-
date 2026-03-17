import sys
import os
import pandas as pd
from pathlib import Path
from pipeline import Phase1Pipeline
from logger import get_logger

log = get_logger(__name__)

BASE = Path(__file__).parent.resolve()
TRAIN_CSV = BASE / "train.csv"
DATA_OUT  = BASE / "data" / "uploaded_data.csv"


def prepare_real_data():
    """Convert the 3 Kaggle CSVs into pipeline format. No synthetic data."""
    if not TRAIN_CSV.exists():
        raise FileNotFoundError(
            "train.csv not found in backend/. "
            "Download from https://www.kaggle.com/datasets/dhrubangtalukdar/store-item-demand-forecasting-dataset"
        )

    log.info("Preparing real Kaggle data from train.csv + test.csv + sample_submission.csv")

    # ── train.csv: date, store, item, sales ──────────────────────────────────
    tr = pd.read_csv(TRAIN_CSV)
    tr.columns = tr.columns.str.strip().str.lower()
    tr["date"] = pd.to_datetime(tr["date"])

    # Aggregate daily → weekly (week ending Friday)
    tr["week"] = tr["date"].dt.to_period("W-FRI").apply(lambda p: p.end_time.normalize())
    weekly = tr.groupby(["week", "store", "item"])["sales"].sum().reset_index()

    # Use last 2 full years: 2016 (train) + 2017 (test/drift)
    weekly["year"] = weekly["week"].dt.year
    years = sorted(weekly["year"].unique())
    use = years[-3:-1] if len(years) >= 3 else years[-2:]
    weekly = weekly[weekly["year"].isin(use)].copy()

    train_data = pd.DataFrame({
        "Date":    weekly["week"].dt.strftime("%d-%m-%Y"),
        "Store":   weekly["store"].astype(int),
        "Product": weekly["item"].astype(int),
        "Demand":  weekly["sales"].astype(int),
    }).sort_values(["Date", "Store", "Product"]).reset_index(drop=True)

    DATA_OUT.parent.mkdir(exist_ok=True)
    train_data.to_csv(DATA_OUT, index=False)
    log.info(f"Saved {len(train_data):,} rows to {DATA_OUT} | years: {use}")

    # ── test.csv: future dates for sequential prediction (no sales — ignored) ──
    if TEST_CSV.exists():
        log.info("test.csv found — not used (no sales column, Kaggle competition blind test)")

    return train_data


def main():
    try:
        # Always prepare from real CSVs — no synthetic fallback
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
