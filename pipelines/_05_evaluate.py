from pipelines.utils import logger, PROCESSED_DIR, REPORT_DIR, mae, rmse, mape
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import os


def evaluate():
    hist = pd.read_parquet(f"{PROCESSED_DIR}/features.parquet")[["id", "date", "sales"]]
    pred = pd.read_parquet(f"{PROCESSED_DIR}/predictions.parquet")

    hist["date"] = pd.to_datetime(hist["date"])
    pred["date"] = pd.to_datetime(pred["date"])

    full = hist.merge(pred, on=["id", "date"], how="left")

    # Fix 7: alignment sanity check
    if len(full) == 0:
        raise ValueError("No matching rows between actuals and predictions — check id/date alignment")

    # Fix 2: missing prediction handling
    missing = full["yhat"].isna().sum()
    if missing > 0:
        logger.warning(f"⚠️ {missing:,} rows have no prediction — dropping before metrics")
    full = full.dropna(subset=["yhat"])

    full["abs_err"] = (full["sales"] - full["yhat"]).abs()

    # Fix 1: compute + save + log numeric metrics
    metrics = {
        "MAE":  mae(full["sales"],  full["yhat"]),
        "RMSE": rmse(full["sales"], full["yhat"]),
        "MAPE": mape(full["sales"], full["yhat"]),
    }
    logger.info(f"📊 MAE={metrics['MAE']:.4f} | RMSE={metrics['RMSE']:.4f} | MAPE={metrics['MAPE']:.2f}%")
    os.makedirs(REPORT_DIR, exist_ok=True)
    pd.DataFrame([metrics]).to_csv(f"{REPORT_DIR}/evaluation_metrics.csv", index=False)

    # Fix 3: store-level MAE
    if "store_id" in full.columns:
        store_agg = full.groupby(["store_id", "date"])[["sales", "yhat"]].sum().reset_index()
        store_mae = mae(store_agg["sales"], store_agg["yhat"])
        logger.info(f"🏬 Store-level MAE: {store_mae:.4f}")
        full.groupby("store_id")["abs_err"].mean().sort_values(ascending=False)\
            .to_csv(f"{REPORT_DIR}/store_mae.csv")

    # Fix 5: worst SKUs
    full.groupby("id")["abs_err"].mean()\
        .sort_values(ascending=False).head(20)\
        .to_csv(f"{REPORT_DIR}/worst_skus.csv")
    logger.info("⚠️ Worst SKUs saved")

    # ── Charts ────────────────────────────────────────────

    # Fix 8: aggregated chart + last-30-days zoom
    agg = full.groupby("date")[["sales", "yhat"]].sum()

    fig, axes = plt.subplots(2, 1, figsize=(12, 8))
    axes[0].plot(agg.index, agg["sales"], label="Actual",    color="steelblue")
    axes[0].plot(agg.index, agg["yhat"],  label="Predicted", color="darkorange", linestyle="--")
    axes[0].set_title("Daily Sales: Actual vs Predicted (Full)")
    axes[0].legend()

    tail = agg.tail(30)
    axes[1].plot(tail.index, tail["sales"], label="Actual",    color="steelblue")
    axes[1].plot(tail.index, tail["yhat"],  label="Predicted", color="darkorange", linestyle="--")
    axes[1].set_title("Last 30 Days")
    axes[1].legend()

    fig.tight_layout()
    fig.savefig(f"{REPORT_DIR}/agg_actual_vs_predicted.png", dpi=150)
    plt.close(fig)

    # Fix 4: error distribution
    fig2, ax2 = plt.subplots(figsize=(8, 4))
    full["abs_err"].hist(bins=50, ax=ax2, color="tomato", edgecolor="white")
    ax2.set_title("Absolute Error Distribution")
    ax2.set_xlabel("Absolute Error")
    fig2.tight_layout()
    fig2.savefig(f"{REPORT_DIR}/error_distribution.png", dpi=150)
    plt.close(fig2)

    # Fix 6: daily error trend (drift signal)
    fig3, ax3 = plt.subplots(figsize=(10, 3))
    full.groupby("date")["abs_err"].mean().plot(ax=ax3, color="purple")
    ax3.set_title("Daily Mean Absolute Error Trend")
    ax3.set_ylabel("MAE")
    fig3.tight_layout()
    fig3.savefig(f"{REPORT_DIR}/error_trend.png", dpi=150)
    plt.close(fig3)

    logger.info("✅ Evaluation complete — metrics + 3 charts saved")
    return metrics


if __name__ == "__main__":
    evaluate()
