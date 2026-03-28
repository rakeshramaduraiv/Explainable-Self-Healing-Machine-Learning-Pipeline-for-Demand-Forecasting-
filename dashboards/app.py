import os
import sys
import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pipelines.utils import PROCESSED_DIR, MODEL_DIR
from pipelines._drift import run_drift_check
from pipelines._06_retrain import fine_tune, sliding_window_retrain, predict_next_month
from pipelines._03_features import create_features_for_new_data

st.set_page_config(page_title="Demand Forecasting", layout="wide", page_icon="📦")
st.title("📦 Real-Time Demand Forecasting Dashboard")

# ─────────────────────────────────────────────
# SECTION 1: Upload Actual Month Data
# ─────────────────────────────────────────────
st.header("1. Upload Actual Month Data")

# Upload format selector
upload_mode = st.radio(
    "Select upload format:",
    ["3 Columns (id, date, sales)", "14 Columns (full merged format)"],
    horizontal=True
)

# Show format guide
if upload_mode == "3 Columns (id, date, sales)":
    st.markdown("""
    **Required columns:** `id`, `date`, `sales`
    - `id` format: `HOBBIES_1_001_CA_1_validation`
    - `date` format: `YYYY-MM-DD`
    - `sales`: integer >= 0
    """)
else:
    st.markdown("""
    **Required 14 columns:**
    `item_id`, `dept_id`, `cat_id`, `store_id`, `state_id`,
    `wm_yr_wk`, `snap_CA`, `snap_TX`, `snap_WI`, `sell_price`,
    `dayofweek`, `weekofyear`, `month`, `year`

    **Plus required:** `date`, `sales`
    """)

COLS_3  = ["id", "date", "sales"]
COLS_14 = ["item_id","dept_id","cat_id","store_id","state_id",
           "wm_yr_wk","snap_CA","snap_TX","snap_WI","sell_price",
           "dayofweek","weekofyear","month","year","date","sales"]

uploaded = st.file_uploader("Upload CSV", type=["csv"])

if uploaded:
    actual_df = pd.read_csv(uploaded, parse_dates=["date"])

    # Validate based on selected mode
    if upload_mode == "3 Columns (id, date, sales)":
        missing = [c for c in COLS_3 if c not in actual_df.columns]
        if missing:
            st.error(f"Missing columns: {missing}")
            st.stop()
        st.success(f"3-column format detected — pipeline will auto-fill remaining columns")

    else:
        missing = [c for c in COLS_14 if c not in actual_df.columns]
        if missing:
            st.error(f"Missing columns: {missing}")
            st.stop()

        # Validate column values
        errors = []
        if not actual_df["cat_id"].isin(["HOBBIES","FOODS","HOUSEHOLD"]).all():
            errors.append("cat_id must be HOBBIES, FOODS or HOUSEHOLD")
        if not actual_df["state_id"].isin(["CA","TX","WI"]).all():
            errors.append("state_id must be CA, TX or WI")
        if not actual_df["snap_CA"].isin([0,1]).all():
            errors.append("snap_CA must be 0 or 1")
        if not actual_df["snap_TX"].isin([0,1]).all():
            errors.append("snap_TX must be 0 or 1")
        if not actual_df["snap_WI"].isin([0,1]).all():
            errors.append("snap_WI must be 0 or 1")
        if (actual_df["dayofweek"] < 0).any() or (actual_df["dayofweek"] > 6).any():
            errors.append("dayofweek must be 0 to 6")
        if (actual_df["month"] < 1).any() or (actual_df["month"] > 12).any():
            errors.append("month must be 1 to 12")
        if (actual_df["sell_price"] < 0).any():
            errors.append("sell_price must be positive")
        if errors:
            for e in errors:
                st.error(e)
            st.stop()

        # Build id column from 14-column format
        actual_df["id"] = (
            actual_df["item_id"] + "_" +
            actual_df["store_id"] + "_validation"
        )
        st.success("14-column format detected — id column auto-generated")

    # Show column summary
    col1, col2, col3 = st.columns(3)
    col1.metric("Rows", f"{len(actual_df):,}")
    col2.metric("SKUs", f"{actual_df['id'].nunique() if 'id' in actual_df.columns else 'N/A'}")
    col3.metric("Date Range", f"{actual_df['date'].min().date()} to {actual_df['date'].max().date()}")
    st.dataframe(actual_df.head(10), use_container_width=True)

    # Save actual month parquet
    actual_df.to_parquet(f"{PROCESSED_DIR}/actual_month.parquet", index=False)

    # ─────────────────────────────────────────────
    # SECTION 2: Drift Detection
    # ─────────────────────────────────────────────
    st.header("2. Drift Detection (KS Test)")

    pred_path = f"{PROCESSED_DIR}/predictions.parquet"
    if not os.path.exists(pred_path):
        st.warning("⚠️ No predictions file found. Run the base pipeline first.")
        st.stop()

    if st.button("▶ Run Drift Check"):
        with st.spinner("Running KS drift test..."):
            result = run_drift_check()

        ks   = result["ks_stat"]
        level = result["level"]

        col1, col2 = st.columns(2)
        col1.metric("KS Statistic", f"{ks:.4f}" if ks is not None else "N/A")
        col2.metric("Drift Level", level.upper())

        # Visual gauge — only draw if ks is valid
        if ks is not None:
            fig, ax = plt.subplots(figsize=(6, 1))
            ax.barh(0, float(ks), color={"low": "green", "medium": "orange", "high": "red"}.get(level, "gray"), height=0.4)
            ax.axvline(0.1, color="orange", linestyle="--", linewidth=1, label="Medium (0.1)")
            ax.axvline(0.3, color="red",    linestyle="--", linewidth=1, label="High (0.3)")
            ax.set_xlim(0, 1)
            ax.set_yticks([])
            ax.set_xlabel("KS Statistic")
            ax.legend(loc="upper right", fontsize=8)
            ax.set_title("Drift Gauge")
            st.pyplot(fig)
        else:
            st.warning("No overlapping rows between uploaded data and predictions. Check that id and date match.")

        st.session_state["drift_level"] = level
        st.session_state["ks_stat"]     = ks

        if level == "low":
            st.info("✅ LOW drift — model is stable. Monitoring only.")
        elif level == "medium":
            st.warning("⚠️ MEDIUM drift — fine-tuning recommended.")
        else:
            st.error("🚨 HIGH drift — sliding window retrain required.")

    # ─────────────────────────────────────────────
    # SECTION 3: Model Update
    # ─────────────────────────────────────────────
    if "drift_level" in st.session_state:
        level = st.session_state["drift_level"]
        st.header("3. Model Update")

        if level == "low":
            st.info("No retraining needed. Proceeding to prediction.")

        elif level == "medium":
            if st.button("🔧 Fine-Tune Model"):
                with st.spinner("Engineering features for new data..."):
                    create_features_for_new_data(actual_df)
                with st.spinner("Fine-tuning model..."):
                    metrics = fine_tune()
                st.success("✅ Fine-tuning complete!")
                st.json(metrics)

        elif level == "high":
            if st.button("🔁 Sliding Window Retrain"):
                with st.spinner("Engineering features for new data..."):
                    create_features_for_new_data(actual_df)
                with st.spinner("Retraining with sliding window..."):
                    metrics = sliding_window_retrain()
                st.success("✅ Retrain complete!")
                st.json(metrics)

        # ─────────────────────────────────────────────
        # SECTION 4: Predict Next Month
        # ─────────────────────────────────────────────
        st.header("4. Predict Next Month")

        if st.button("🔮 Generate Next Month Forecast"):
            with st.spinner("Generating predictions..."):
                out_df = predict_next_month()

            st.success(f"✅ Predicted {len(out_df):,} rows for next month.")

            # Preview
            st.dataframe(out_df.head(20), use_container_width=True)

            # Aggregated chart
            agg = out_df.groupby("date")["predicted_sales"].sum().reset_index()
            fig2, ax2 = plt.subplots(figsize=(10, 4))
            ax2.plot(agg["date"], agg["predicted_sales"], color="tab:blue", linewidth=2)
            ax2.set_title("Next Month — Total Predicted Daily Sales")
            ax2.set_xlabel("Date")
            ax2.set_ylabel("Units")
            st.pyplot(fig2)

            # Download button
            csv = out_df.to_csv(index=False).encode("utf-8")
            st.download_button(
                label="⬇️ Download Predictions as CSV",
                data=csv,
                file_name=f"next_month_predictions_{out_df['date'].min().date()}.csv",
                mime="text/csv"
            )

else:
    st.info("👆 Upload the actual month CSV to get started.")

    # Show existing predictions if available
    pred_path = f"{PROCESSED_DIR}/predictions.parquet"
    if os.path.exists(pred_path):
        st.subheader("Last Known Predictions")
        df = pd.read_parquet(pred_path)
        agg = df.groupby("date")["yhat"].sum().reset_index()
        fig, ax = plt.subplots(figsize=(10, 3))
        ax.plot(agg["date"], agg["yhat"], color="tab:orange")
        ax.set_title("Aggregated Predicted Sales (Last Run)")
        ax.set_xlabel("Date")
        ax.set_ylabel("Units")
        st.pyplot(fig)
