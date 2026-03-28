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
from pipelines._02_validate import validate_upload

REPORT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "reports")

st.set_page_config(page_title="Demand Forecasting", layout="wide", page_icon="📦")

for _key in ["drift_level", "actual_df", "data_ready", "ks_stat", "psi"]:
    if _key not in st.session_state:
        st.session_state[_key] = None

st.title("📦 Real-Time Demand Forecasting Dashboard")

# ─────────────────────────────────────────────
# SECTION 1: Upload Actual Month Data
# ─────────────────────────────────────────────
st.header("1. Upload Actual Month Data")

upload_mode = st.radio(
    "Select upload format:",
    ["3 Columns (id, date, sales)", "14 Columns (full merged format)"],
    horizontal=True
)

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

    if actual_df["date"].isna().any():
        st.error("Invalid date format. Use YYYY-MM-DD.")
        st.stop()

    if upload_mode == "3 Columns (id, date, sales)":
        missing = [c for c in COLS_3 if c not in actual_df.columns]
        if missing:
            st.error(f"Missing columns: {missing}")
            st.stop()
        st.success("3-column format detected — pipeline will auto-fill remaining columns")
    else:
        missing = [c for c in COLS_14 if c not in actual_df.columns]
        if missing:
            st.error(f"Missing columns: {missing}")
            st.stop()

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

        actual_df["id"] = actual_df["item_id"] + "_" + actual_df["store_id"] + "_validation"
        st.success("14-column format detected — id column auto-generated")

    col1, col2, col3 = st.columns(3)
    col1.metric("Rows",       f"{len(actual_df):,}")
    col2.metric("SKUs",       f"{actual_df['id'].nunique() if 'id' in actual_df.columns else 'N/A'}")
    col3.metric("Date Range", f"{actual_df['date'].min().date()} to {actual_df['date'].max().date()}")
    st.dataframe(actual_df.head(10), use_container_width=True)

    # Upgrade A: ID integrity + upload validation
    if "sales" in actual_df.columns and len(actual_df) > 0:
        ref_ids = None
        try:
            ref_ids = pd.read_parquet(f"{PROCESSED_DIR}/features.parquet")["id"].unique()
        except Exception:
            pass
        upload_errors = validate_upload(actual_df, ref_ids)
        if upload_errors:
            for e in upload_errors:
                st.error(f"❌ {e}")
            st.stop()
        actual_df.to_parquet(f"{PROCESSED_DIR}/actual_month.parquet", index=False)
        st.session_state["actual_df"]  = actual_df
        st.session_state["data_ready"] = True
    else:
        st.error("Uploaded file has no valid sales data.")
        st.stop()

# Restore from session on rerun
if st.session_state["actual_df"] is not None:
    actual_df = st.session_state["actual_df"]

    # ─────────────────────────────────────────────
    # SECTION 2: Drift Detection
    # ─────────────────────────────────────────────
    st.header("2. Drift Detection")

    pred_path = f"{PROCESSED_DIR}/predictions.parquet"
    if not os.path.exists(pred_path):
        st.warning("⚠️ No predictions file found. Run the base pipeline first.")
        st.stop()

    if st.button("▶ Run Drift Check"):
        with st.spinner("Running drift analysis (KS + PSI + Error-Based)..."):
            result = run_drift_check()

        ks          = result.get("ks_stat")
        psi         = result.get("psi")
        mae_val     = result.get("mae")
        error_level = result.get("error_level", "N/A")
        drift_score = result.get("drift_score")
        feat_drift  = result.get("feature_drift", {})
        level       = result.get("level", "unknown")

        # Upgrade C: 5 metric cards including weighted drift score
        col1, col2, col3, col4, col5 = st.columns(5)
        col1.metric("KS Statistic",  f"{ks:.4f}"          if ks          is not None else "N/A", help="Concept Drift")
        col2.metric("PSI",           f"{psi:.4f}"         if psi         is not None else "N/A", help="Data Drift")
        col3.metric("Current MAE",   f"{mae_val:.4f}"     if mae_val     is not None else "N/A", help="Error-Based Drift")
        col4.metric("Drift Score",   f"{drift_score:.4f}" if drift_score is not None else "N/A", help="Weighted: 0.4×PSI + 0.3×KS + 0.3×Error")
        col5.metric("Final Decision", level.upper())

        if ks is not None:
            color = {"low": "green", "medium": "orange", "high": "red"}.get(level, "gray")
            fig, axes = plt.subplots(1, 3, figsize=(13, 1.2))

            axes[0].barh(0, ks,  color=color, height=0.4)
            axes[0].axvline(0.1, color="orange", linestyle="--", linewidth=1, label="0.1")
            axes[0].axvline(0.3, color="red",    linestyle="--", linewidth=1, label="0.3")
            axes[0].set_xlim(0, 1); axes[0].set_yticks([])
            axes[0].set_title(f"KS = {ks}"); axes[0].legend(fontsize=7)

            axes[1].barh(0, psi, color=color, height=0.4)
            axes[1].axvline(0.1,  color="orange", linestyle="--", linewidth=1, label="0.1")
            axes[1].axvline(0.25, color="red",    linestyle="--", linewidth=1, label="0.25")
            axes[1].set_xlim(0, 1); axes[1].set_yticks([])
            axes[1].set_title(f"PSI = {psi}"); axes[1].legend(fontsize=7)

            err_map = {"low": 0.05, "medium": 0.15, "high": 0.5}
            axes[2].barh(0, err_map.get(error_level, 0), color=color, height=0.4)
            axes[2].axvline(0.1, color="orange", linestyle="--", linewidth=1, label="Medium")
            axes[2].axvline(0.5, color="red",    linestyle="--", linewidth=1, label="High")
            axes[2].set_xlim(0, 1); axes[2].set_yticks([])
            axes[2].set_title(f"Error = {str(error_level).upper()}"); axes[2].legend(fontsize=7)
            st.pyplot(fig)

        # Feature-wise PSI table
        if feat_drift:
            st.markdown("**Feature-wise PSI**")
            fd_df = pd.DataFrame(feat_drift.items(), columns=["Feature", "PSI"])
            fd_df["Status"] = fd_df["PSI"].apply(
                lambda x: "🟢 Stable" if x < 0.1 else ("🟡 Moderate" if x < 0.25 else "🔴 High")
            )
            st.dataframe(fd_df, use_container_width=True)

        # Upgrade F: Drift history chart
        drift_log = os.path.join(REPORT_DIR, "drift_history.csv")
        if os.path.exists(drift_log):
            st.markdown("**Drift History**")
            dh = pd.read_csv(drift_log)
            if len(dh) > 1:
                fig_h, ax_h = plt.subplots(figsize=(10, 2.5))
                ax_h.plot(dh["date"], dh["psi"],         label="PSI",         marker="o")
                ax_h.plot(dh["date"], dh["ks_stat"],     label="KS",          marker="s")
                ax_h.plot(dh["date"], dh["drift_score"], label="Drift Score", marker="^")
                ax_h.axhline(0.1,  color="orange", linestyle="--", linewidth=0.8)
                ax_h.axhline(0.25, color="red",    linestyle="--", linewidth=0.8)
                ax_h.set_title("Drift Metrics Over Time")
                ax_h.legend(fontsize=8); plt.xticks(rotation=30)
                st.pyplot(fig_h)

        if level == "low":
            st.success("✅ LOW drift — model is stable.")
        elif level == "medium":
            st.warning("⚠️ MEDIUM drift — fine-tuning recommended.")
        elif level == "high":
            st.error("🚨 HIGH drift — sliding window retrain required.")
        else:
            st.warning("Could not compute drift — check that sales data is valid.")

        st.session_state["drift_level"] = level
        st.session_state["ks_stat"]     = ks
        st.session_state["psi"]         = psi

    # ─────────────────────────────────────────────
    # SECTION 3: Model Update
    # ─────────────────────────────────────────────
    if st.session_state["drift_level"] is not None:
        level = st.session_state["drift_level"]
        st.header("3. Model Update")

        if level == "low":
            st.success("✅ LOW drift — model is healthy. No retraining needed.")
            st.info("Proceed to Section 4 to generate next month forecast.")

        elif level == "medium":
            st.warning("⚠️ MEDIUM drift — Fine-tuning recommended.")
            st.markdown("**Fine-tuning** continues training the existing model on new month data.")
            if st.button("🔧 Fine-Tune Model"):
                with st.spinner("Engineering features for new data..."):
                    create_features_for_new_data(actual_df)
                with st.spinner("Fine-tuning model..."):
                    metrics = fine_tune()
                st.success("✅ Fine-tuning complete!")
                c1, c2, c3 = st.columns(3)
                c1.metric("MAE",  f"{metrics.get('MAE',  0):.4f}")
                c2.metric("RMSE", f"{metrics.get('RMSE', 0):.4f}")
                c3.metric("MAPE", f"{metrics.get('MAPE', 0):.4f}")
                st.session_state["model_updated"] = True

        elif level == "high":
            st.error("🚨 HIGH drift — Sliding Window Retrain required.")
            st.markdown("**Sliding window retrain** rebuilds the model using the last 6 months of data.")
            if st.button("🔁 Sliding Window Retrain"):
                with st.spinner("Engineering features for new data..."):
                    create_features_for_new_data(actual_df)
                with st.spinner("Retraining model with sliding window (last 6 months)..."):
                    metrics = sliding_window_retrain()
                st.success("✅ Retrain complete!")
                c1, c2, c3 = st.columns(3)
                c1.metric("MAE",  f"{metrics.get('MAE',  0):.4f}")
                c2.metric("RMSE", f"{metrics.get('RMSE', 0):.4f}")
                c3.metric("MAPE", f"{metrics.get('MAPE', 0):.4f}")
                st.session_state["model_updated"] = True

        # ─────────────────────────────────────────────
        # SECTION 4: Predict Next Month
        # ─────────────────────────────────────────────
        st.header("4. Predict Next Month")

        if st.button("🔮 Generate Next Month Forecast"):
            with st.spinner("Generating recursive forecast..."):
                out_df = predict_next_month()

            st.success(f"✅ Predicted {len(out_df):,} rows for next month.")
            st.dataframe(out_df.head(20), use_container_width=True)

            # Aggregated daily chart
            agg = out_df.groupby("date")["predicted_sales"].sum().reset_index()
            fig2, ax2 = plt.subplots(figsize=(10, 4))
            ax2.plot(agg["date"], agg["predicted_sales"], color="tab:blue", linewidth=2)
            ax2.set_title("Next Month — Total Predicted Daily Sales")
            ax2.set_xlabel("Date"); ax2.set_ylabel("Units")
            st.pyplot(fig2)

            # Upgrade F: store-level breakdown if store_id available
            if "store_id" in out_df.columns:
                st.markdown("**Store-Level Forecast**")
                store_agg = out_df.groupby("store_id")["predicted_sales"].sum().reset_index().sort_values("predicted_sales", ascending=False)
                fig3, ax3 = plt.subplots(figsize=(10, 3))
                ax3.bar(store_agg["store_id"].astype(str), store_agg["predicted_sales"], color="tab:green")
                ax3.set_title("Total Predicted Sales by Store")
                ax3.set_xlabel("Store"); ax3.set_ylabel("Units")
                plt.xticks(rotation=45)
                st.pyplot(fig3)

            csv = out_df.to_csv(index=False).encode("utf-8")
            st.download_button(
                label="⬇️ Download Predictions as CSV",
                data=csv,
                file_name=f"next_month_predictions_{out_df['date'].min().date()}.csv",
                mime="text/csv"
            )

else:
    st.info("👆 Upload the actual month CSV to get started.")

    pred_path = f"{PROCESSED_DIR}/predictions.parquet"
    if os.path.exists(pred_path):
        st.subheader("Last Known Predictions")
        df  = pd.read_parquet(pred_path)
        agg = df.groupby("date")["yhat"].sum().reset_index()
        fig, ax = plt.subplots(figsize=(10, 3))
        ax.plot(agg["date"], agg["yhat"], color="tab:orange")
        ax.set_title("Aggregated Predicted Sales (Last Run)")
        ax.set_xlabel("Date"); ax.set_ylabel("Units")
        st.pyplot(fig)
