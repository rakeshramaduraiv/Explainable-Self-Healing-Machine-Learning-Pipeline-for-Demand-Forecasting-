import sys
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

    # Cap at 2023-12-31 — prevents week-boundary bleed into 2024
    df = df[df["date"].dt.year <= 2023].copy()

    # Aggregate daily → weekly (week ending Friday)
    df["week"] = df["date"] - pd.to_timedelta((df["date"].dt.dayofweek - 4) % 7 - 7, unit="D")
    # Drop any weeks whose end-date fell into 2024 after the shift
    df = df[df["week"].dt.year <= 2023]
    agg = df.groupby(["week", "store_int", "item_int"]).agg(
        Demand=("sales", "sum"),
        Price =("price", "mean"),
        Promo =("promo", "max"),
    ).reset_index()

    out = pd.DataFrame({
        "Date":    agg["week"].dt.strftime("%d-%m-%Y"),
        "Store":   agg["store_int"].astype(int),
        "Product": agg["item_int"].astype(int),
        "Demand":  agg["Demand"].astype(int),
        "Price":   agg["Price"].round(2),
        "Promo":   agg["Promo"].astype(int),
    }).sort_values(["Date", "Store", "Product"]).reset_index(drop=True)

    years = sorted(out["Date"].apply(lambda d: pd.to_datetime(d, dayfirst=True).year).unique())
    log.info(f"Years in data: {years}")
    DATA_OUT.parent.mkdir(exist_ok=True)
    out.to_csv(DATA_OUT, index=False)
    log.info(f"Saved {len(out):,} rows → {DATA_OUT}  (Train: 2019–2022 | Test: 2023)")
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


def main():
    try:
        # Always prepare from real CSVs — no synthetic fallback
        _clear_stale_logs()
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
