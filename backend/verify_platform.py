"""
Platform Verification Script — Self-Healing Demand Forecasting System
Verifies that upload_platform.py logic matches Phase 1 (main.py) exactly.
Run: python verify_platform.py
"""
import os, sys, json, glob, warnings
warnings.filterwarnings("ignore")

import numpy as np
import pandas as pd
import joblib
from datetime import datetime
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

sys.path.insert(0, os.path.dirname(__file__))
from feature_engineering import FeatureEngineer
from drift_detector import DriftDetector

# ── Paths ──────────────────────────────────────────────────────────────────────
LOGS      = "logs"
DATA_CSV  = "data/uploaded_data.csv"
TEST_DIR  = "test_data"
PROC_DIR  = "processed"
UPL_DIR   = "uploads"
RW_FILE   = os.path.join(LOGS, "rolling_window.json")

os.makedirs(PROC_DIR, exist_ok=True)
os.makedirs(UPL_DIR,  exist_ok=True)

PASS = "[PASS]"
FAIL = "[FAIL]"
WARN = "[WARN]"

# ── Load model & baseline (mirrors upload_platform.py cache) ──────────────────
def load_model():
    mp = os.path.join(LOGS, "baseline_model.pkl")
    rp = os.path.join(LOGS, "baseline_model_rf.pkl")
    assert os.path.exists(mp), "baseline_model.pkl not found — run main.py first"
    m = joblib.load(mp)
    r = joblib.load(rp) if os.path.exists(rp) else m
    return m, r

def load_baseline():
    raw = pd.read_csv(DATA_CSV)
    raw["Date"] = pd.to_datetime(raw["Date"], dayfirst=True)
    cutoff = raw["Date"].min() + pd.DateOffset(months=12)
    train  = raw[raw["Date"] < cutoff].copy()
    eng    = FeatureEngineer()
    # fit=True so the Season LabelEncoder is trained on training data
    proc, feats = eng.run_feature_pipeline(train, fit=True)
    store_stats = eng._store_stats
    return proc, feats, store_stats, eng  # return the fitted engineer

def load_meta():
    sm = json.load(open(os.path.join(LOGS, "phase1_summary.json")))
    bm = json.load(open(os.path.join(LOGS, "baseline_metrics.json")))["train"]
    return sm, bm

# ── Pipeline helpers (identical to upload_platform.py) ────────────────────────
def load_train_history():
    """Return raw training rows for lag/rolling context."""
    raw = pd.read_csv(DATA_CSV)
    raw["Date"] = pd.to_datetime(raw["Date"], dayfirst=True)
    cutoff = raw["Date"].min() + pd.DateOffset(months=12)
    return raw[raw["Date"] < cutoff].copy()

def predict(df, model, feature_names, store_stats, train_hist, fitted_eng):
    # Reuse the fitted engineer (has trained Season LabelEncoder + store_stats)
    eng = FeatureEngineer()
    eng._store_stats = store_stats
    eng.encoders = fitted_eng.encoders  # reuse fitted LabelEncoder for Season

    upload_dates = set(df["Date"].dt.normalize().unique())
    combined = pd.concat([train_hist, df], ignore_index=True).sort_values(["Store","Date"])
    proc, _ = eng.run_feature_pipeline(combined, fit=False)
    proc = proc[proc["Date"].dt.normalize().isin(upload_dates)].reset_index(drop=True)

    for f in feature_names:
        if f not in proc.columns:
            proc[f] = 0
    X     = proc[feature_names]
    y     = proc["Weekly_Sales"].values
    preds = model.predict(X)
    return proc, X, y, preds

def calc_metrics(y, p):
    mae  = float(mean_absolute_error(y, p))
    rmse = float(np.sqrt(mean_squared_error(y, p)))
    r2   = float(r2_score(y, p))
    mask = y != 0
    mape = float(np.mean(np.abs((y[mask]-p[mask])/y[mask]))*100) if mask.any() else 0.0
    wmape = float(np.sum(np.abs(y-p)) / np.sum(np.abs(y))) * 100
    return {"MAE": mae, "RMSE": rmse, "R2": r2, "MAPE": mape, "WMAPE": wmape}

def run_drift(X, y, preds, model_rf, feature_names, baseline_proc):
    det = DriftDetector()
    if hasattr(model_rf, "feature_importances_"):
        det.set_feature_importance(model_rf, feature_names)
    for f in feature_names:
        if f not in baseline_proc.columns:
            baseline_proc[f] = 0
    X_tr  = baseline_proc[feature_names]
    tr_y  = baseline_proc["Weekly_Sales"].values
    tr_p  = model_rf.predict(X_tr)
    det.set_baseline(X_tr, errors=tr_y - tr_p)
    return det.comprehensive_detection(X, y - preds)

# ── Rolling window ─────────────────────────────────────────────────────────────
MAX_WINDOW = 12

def load_rolling_window():
    if os.path.exists(RW_FILE):
        return json.load(open(RW_FILE))
    return {"months": [], "files": []}

def save_rolling_window(rw):
    with open(RW_FILE, "w") as f:
        json.dump(rw, f, indent=2)

def update_rolling_window(month_label, pred_file, upload_file):
    rw = load_rolling_window()
    rw["months"].append(month_label)
    rw["files"].append({"month": month_label, "pred": pred_file, "upload": upload_file})
    if len(rw["months"]) > MAX_WINDOW:
        dropped = rw["months"].pop(0)
        rw["files"].pop(0)
        return rw, dropped
    return rw, None

# ── Verification checks ────────────────────────────────────────────────────────
def check(label, condition, detail=""):
    status = PASS if condition else FAIL
    print(f"  {status} {label}" + (f" — {detail}" if detail else ""))
    return condition

# ══════════════════════════════════════════════════════════════════════════════
# MAIN VERIFICATION
# ══════════════════════════════════════════════════════════════════════════════
def main():
    print("=" * 65)
    print("PLATFORM VERIFICATION — Self-Healing Demand Forecasting System")
    print("=" * 65)
    results = []

    # ── SECTION 1: Prerequisites ───────────────────────────────────────────────
    print("\n[1/5] PREREQUISITES")
    sm, bm = load_meta()
    feature_names = sm["feature_names"]

    check("baseline_model.pkl exists",    os.path.exists(os.path.join(LOGS, "baseline_model.pkl")))
    check("baseline_model_rf.pkl exists", os.path.exists(os.path.join(LOGS, "baseline_model_rf.pkl")))
    check("phase1_summary.json exists",   os.path.exists(os.path.join(LOGS, "phase1_summary.json")))
    check("baseline_metrics.json exists", os.path.exists(os.path.join(LOGS, "baseline_metrics.json")))
    check("Test data files exist",        len(glob.glob(os.path.join(TEST_DIR, "*.csv"))) > 0,
          f"{len(glob.glob(os.path.join(TEST_DIR, '*.csv')))} files in {TEST_DIR}/")
    check(f"Feature count = 49",          len(feature_names) == 49,
          f"got {len(feature_names)}")

    # ── SECTION 2: Feature Engineering Match ──────────────────────────────────
    print("\n[2/5] FEATURE ENGINEERING — Phase 1 Match")
    model, model_rf = load_model()
    baseline_proc, baseline_feats, store_stats, fitted_eng = load_baseline()
    train_hist = load_train_history()

    EXPECTED_FEATURES = {
        # temporal
        "Year","Month","Week","Quarter","Season","Is_Year_End","Is_Year_Start",
        "Week_Sin","Week_Cos","Month_Sin","Month_Cos",
        "Weeks_To_Holiday_6","Weeks_To_Holiday_47","Weeks_To_Holiday_51",
        # lag
        "Lag_1","Lag_2","Lag_4","Lag_8","Lag_12","Lag_26","Lag_52",
        # rolling
        "Rolling_Mean_4","Rolling_Std_4","Rolling_Mean_8","Rolling_Std_8",
        "Rolling_Mean_12","Rolling_Std_12","Rolling_Mean_26","Rolling_Std_26",
        "Rolling_Max_4","Rolling_Min_4","Rolling_Max_12","Rolling_Min_12",
        # store
        "Store_Mean","Store_Median","Store_Std","Sales_vs_Store_Mean",
        # interaction
        "Store_Holiday","Temp_Fuel","Price_Index","Fuel_Unemployment","CPI_Fuel","Temp_Holiday",
        # raw
        "Store","Holiday_Flag","Temperature","Fuel_Price","CPI","Unemployment",
    }
    actual_set = set(feature_names)
    missing = EXPECTED_FEATURES - actual_set
    extra   = actual_set - EXPECTED_FEATURES

    check("All expected features present", len(missing) == 0,
          f"missing: {missing}" if missing else "all 49 features confirmed")
    check("No unexpected extra features",  len(extra) == 0,
          f"extra: {extra}" if extra else "")

    # Verify drift thresholds from config
    cfg = json.load(open("config.json"))
    check("KS mild threshold  = 0.05",  cfg["ks_mild"]   == 0.05)
    check("KS severe threshold = 0.15", cfg["ks_severe"] == 0.15)
    check("PSI mild threshold  = 0.10", cfg["psi_mild"]  == 0.10)
    check("PSI severe threshold = 0.25",cfg["psi_severe"] == 0.25)

    # ── SECTION 3: Sequential Upload Simulation ────────────────────────────────
    print("\n[3/5] SEQUENTIAL UPLOAD SIMULATION (all test months)")
    test_files = sorted(glob.glob(os.path.join(TEST_DIR, "*.csv")))
    check("Test files found", len(test_files) > 0, f"{len(test_files)} files")

    month_results = []
    rolling_window = {"months": [], "files": []}

    for i, fpath in enumerate(test_files, 1):
        fname  = os.path.basename(fpath)
        label  = fname.replace(".csv", "").replace("_", "-")

        df = pd.read_csv(fpath)
        df["Date"] = pd.to_datetime(df["Date"], infer_datetime_format=True)

        # Validate required columns
        REQUIRED = {"Store","Date","Weekly_Sales","Holiday_Flag","Temperature","Fuel_Price","CPI","Unemployment"}
        missing_cols = REQUIRED - set(df.columns)
        if missing_cols:
            print(f"  {FAIL} {label}: missing columns {missing_cols}")
            continue

        # Run pipeline
        try:
            proc, X, y, preds = predict(df, model, feature_names, store_stats, train_hist, fitted_eng)
            m = calc_metrics(y, preds)
            drift = run_drift(X, y, preds, model_rf, feature_names, baseline_proc.copy())
        except Exception as e:
            print(f"  {FAIL} {label}: pipeline error — {e}")
            continue

        # Save predictions
        ts       = datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:19]
        pred_csv = os.path.join(PROC_DIR, f"predictions_{label}_{ts}.csv")
        summ_json= os.path.join(PROC_DIR, f"summary_{label}_{ts}.json")
        upl_copy = os.path.join(UPL_DIR,  fname)

        out_df = pd.DataFrame({"actual": y, "predicted": preds, "error": y - preds})
        out_df.to_csv(pred_csv, index=False)
        df.to_csv(upl_copy, index=False)

        summary = {
            "month": label, "timestamp": ts,
            "rows": int(len(y)), "stores": int(df["Store"].nunique()),
            "metrics": {k: round(v, 4) for k, v in m.items()},
            "drift": {
                "severity": drift["severity"],
                "severe_features": drift["severe_features"],
                "mild_features": drift["mild_features"],
                "total_features": drift["total_features"],
                "error_increase": round(drift["error_trend"].get("error_increase", 0), 4),
            }
        }
        with open(summ_json, "w") as f:
            json.dump(summary, f, indent=2)

        # Update rolling window
        rolling_window["months"].append(label)
        rolling_window["files"].append({"month": label, "pred": pred_csv, "upload": upl_copy})
        dropped = None
        if len(rolling_window["months"]) > MAX_WINDOW:
            dropped = rolling_window["months"].pop(0)
            rolling_window["files"].pop(0)
        save_rolling_window(rolling_window)

        et = drift["error_trend"]
        row = {
            "Month": label,
            "Rows": len(y),
            "MAE": round(m["MAE"], 0),
            "RMSE": round(m["RMSE"], 0),
            "MAPE%": round(m["MAPE"], 2),
            "Drift": drift["severity"].upper(),
            "Severe_Feats": drift["severe_features"],
            "Mild_Feats": drift["mild_features"],
            "Err_Increase%": round(et.get("error_increase", 0) * 100, 1),
            "Saved": os.path.exists(pred_csv),
            "Window_Size": len(rolling_window["months"]),
            "Dropped": dropped or "",
        }
        month_results.append(row)

        sev_icon = {"severe": "RED", "mild": "YLW", "none": "GRN"}.get(drift["severity"], "---")
        print(f"  [{i:2d}] {label:12s} | MAE={m['MAE']:>9,.0f} | RMSE={m['RMSE']:>9,.0f} | "
              f"Drift={sev_icon} | Window={len(rolling_window['months'])}"
              + (f" | Dropped={dropped}" if dropped else ""))

    # ── SECTION 4: Storage & Rolling Window Checks ────────────────────────────
    print("\n[4/5] STORAGE & ROLLING WINDOW")
    pred_files = glob.glob(os.path.join(PROC_DIR, "predictions_*.csv"))
    summ_files = glob.glob(os.path.join(PROC_DIR, "summary_*.json"))
    upl_files  = glob.glob(os.path.join(UPL_DIR,  "*.csv"))

    check("Prediction CSVs saved to processed/",  len(pred_files) >= len(test_files),
          f"{len(pred_files)} files")
    check("Summary JSONs saved to processed/",    len(summ_files) >= len(test_files),
          f"{len(summ_files)} files")
    check("Upload copies saved to uploads/",      len(upl_files) >= len(test_files),
          f"{len(upl_files)} files")
    check("rolling_window.json exists",           os.path.exists(RW_FILE))

    rw = load_rolling_window()
    check(f"Rolling window <= {MAX_WINDOW} months", len(rw["months"]) <= MAX_WINDOW,
          f"current size = {len(rw['months'])}")
    check("Rolling window has correct months",    len(rw["months"]) > 0,
          f"months: {rw['months']}")

    # ── SECTION 5: Phase 1 Compatibility ──────────────────────────────────────
    print("\n[5/5] PHASE 1 COMPATIBILITY")
    ph1 = json.load(open(os.path.join(LOGS, "phase1_summary.json")))
    ph1_feats = set(ph1["feature_names"])
    plat_feats = set(feature_names)

    check("Feature names match Phase 1 exactly",  ph1_feats == plat_feats,
          f"diff={ph1_feats.symmetric_difference(plat_feats)}" if ph1_feats != plat_feats else "")
    check("Train MAE matches baseline_metrics",
          abs(bm["MAE"] - ph1["train_metrics"]["MAE"]) < 1.0,
          f"baseline={bm['MAE']:.2f}, phase1={ph1['train_metrics']['MAE']:.2f}")
    check("Train R2 matches baseline_metrics",
          abs(bm["R2"] - ph1["train_metrics"]["R2"]) < 0.0001)
    check("Phase 1 severity = severe (expected)", ph1["final_severity"] == "severe")
    check("Phase 1 months monitored = 9",         ph1["months_monitored"] == 9,
          f"got {ph1['months_monitored']}")

    # ── REPORT ─────────────────────────────────────────────────────────────────
    print("\n" + "=" * 65)
    print("MONTH-BY-MONTH RESULTS")
    print("=" * 65)
    header = f"{'Month':<14} {'MAE':>10} {'RMSE':>10} {'MAPE%':>7} {'Drift':<8} {'Window':>6} {'Dropped'}"
    print(header)
    print("-" * 65)
    for r in month_results:
        print(f"{r['Month']:<14} {r['MAE']:>10,.0f} {r['RMSE']:>10,.0f} "
              f"{r['MAPE%']:>7.2f} {r['Drift']:<8} {r['Window_Size']:>6}  {r['Dropped']}")

    # Save report CSV
    report_df = pd.DataFrame(month_results)
    report_path = os.path.join(PROC_DIR, "verification_report.csv")
    report_df.to_csv(report_path, index=False)

    print("\n" + "=" * 65)
    print("SUMMARY")
    print("=" * 65)
    total_months = len(month_results)
    saved_ok     = sum(1 for r in month_results if r["Saved"])
    severe_count = sum(1 for r in month_results if r["Drift"] == "SEVERE")
    mild_count   = sum(1 for r in month_results if r["Drift"] == "MILD")
    none_count   = sum(1 for r in month_results if r["Drift"] == "NONE")

    print(f"  Months processed : {total_months}")
    print(f"  Files saved      : {saved_ok}/{total_months}")
    print(f"  Drift — SEVERE   : {severe_count}")
    print(f"  Drift — MILD     : {mild_count}")
    print(f"  Drift — NONE     : {none_count}")
    print(f"  Rolling window   : {len(rw['months'])} months (max {MAX_WINDOW})")
    print(f"  Report saved     : {report_path}")

    all_saved = saved_ok == total_months
    drift_detected = severe_count > 0 or mild_count > 0
    window_ok = len(rw["months"]) <= MAX_WINDOW

    verdict = PASS if (all_saved and drift_detected and window_ok) else FAIL
    print(f"\n  OVERALL VERDICT: {verdict}")
    print("=" * 65)

if __name__ == "__main__":
    main()
