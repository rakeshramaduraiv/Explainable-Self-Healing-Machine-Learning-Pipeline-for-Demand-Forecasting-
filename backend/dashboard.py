import json, os, warnings, time
import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import streamlit as st
import joblib
from demand_analyzer import DemandAnalyzer

warnings.filterwarnings("ignore")

st.set_page_config(page_title="SH-DFS Monitor", layout="wide", initial_sidebar_state="expanded")

if "dark" not in st.session_state:
    st.session_state.dark = False

# Read AFTER any potential rerun so the value is always current
D = st.session_state.dark

# ── Palette ───────────────────────────────────────────────────────────────────
if D:
    BG      = "#0f172a"
    SIDEBAR = "#111827"
    CARD    = "#1e293b"
    BORDER  = "#334155"
    TEXT    = "#f1f5f9"
    TEXT2   = "#94a3b8"
    TEXT3   = "#475569"
    HOVER   = "#1e293b"
    ACTIVE  = "#1d4ed8"
    ACTIVE_BG = "rgba(59,130,246,0.12)"
else:
    BG      = "#f1f5f9"
    SIDEBAR = "#ffffff"
    CARD    = "#ffffff"
    BORDER  = "#cbd5e1"
    TEXT    = "#0f172a"
    TEXT2   = "#1e293b"
    TEXT3   = "#475569"
    HOVER   = "#e2e8f0"
    ACTIVE  = "#1d4ed8"
    ACTIVE_BG = "#dbeafe"

BLUE   = "#3b82f6"
GREEN  = "#10b981"
ORANGE = "#f59e0b"
RED    = "#ef4444"
PURPLE = "#8b5cf6"
GR     = "rgba(255,255,255,0.03)" if D else "rgba(0,0,0,0.03)"

PLOT = dict(
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor=CARD,
    font=dict(color=TEXT2, family="Inter", size=12),
    legend=dict(bgcolor="rgba(0,0,0,0)", font=dict(color=TEXT2, size=11),
                bordercolor=BORDER, borderwidth=1),
    margin=dict(t=36, b=28, l=8, r=8),
    hoverlabel=dict(bgcolor=CARD, bordercolor=BORDER, font=dict(color=TEXT, size=12)),
)

# ── Global CSS ────────────────────────────────────────────────────────────────
st.markdown(f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap');
*{{box-sizing:border-box}}
html,body,[class*="css"]{{font-family:'Inter',sans-serif;background:{BG};color:{TEXT}}}
.stApp{{background:{BG}}}
#MainMenu,footer,header{{visibility:hidden}}

/* ── Sidebar ── */
section[data-testid="stSidebar"]{{
  background:{SIDEBAR}!important;
  border-right:1px solid {BORDER}!important;
  min-width:220px!important;max-width:220px!important;
}}
section[data-testid="stSidebar"] > div{{padding:0!important}}

/* ── Hide default radio bullets, style as nav items ── */
div[data-testid="stRadio"] > label{{display:none}}
div[data-testid="stRadio"] > div{{gap:1px!important}}
div[data-testid="stRadio"] label{{
  display:flex!important;align-items:center!important;
  padding:8px 16px!important;border-radius:0!important;
  font-size:13px!important;font-weight:500!important;
  color:{TEXT2}!important;cursor:pointer!important;
  transition:background .1s,color .1s!important;
  border-left:3px solid transparent!important;
  margin:0!important;width:100%!important;
}}
div[data-testid="stRadio"] label:hover{{
  background:{HOVER}!important;color:{TEXT}!important;
}}
div[data-testid="stRadio"] label[data-baseweb="radio"] span:first-child{{display:none!important}}

/* ── Metrics ── */
div[data-testid="stMetric"]{{
  background:{CARD};border:1px solid {BORDER};border-radius:8px;
  padding:16px 18px;transition:border-color .15s;
}}
div[data-testid="stMetric"]:hover{{border-color:{BLUE}}}
div[data-testid="stMetric"] label{{
  color:{TEXT3}!important;font-size:10px!important;
  text-transform:uppercase;letter-spacing:1.2px;font-weight:600;
}}
div[data-testid="stMetric"] [data-testid="stMetricValue"]{{
  color:{TEXT}!important;font-family:'JetBrains Mono',monospace!important;
  font-size:20px!important;font-weight:700!important;
}}
div[data-testid="stMetricDelta"]{{font-size:11px!important;color:{TEXT2}!important}}

/* ── Light-mode text contrast ── */
[data-testid="stMarkdownContainer"] *,
[data-testid="stText"] *,
[data-testid="stCaptionContainer"] * {{
  color:{TEXT}!important;
}}
.stSelectbox label, .stSlider label, .stTextInput label,
.stFileUploader label, .stRadio label, .stCheckbox label,
.stExpander label, [data-testid="stExpander"] summary {{
  color:{TEXT}!important;
}}
[data-testid="stSidebar"] [data-testid="stMarkdownContainer"] * {{
  color:{TEXT2}!important;
}}
[data-testid="stMetric"] label {{ color:{TEXT3}!important; }}
[data-testid="stMetricValue"] {{ color:{TEXT}!important; }}
[data-testid="stMetricDelta"] {{ color:{TEXT2}!important; }}
.stDataFrame * {{ color:{TEXT}!important; }}
[data-testid="stTable"] * {{ color:{TEXT}!important; }}

/* ── Inputs ── */
.stSelectbox>div>div{{
  background:{CARD}!important;border:1px solid {BORDER}!important;
  border-radius:6px!important;color:{TEXT}!important;font-size:13px!important;
}}
.stSlider label{{color:{TEXT2}!important;font-size:12px!important}}
.stDataFrame{{border-radius:8px;overflow:hidden;border:1px solid {BORDER}}}
.stFileUploader>div{{
  background:{CARD}!important;border:2px dashed {BORDER}!important;border-radius:8px!important;
}}
.stDownloadButton>button{{
  background:transparent!important;border:1px solid {BORDER}!important;
  color:{TEXT2}!important;border-radius:6px!important;font-size:12px!important;
  font-weight:500!important;padding:6px 14px!important;
}}
.stDownloadButton>button:hover{{border-color:{BLUE}!important;color:{BLUE}!important}}
button[kind="primary"]{{
  background:{BLUE}!important;border:none!important;border-radius:6px!important;
  font-weight:600!important;font-size:13px!important;
}}

/* ── Scrollbar ── */
::-webkit-scrollbar{{width:4px;height:4px}}
::-webkit-scrollbar-thumb{{background:{BORDER};border-radius:4px}}

/* ── Custom components ── */
.card{{
  background:{CARD};border:1px solid {BORDER};border-radius:8px;
  padding:18px 20px;margin-bottom:12px;
}}
.card-title{{
  font-size:10px;font-weight:700;color:{TEXT3};
  text-transform:uppercase;letter-spacing:1.8px;margin-bottom:14px;
}}
.kv{{
  display:flex;justify-content:space-between;align-items:center;
  padding:5px 0;border-bottom:1px solid {BORDER};font-size:13px;
}}
.kv:last-child{{border-bottom:none}}
.kv .k{{color:{TEXT2}}}
.kv .v{{color:{TEXT};font-family:'JetBrains Mono',monospace;font-size:11px}}
.badge{{
  display:inline-flex;align-items:center;padding:2px 9px;
  border-radius:4px;font-size:11px;font-weight:600;letter-spacing:.5px;
}}
.b-red{{background:rgba(239,68,68,0.1);color:{RED};border:1px solid rgba(239,68,68,0.25)}}
.b-orange{{background:rgba(245,158,11,0.1);color:{ORANGE};border:1px solid rgba(245,158,11,0.25)}}
.b-green{{background:rgba(16,185,129,0.1);color:{GREEN};border:1px solid rgba(16,185,129,0.25)}}
.b-blue{{background:rgba(59,130,246,0.1);color:{BLUE};border:1px solid rgba(59,130,246,0.25)}}
.divider{{height:1px;background:{BORDER};margin:12px 0}}
.section-label{{
  font-size:10px;font-weight:700;color:{TEXT3};
  text-transform:uppercase;letter-spacing:1.8px;
  margin:16px 0 8px;display:flex;align-items:center;gap:8px;
}}
.section-label::after{{content:'';flex:1;height:1px;background:{BORDER}}}
.alert{{border-radius:0 6px 6px 0;padding:10px 14px;font-size:13px;margin:6px 0;line-height:1.5}}
.alert-r{{background:rgba(239,68,68,0.06);border-left:3px solid {RED};color:{TEXT2}}}
.alert-y{{background:rgba(245,158,11,0.06);border-left:3px solid {ORANGE};color:{TEXT2}}}
.alert-g{{background:rgba(16,185,129,0.06);border-left:3px solid {GREEN};color:{TEXT2}}}
.alert-b{{background:rgba(59,130,246,0.06);border-left:3px solid {BLUE};color:{TEXT2}}}
.step-row{{display:flex;align-items:center;gap:10px;padding:6px 0;border-bottom:1px solid {BORDER};font-size:13px}}
.step-row:last-child{{border-bottom:none}}
.dot{{width:20px;height:20px;border-radius:50%;display:inline-flex;align-items:center;justify-content:center;font-size:9px;font-weight:700;color:#fff;flex-shrink:0}}
.dot-done{{background:{GREEN}}}
.dot-active{{background:{ORANGE};animation:pulse 1.2s infinite}}
.dot-wait{{background:{BORDER};color:{TEXT3}}}
@keyframes pulse{{0%,100%{{box-shadow:0 0 0 0 rgba(245,158,11,.4)}}50%{{box-shadow:0 0 0 5px rgba(245,158,11,0)}}}}
</style>
""", unsafe_allow_html=True)

# ── Data loaders ──────────────────────────────────────────────────────────────
LOGS      = "logs"
DATA_PATH = "data/uploaded_data.csv"

@st.cache_data(ttl=30)
def load_json(fname):
    p = os.path.join(LOGS, fname)
    return json.load(open(p)) if os.path.exists(p) else None

@st.cache_data(ttl=30)
def load_drift():
    raw = load_json("drift_history.json") or []
    seen, out = set(), []
    for d in reversed(raw):
        if d["month"] not in seen:
            seen.add(d["month"]); out.insert(0, d)
    return sorted(out, key=lambda x: x["month"])

@st.cache_data(ttl=30)
def load_batches():
    raw = load_json("prediction_batches.json") or []
    seen, out = set(), []
    for d in reversed(raw):
        if d["month"] not in seen:
            seen.add(d["month"]); out.insert(0, d)
    return sorted(out, key=lambda x: x["month"])

@st.cache_resource(show_spinner=False)
def load_model():
    mp = os.path.join("models", "active_model.pkl")
    rp = os.path.join("models", "baseline_model_rf.pkl")
    if not os.path.exists(mp): return None, None
    return joblib.load(mp), joblib.load(rp) if os.path.exists(rp) else joblib.load(mp)

@st.cache_data(ttl=300)
def load_importance():
    try:
        s = load_json("phase1_summary.json") or {}
        feats = s.get("feature_names", [])
        _, rf = load_model()
        if feats and rf and hasattr(rf, "feature_importances_"):
            pairs = sorted(zip(feats, rf.feature_importances_), key=lambda x: x[1], reverse=True)
            return [p[0] for p in pairs], [p[1] for p in pairs]
    except Exception:
        pass
    return [], []

@st.cache_data(ttl=300)
def load_real_feature_data():
    if not os.path.exists(DATA_PATH): return None, None, None
    try:
        from feature_engineering import FeatureEngineer
        from scipy.stats import ks_2samp
        fn = (load_json("phase1_summary.json") or {}).get("feature_names", [])
        if not fn: return None, None, None
        raw = pd.read_csv(DATA_PATH)
        raw["Date"] = pd.to_datetime(raw["Date"], dayfirst=True)
        cut = raw["Date"].min() + pd.DateOffset(months=12)
        eng = FeatureEngineer()
        tr, _ = eng.run_feature_pipeline(raw[raw["Date"] < cut].copy(), fit=True)
        te, _ = eng.run_feature_pipeline(raw[raw["Date"] >= cut].copy(), fit=False)
        ks = {}
        for f in fn:
            if f in tr.columns and f in te.columns:
                a, b = tr[f].dropna().values, te[f].dropna().values
                if len(a) > 5 and len(b) > 5:
                    s, p = ks_2samp(a, b)
                    ks[f] = {"ks": round(float(s), 4), "pval": round(float(p), 4)}
        return tr, te, ks
    except Exception:
        return None, None, None

# ── Global state ──────────────────────────────────────────────────────────────
summary    = load_json("phase1_summary.json")
metrics    = load_json("baseline_metrics.json")
drift_data = load_drift()
batches    = load_batches()
feat_names, feat_imp = load_importance()

tm    = (metrics or {}).get("train", {})
RMSE  = tm.get("RMSE",  9118)
MAE   = tm.get("MAE",   6910)
R2    = tm.get("R2",    0.9997)
MAPE  = tm.get("MAPE",  0.84)
WMAPE = tm.get("WMAPE", 0.66)
SEV   = (summary or {}).get("final_severity", "severe")
MONTHS_MON = (summary or {}).get("months_monitored", len(drift_data))
SEV_CLS = "b-red" if SEV == "severe" else ("b-orange" if SEV == "mild" else "b-green")

# ── SIDEBAR ───────────────────────────────────────────────────────────────────
NAV_ITEMS = [
    ("Dashboard",         "Overview"),
    ("Demand Insights",   "Demand Insights"),
    ("Datasets",          "Datasets"),
    ("Reports",           "Reports"),
    ("Traces",            "Model Performance"),
    ("Feature Analysis",  "Feature Importance"),
    ("Alerts",            "Alerts"),
    ("Upload & Monitor",  "Upload & Monitor"),
]

with st.sidebar:
    # Project header
    st.markdown(f"""
    <div style="padding:20px 16px 14px;border-bottom:1px solid {BORDER}">
      <div style="font-size:11px;color:{TEXT3};font-weight:500;margin-bottom:6px">PROJECT</div>
      <div style="font-size:14px;font-weight:700;color:{TEXT};letter-spacing:-.2px">SH-DFS Monitor</div>
      <div style="font-size:10px;color:{TEXT3};margin-top:3px;font-family:'JetBrains Mono',monospace">
        Phase 1 · ML Monitoring
      </div>
    </div>
    """, unsafe_allow_html=True)

    # Theme toggle — flip state then rerun so CSS rebuilds with new palette
    st.markdown(f"<div style='padding:10px 16px 4px'>", unsafe_allow_html=True)
    btn_label = "Switch to Light" if D else "Switch to Dark"
    if st.button(btn_label, key="theme_btn", width='stretch'):
        st.session_state.dark = not st.session_state.dark
        st.cache_data.clear()
        st.rerun()
    st.markdown("</div>", unsafe_allow_html=True)

    # Nav section label
    st.markdown(f"""
    <div style="padding:14px 16px 6px;font-size:10px;font-weight:700;
      color:{TEXT3};text-transform:uppercase;letter-spacing:1.8px">
      Project Navigation
    </div>
    """, unsafe_allow_html=True)

    # Navigation radio (labels are the display names)
    display_labels = [item[0] for item in NAV_ITEMS]
    selected_label = st.radio("nav", display_labels, label_visibility="collapsed")
    # Map display label → internal page key
    page = dict(NAV_ITEMS)[selected_label]

    # Divider + thresholds
    st.markdown(f"<div style='height:1px;background:{BORDER};margin:12px 0'></div>", unsafe_allow_html=True)
    st.markdown(f"""
    <div style="padding:0 16px 6px;font-size:10px;font-weight:700;
      color:{TEXT3};text-transform:uppercase;letter-spacing:1.8px">
      Drift Thresholds
    </div>
    """, unsafe_allow_html=True)
    with st.container():
        ks_mild    = st.slider("KS Mild",    0.05, 0.30, 0.10, 0.01)
        ks_severe  = st.slider("KS Severe",  0.10, 0.50, 0.20, 0.01)
        psi_mild   = st.slider("PSI Mild",   0.05, 0.30, 0.10, 0.01)
        psi_severe = st.slider("PSI Severe", 0.10, 0.50, 0.25, 0.01)

    # Status pill
    st.markdown(f"<div style='height:1px;background:{BORDER};margin:10px 0'></div>", unsafe_allow_html=True)
    dot_c = RED if SEV == "severe" else (ORANGE if SEV == "mild" else GREEN)
    st.markdown(f"""
    <div style="margin:0 12px 12px;padding:10px 12px;border-radius:6px;
      background:{ACTIVE_BG};border:1px solid {BORDER}">
      <div style="display:flex;align-items:center;gap:8px">
        <div style="width:7px;height:7px;border-radius:50%;background:{dot_c}"></div>
        <div>
          <div style="font-size:11px;font-weight:700;color:{dot_c}">{SEV.upper()} DRIFT</div>
          <div style="font-size:10px;color:{TEXT3}">{MONTHS_MON} months monitored</div>
        </div>
      </div>
    </div>
    """, unsafe_allow_html=True)

# ── Breadcrumb + page header ──────────────────────────────────────────────────
BREADCRUMB = {
    "Overview":          "Dashboard",
    "Demand Insights":   "Demand Insights",
    "Datasets":          "Datasets",
    "Reports":           "Reports",
    "Model Performance": "Traces",
    "Feature Importance":"Feature Analysis",
    "Alerts":            "Alerts",
    "Upload & Monitor":  "Upload & Monitor",
}
SUBTITLES = {
    "Overview":          "System health · drift status · executive summary",
    "Demand Insights":   "Demand metrics · trends · forecasting analysis",
    "Datasets":          "Reference dataset · uploaded batches · data management",
    "Reports":           "Generated drift and model reports · export · history",
    "Model Performance": "Actual vs predicted · MAE trend · error distribution",
    "Feature Importance":"Top features · importance scores · real distributions",
    "Alerts":            "Active drift alerts · severity · acknowledgement log",
    "Upload & Monitor":  "Upload new data · instant predictions · drift check",
}

crumb_page = BREADCRUMB[page]
proj_id    = (summary or {}).get("project_id", "shdfs-phase1-walmart")

st.markdown(f"""
<div style="padding:18px 0 0">
  <div style="font-size:12px;color:{TEXT3};margin-bottom:6px">
    Home &nbsp;/&nbsp; Projects &nbsp;/&nbsp;
    <span style="color:{TEXT2}">SH-DFS Monitor</span> &nbsp;/&nbsp;
    <span style="color:{TEXT}">{crumb_page}</span>
  </div>
  <div style="font-size:10px;color:{TEXT3};font-family:'JetBrains Mono',monospace;margin-bottom:14px">
    project id: {proj_id}
  </div>
</div>
""", unsafe_allow_html=True)

# Page title row
tc1, tc2 = st.columns([6, 1])
with tc1:
    st.markdown(f"""
    <div style="border-bottom:1px solid {BORDER};padding-bottom:14px;margin-bottom:20px">
      <div style="font-size:22px;font-weight:700;color:{TEXT};letter-spacing:-.4px">{page}</div>
      <div style="font-size:12px;color:{TEXT3};margin-top:3px">{SUBTITLES[page]}</div>
    </div>
    """, unsafe_allow_html=True)
with tc2:
    st.markdown(f"""
    <div style="padding-top:6px;text-align:right">
      <span class="badge {SEV_CLS}">{SEV.upper()}</span>
    </div>
    """, unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════════════════════
# PAGE: Overview (Dashboard)
# ══════════════════════════════════════════════════════════════════════════════
if page == "Overview":
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Model MAE",  f"${MAE:,.0f}",  "Training baseline")
    c2.metric("R² Score",   f"{R2:.4f}",      "Variance explained")
    c3.metric("RMSE",       f"${RMSE:,.0f}",  "Root mean sq error")
    c4.metric("MAPE",       f"{MAPE:.2f}%",   f"WMAPE {WMAPE:.2f}%")
    c5.metric("Months",     str(MONTHS_MON),  f"{SEV.upper()} drift")

    if drift_data:
        ml = [d["month"] for d in drift_data]
        ce = [d["error_trend"]["current_error"]  for d in drift_data]
        be = [d["error_trend"]["baseline_error"] for d in drift_data]
        sf = [d["severe_features"] for d in drift_data]
        mf = [d["mild_features"]   for d in drift_data]
        ei = [d["error_trend"]["error_increase"] for d in drift_data]

        st.markdown('<div class="section-label">Drift Severity Over Time</div>', unsafe_allow_html=True)
        fig = make_subplots(rows=1, cols=2, column_widths=[0.6, 0.4],
            subplot_titles=["Baseline vs Current MAE", "Drifted Features per Month"])
        fig.add_trace(go.Scatter(x=ml, y=be, name="Baseline MAE",
            line=dict(color=GREEN, width=2, dash="dash"), marker=dict(size=4)), row=1, col=1)
        fig.add_trace(go.Scatter(x=ml, y=ce, name="Current MAE",
            line=dict(color=RED, width=2.5), fill="tonexty",
            fillcolor="rgba(239,68,68,0.06)", marker=dict(size=4)), row=1, col=1)
        fig.add_trace(go.Bar(x=ml, y=sf, name="Severe", marker_color=RED, opacity=0.8), row=1, col=2)
        fig.add_trace(go.Bar(x=ml, y=mf, name="Mild",   marker_color=ORANGE, opacity=0.8), row=1, col=2)
        fig.update_layout(**PLOT, height=300, barmode="stack")
        fig.update_xaxes(gridcolor=GR, showline=False, tickangle=-45, tickfont=dict(size=9))
        fig.update_yaxes(gridcolor=GR, showline=False)
        for ann in fig.layout.annotations:
            ann.font.color = TEXT3; ann.font.size = 10
        st.plotly_chart(fig, width='stretch')

        st.markdown('<div class="section-label">Error Increase Ratio by Month</div>', unsafe_allow_html=True)
        fig_h = go.Figure(go.Heatmap(
            z=[ei], x=ml, y=["Error×"],
            colorscale=[[0,"rgba(16,185,129,0.6)"],[0.3,"rgba(245,158,11,0.7)"],[1,"rgba(239,68,68,0.9)"]],
            showscale=True, colorbar=dict(thickness=10, len=0.8, tickfont=dict(color=TEXT3, size=10)),
            text=[[f"{v:.2f}x" for v in ei]], texttemplate="%{text}",
            textfont=dict(size=10, color="white"),
            hovertemplate="Month: %{x}<br>Error Ratio: %{z:.2f}x<extra></extra>"))
        fig_h.update_layout(**{**PLOT, "height":100, "margin":dict(t=10,b=10,l=10,r=60)})
        fig_h.update_yaxes(showticklabels=False)
        st.plotly_chart(fig_h, width='stretch')

    st.markdown('<div class="section-label">System Summary</div>', unsafe_allow_html=True)
    ca, cb, cc = st.columns(3)
    split_info = load_json("data_split.json") or {}
    train_rows = split_info.get("train_rows", 2385)
    test_rows  = split_info.get("test_rows",  4050)
    cutoff_dt  = split_info.get("cutoff_date", "2011-02-05")
    with ca:
        st.markdown(f"""<div class="card">
        <div class="card-title">Dataset</div>
        <div class="kv"><span class="k">Source</span><span class="v">Walmart Weekly Sales</span></div>
        <div class="kv"><span class="k">Total Records</span><span class="v">6,435 rows</span></div>
        <div class="kv"><span class="k">Stores</span><span class="v">45</span></div>
        <div class="kv"><span class="k">Train rows</span><span class="v">{train_rows:,}</span></div>
        <div class="kv"><span class="k">Test rows</span><span class="v">{test_rows:,}</span></div>
        <div class="kv"><span class="k">Cutoff</span><span class="v">{cutoff_dt}</span></div>
        </div>""", unsafe_allow_html=True)
    with cb:
        insp = load_json("data_inspection.json") or {}
        dr = insp.get("date_range", ["2010-02-05", "2012-10-26"])
        st.markdown(f"""<div class="card">
        <div class="card-title">Model</div>
        <div class="kv"><span class="k">Algorithm</span><span class="v">Random Forest</span></div>
        <div class="kv"><span class="k">Features</span><span class="v">{len(feat_names)} engineered</span></div>
        <div class="kv"><span class="k">CV</span><span class="v">TimeSeriesSplit n=5</span></div>
        <div class="kv"><span class="k">Date Range</span><span class="v">{dr[0][:10]} to {dr[1][:10]}</span></div>
        <div class="kv"><span class="k">CI Coverage</span><span class="v">{(summary or {}).get('confidence_intervals',{}).get('coverage',1.0):.0%}</span></div>
        </div>""", unsafe_allow_html=True)
    with cc:
        rec = (summary or {}).get("recommendation", "Phase 2 retraining required")
        sc  = (summary or {}).get("severity_counts", {})
        ac  = RED if SEV == "severe" else ORANGE
        st.markdown(f"""<div class="card" style="border-color:rgba(239,68,68,0.3)">
        <div class="card-title">Status & Action</div>
        <div class="kv"><span class="k">Final Severity</span><span class="v" style="color:{ac};font-weight:700">{SEV.upper()}</span></div>
        <div class="kv"><span class="k">Severe months</span><span class="v" style="color:{RED}">{sc.get('severe',0)} / {MONTHS_MON}</span></div>
        <div class="kv"><span class="k">Mild months</span><span class="v" style="color:{ORANGE}">{sc.get('mild',0)} / {MONTHS_MON}</span></div>
        <div class="kv"><span class="k">Action</span><span class="v" style="color:{ORANGE}">Retrain Now</span></div>
        <div style="margin-top:8px;font-size:11px;color:{TEXT3};line-height:1.6">{rec}</div>
        </div>""", unsafe_allow_html=True)

    if drift_data:
        lat = drift_data[-1]
        st.markdown(f"""<div class="alert alert-r">
          <strong style="color:{RED}">Latest: {lat['month']}</strong> —
          {lat['severe_features']} severe features · {lat['mild_features']} mild ·
          MAE <strong style="color:{RED}">${lat['error_trend']['current_error']:,.0f}</strong>
          vs baseline <strong style="color:{GREEN}">${lat['error_trend']['baseline_error']:,.0f}</strong> ·
          ratio <strong style="color:{RED}">{lat['error_trend']['error_increase']:.2f}x</strong>
        </div>""", unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════════════════════
# PAGE: Demand Insights
# ══════════════════════════════════════════════════════════════════════════════
elif page == "Demand Insights":
    from demand_analyzer import DemandAnalyzer
    
    # Check if data exists
    if not os.path.exists(DATA_PATH):
        st.markdown(f'<div class="alert alert-r">No data uploaded yet. Please upload a dataset first in the Upload & Monitor page.</div>', unsafe_allow_html=True)
    else:
        try:
            # Initialize analyzer and load data
            analyzer = DemandAnalyzer()
            analyzer.load_data(DATA_PATH)
            metrics = analyzer.calculate_demand_metrics()
            
            # Display metrics cards
            st.markdown('<div class="section-label">Key Demand Metrics</div>', unsafe_allow_html=True)
            
            def format_number(num):
                if num >= 1_000_000:
                    return f"{num/1_000_000:.1f}M"
                elif num >= 1_000:
                    return f"{num/1_000:.1f}K"
                return f"{num:.0f}"
            
            c1, c2, c3, c4, c5 = st.columns(5)
            c1.metric("Average Weekly Demand", f"${format_number(metrics['avg_weekly_demand'])}")
            growth = metrics["demand_growth_rate"]
            c2.metric("Growth Rate (MoM)", f"{growth:+.1f}%", delta=f"{growth:.1f}%")
            c3.metric("Peak Demand Month", metrics["peak_demand_month"])
            c4.metric("Lowest Demand Month", metrics["lowest_demand_month"])
            c5.metric("Total Demand", f"${format_number(metrics['total_demand'])}")
            
            # Visualizations
            st.markdown('<div class="section-label">Demand Visualizations</div>', unsafe_allow_html=True)
            
            # Row 1: Demand Trend and Monthly Demand
            col1, col2 = st.columns(2)
            
            with col1:
                trend_data = analyzer.get_demand_trend_data()
                fig_trend = go.Figure()
                fig_trend.add_trace(go.Scatter(
                    x=trend_data["Date"], 
                    y=trend_data["Weekly_Sales"],
                    mode="lines+markers",
                    line=dict(color=BLUE, width=2),
                    marker=dict(size=4),
                    name="Weekly Sales",
                    hovertemplate="Date: %{x}<br>Sales: $%{y:,.0f}<extra></extra>"
                ))
                fig_trend.update_layout(**PLOT, height=300,
                    title=dict(text="Demand Trend Over Time", font=dict(color=TEXT3, size=12)),
                    xaxis=dict(title="Date", gridcolor=GR, tickangle=-45, tickfont=dict(size=9)),
                    yaxis=dict(title="Weekly Sales ($)", gridcolor=GR))
                st.plotly_chart(fig_trend, use_container_width=True)
            
            with col2:
                monthly_data = analyzer.get_monthly_demand_data()
                fig_monthly = go.Figure()
                fig_monthly.add_trace(go.Bar(
                    x=monthly_data["Date"],
                    y=monthly_data["Weekly_Sales"],
                    marker_color=ORANGE,
                    opacity=0.85,
                    name="Monthly Total",
                    text=[f"${v/1000:.0f}K" for v in monthly_data["Weekly_Sales"]],
                    textposition="outside",
                    textfont=dict(color=TEXT3, size=9),
                    hovertemplate="Month: %{x}<br>Total: $%{y:,.0f}<extra></extra>"
                ))
                fig_monthly.update_layout(**PLOT, height=300,
                    title=dict(text="Monthly Demand Aggregation", font=dict(color=TEXT3, size=12)),
                    xaxis=dict(title="Month", gridcolor=GR, tickangle=-45, tickfont=dict(size=9)),
                    yaxis=dict(title="Total Monthly Sales ($)", gridcolor=GR))
                st.plotly_chart(fig_monthly, use_container_width=True)
            
            # Store-Level Analysis (if applicable)
            store_data = analyzer.get_store_demand_data()
            if not store_data.empty:
                st.markdown('<div class="section-label">Store-Level Demand Analysis</div>', unsafe_allow_html=True)
                
                col1, col2 = st.columns(2)
                
                with col1:
                    fig_store = go.Figure()
                    fig_store.add_trace(go.Bar(
                        x=store_data["Store"],
                        y=store_data["Weekly_Sales"],
                        marker_color=GREEN,
                        opacity=0.85,
                        text=[f"${v/1000:.0f}K" for v in store_data["Weekly_Sales"]],
                        textposition="outside",
                        textfont=dict(color=TEXT3, size=9),
                        hovertemplate="%{x}<br>Total: $%{y:,.0f}<extra></extra>"
                    ))
                    fig_store.update_layout(**PLOT, height=300,
                        title=dict(text="Total Demand by Store", font=dict(color=TEXT3, size=12)),
                        xaxis=dict(title="Store", gridcolor=GR, tickangle=-45, tickfont=dict(size=9)),
                        yaxis=dict(title="Total Sales ($)", gridcolor=GR))
                    st.plotly_chart(fig_store, use_container_width=True)
                
                with col2:
                    # Store performance distribution
                    fig_store_dist = go.Figure()
                    fig_store_dist.add_trace(go.Histogram(
                        x=store_data["Weekly_Sales"],
                        nbinsx=15,
                        marker_color=PURPLE,
                        opacity=0.75,
                        name="Store Distribution"
                    ))
                    fig_store_dist.update_layout(**PLOT, height=300,
                        title=dict(text="Store Sales Distribution", font=dict(color=TEXT3, size=12)),
                        xaxis=dict(title="Total Sales ($)", gridcolor=GR),
                        yaxis=dict(title="Number of Stores", gridcolor=GR))
                    st.plotly_chart(fig_store_dist, use_container_width=True)
            
            # Summary insights
            st.markdown('<div class="section-label">Key Insights</div>', unsafe_allow_html=True)
            
            col1, col2, col3 = st.columns(3)
            
            with col1:
                if metrics["demand_growth_rate"] > 5:
                    st.markdown(f'<div class="alert alert-g">📈 <strong>Strong Growth:</strong> Demand increased by {metrics["demand_growth_rate"]:.1f}% month-over-month</div>', unsafe_allow_html=True)
                elif metrics["demand_growth_rate"] < -5:
                    st.markdown(f'<div class="alert alert-r">📉 <strong>Declining Demand:</strong> Sales dropped by {abs(metrics["demand_growth_rate"]):.1f}% month-over-month</div>', unsafe_allow_html=True)
                else:
                    st.markdown(f'<div class="alert alert-b">📊 <strong>Stable Demand:</strong> Growth rate of {metrics["demand_growth_rate"]:.1f}% indicates steady performance</div>', unsafe_allow_html=True)
            
            with col2:
                total_weeks = len(analyzer.df)
                avg_weekly = metrics["avg_weekly_demand"]
                st.markdown(f'<div class="alert alert-b">📅 <strong>Dataset Coverage:</strong> {total_weeks} weeks with average weekly sales of ${format_number(avg_weekly)}</div>', unsafe_allow_html=True)
            
            with col3:
                if not store_data.empty:
                    top_store = store_data.iloc[0]
                    st.markdown(f'<div class="alert alert-g">🏪 <strong>Top Performer:</strong> {top_store["Store"]} with ${format_number(top_store["Weekly_Sales"])} total sales</div>', unsafe_allow_html=True)
                else:
                    st.markdown(f'<div class="alert alert-b">📊 <strong>Single Store:</strong> Analysis based on individual store performance</div>', unsafe_allow_html=True)
            
            # Export functionality
            st.markdown('<div class="section-label">Export Demand Data</div>', unsafe_allow_html=True)
            
            export_data = {
                "Metric": ["Average Weekly Demand", "Total Demand", "Peak Month", "Lowest Month", "Growth Rate"],
                "Value": [
                    f"${metrics['avg_weekly_demand']:,.2f}",
                    f"${metrics['total_demand']:,.2f}",
                    metrics["peak_demand_month"],
                    metrics["lowest_demand_month"],
                    f"{metrics['demand_growth_rate']:.2f}%"
                ]
            }
            export_df = pd.DataFrame(export_data)
            
            col1, col2 = st.columns(2)
            with col1:
                st.dataframe(export_df, use_container_width=True, hide_index=True)
            with col2:
                from datetime import datetime
                st.download_button(
                    "Download Demand Metrics CSV",
                    export_df.to_csv(index=False),
                    f"demand_metrics_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                    "text/csv"
                )
                
                # Also export raw trend data
                trend_export = analyzer.get_demand_trend_data()
                st.download_button(
                    "Download Trend Data CSV",
                    trend_export.to_csv(index=False),
                    f"demand_trend_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                    "text/csv"
                )
                
        except Exception as e:
            st.markdown(f'<div class="alert alert-r">❌ <strong>Error analyzing demand data:</strong> {str(e)}</div>', unsafe_allow_html=True)
            st.markdown(f'<div class="alert alert-b">Please ensure your dataset contains the required columns: Date, Weekly_Sales, Store</div>', unsafe_allow_html=True)
    split_info = load_json("data_split.json") or {}
    insp       = load_json("data_inspection.json") or {}
    dr         = insp.get("date_range", ["2010-02-05", "2012-10-26"])
    train_rows = split_info.get("train_rows", 2385)
    test_rows  = split_info.get("test_rows",  4050)
    cutoff_dt  = split_info.get("cutoff_date", "2011-02-05")

    st.markdown('<div class="section-label">Reference Dataset (Training)</div>', unsafe_allow_html=True)
    st.markdown(f"""<div class="card">
    <div style="display:flex;justify-content:space-between;align-items:flex-start">
      <div>
        <div style="font-size:14px;font-weight:600;color:{TEXT};margin-bottom:10px">Walmart Weekly Sales — Training Split</div>
        <div style="display:flex;gap:32px;flex-wrap:wrap">
          <div><div style="font-size:10px;color:{TEXT3};text-transform:uppercase;letter-spacing:1px;margin-bottom:3px">Records</div>
               <div style="font-size:16px;font-weight:700;color:{TEXT};font-family:'JetBrains Mono',monospace">{train_rows:,}</div></div>
          <div><div style="font-size:10px;color:{TEXT3};text-transform:uppercase;letter-spacing:1px;margin-bottom:3px">Date Range</div>
               <div style="font-size:16px;font-weight:700;color:{TEXT};font-family:'JetBrains Mono',monospace">{dr[0][:10]}</div></div>
          <div><div style="font-size:10px;color:{TEXT3};text-transform:uppercase;letter-spacing:1px;margin-bottom:3px">Cutoff</div>
               <div style="font-size:16px;font-weight:700;color:{TEXT};font-family:'JetBrains Mono',monospace">{cutoff_dt}</div></div>
          <div><div style="font-size:10px;color:{TEXT3};text-transform:uppercase;letter-spacing:1px;margin-bottom:3px">Stores</div>
               <div style="font-size:16px;font-weight:700;color:{TEXT};font-family:'JetBrains Mono',monospace">45</div></div>
          <div><div style="font-size:10px;color:{TEXT3};text-transform:uppercase;letter-spacing:1px;margin-bottom:3px">Features</div>
               <div style="font-size:16px;font-weight:700;color:{TEXT};font-family:'JetBrains Mono',monospace">{len(feat_names)}</div></div>
        </div>
      </div>
      <span class="badge b-green">Reference</span>
    </div>
    </div>""", unsafe_allow_html=True)

    st.markdown('<div class="section-label">Monitored Batches</div>', unsafe_allow_html=True)
    if drift_data and batches:
        drift_by_month = {d["month"]: d for d in drift_data}
        batch_by_month = {b["month"]: b for b in batches}
        all_months = sorted(set(list(drift_by_month.keys()) + list(batch_by_month.keys())))
        rows = []
        for m in all_months:
            d = drift_by_month.get(m, {})
            b = batch_by_month.get(m, {})
            sev = d.get("severity", "N/A").upper()
            rows.append({
                "Month":    m,
                "Records":  b.get("count", "—"),
                "Mean Actual ($)":    f"{b['mean_actual']:,.0f}" if "mean_actual" in b else "—",
                "Mean Predicted ($)": f"{b['mean_pred']:,.0f}"   if "mean_pred"   in b else "—",
                "MAE ($)":  f"{abs(b.get('mean_actual',0)-b.get('mean_pred',0)):,.0f}" if "mean_actual" in b else "—",
                "Error Ratio": f"{d['error_trend']['error_increase']:.2f}x" if "error_trend" in d else "—",
                "Drift":    sev,
            })
        df_ds = pd.DataFrame(rows)
        def _sc(v):
            if v == "SEVERE": return f"color:{RED};font-weight:600"
            if v == "MILD":   return f"color:{ORANGE}"
            if v == "NONE":   return f"color:{GREEN}"
            return ""
        st.dataframe(df_ds.style.applymap(_sc, subset=["Drift"]),
                     width='stretch', hide_index=True)
        st.download_button("Export Batches CSV", df_ds.to_csv(index=False),
                           "batches_summary.csv", "text/csv")
    else:
        st.info("No batch data. Run `python main.py` first.")

    st.markdown('<div class="section-label">Upload New Dataset</div>', unsafe_allow_html=True)
    st.markdown(f"""<div class="alert alert-b">
      To upload and run predictions on new data, go to the <strong>Upload & Monitor</strong> page.
    </div>""", unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════════════════════
# PAGE: Drift Analysis (Reports)
# ══════════════════════════════════════════════════════════════════════════════
elif page == "Reports":
    from datetime import datetime as _dt

    # ── Filter bar ────────────────────────────────────────────────────────────
    fb1, fb2, fb3 = st.columns([3, 2, 1])
    with fb1:
        search = st.text_input("Search reports", placeholder="Filter by month or type...", label_visibility="collapsed")
    with fb2:
        rtype_filter = st.selectbox("Type", ["All", "Drift", "Model", "Feature"], label_visibility="collapsed")
    with fb3:
        gen_clicked = st.button("Generate Report", type="primary", width='stretch')

    if gen_clicked:
        st.session_state["gen_report"] = _dt.now().strftime("%Y-%m-%d %H:%M:%S")

    # ── Build report list from real drift + batch data ────────────────────────
    reports = []
    if drift_data:
        for i, d in enumerate(reversed(drift_data)):
            m   = d["month"]
            sev = d.get("severity", "none")
            reports.append({"id": f"RPT-{len(drift_data)-i:03d}", "month": m,
                            "type": "Drift", "severity": sev.upper(),
                            "features": d["severe_features"],
                            "mae": d["error_trend"]["current_error"],
                            "ratio": d["error_trend"]["error_increase"],
                            "status": "Ready"})
    if batches:
        for i, b in enumerate(reversed(batches)):
            reports.append({"id": f"RPT-M{len(batches)-i:03d}", "month": b["month"],
                            "type": "Model",
                            "severity": "N/A",
                            "features": 0,
                            "mae": abs(b.get("mean_actual",0) - b.get("mean_pred",0)),
                            "ratio": 0,
                            "status": "Ready"})
    if feat_names:
        reports.append({"id": "RPT-FI001", "month": "All", "type": "Feature",
                        "severity": "N/A", "features": len(feat_names),
                        "mae": 0, "ratio": 0, "status": "Ready"})
    if "gen_report" in st.session_state:
        reports.insert(0, {"id": f"RPT-GEN{len(reports)+1:03d}",
                           "month": _dt.now().strftime("%Y-%m"),
                           "type": "Drift", "severity": SEV.upper(),
                           "features": 0, "mae": 0, "ratio": 0,
                           "status": "Processing"})

    # Apply filters
    if search:
        reports = [r for r in reports if search.lower() in r["month"].lower() or search.lower() in r["type"].lower()]
    if rtype_filter != "All":
        reports = [r for r in reports if r["type"] == rtype_filter]

    st.markdown(f'<div class="section-label">{len(reports)} Reports</div>', unsafe_allow_html=True)

    if not reports:
        st.info("No reports match the current filter.")
    else:
        df_rpt = pd.DataFrame([{
            "Report ID":  r["id"],
            "Month":      r["month"],
            "Type":       r["type"],
            "Severity":   r["severity"],
            "Drifted Features": r["features"] if r["features"] else "—",
            "MAE ($)":    f"{r['mae']:,.0f}" if r["mae"] else "—",
            "Error Ratio": f"{r['ratio']:.2f}x" if r["ratio"] else "—",
            "Status":     r["status"],
        } for r in reports])

        def _rc(v):
            if v == "SEVERE":     return f"color:{RED};font-weight:600"
            if v == "MILD":       return f"color:{ORANGE}"
            if v == "NONE":       return f"color:{GREEN}"
            if v == "Ready":      return f"color:{GREEN}"
            if v == "Processing": return f"color:{ORANGE}"
            return ""

        st.dataframe(
            df_rpt.style.applymap(_rc, subset=["Severity", "Status"]),
            width='stretch', hide_index=True)
        st.download_button("Export Reports CSV", df_rpt.to_csv(index=False),
                           "reports.csv", "text/csv")

    # ── Drift detail section (same as before) ─────────────────────────────────
    if not drift_data:
        st.warning("No drift data. Run `python main.py` first.")
    else:
        ml  = [d["month"] for d in drift_data]
        ce  = [d["error_trend"]["current_error"]  for d in drift_data]
        be  = [d["error_trend"]["baseline_error"] for d in drift_data]
        ei  = [d["error_trend"]["error_increase"] for d in drift_data]
        sf  = [d["severe_features"] for d in drift_data]
        mf  = [d["mild_features"]   for d in drift_data]
        lat = drift_data[-1]
        total_f = lat.get("total_features", 49)

        st.markdown(f'<div class="section-label">Drift Gauges — Latest Month ({lat["month"]})</div>', unsafe_allow_html=True)
        g1, g2, g3 = st.columns(3)
        GX = dict(paper_bgcolor="rgba(0,0,0,0)", height=210,
                  margin=dict(t=40,b=10,l=20,r=20), font=dict(color=TEXT2))
        GSTEPS = [{"range":[0,30],"color":"rgba(16,185,129,0.12)"},
                  {"range":[30,60],"color":"rgba(245,158,11,0.12)"},
                  {"range":[60,100],"color":"rgba(239,68,68,0.12)"}]
        for col, val, lbl, color in [
            (g1, min(lat["error_trend"]["error_increase"]/10.0,1.0),
                 f"Error Ratio ({lat['error_trend']['error_increase']:.2f}x)", RED),
            (g2, lat["severe_features"]/max(total_f,1),
                 f"Severe Features ({lat['severe_features']}/{total_f})", PURPLE),
            (g3, lat["mild_features"]/max(total_f,1),
                 f"Mild Features ({lat['mild_features']}/{total_f})", ORANGE),
        ]:
            fg = go.Figure(go.Indicator(
                mode="gauge+number", value=round(val*100,1),
                number={"suffix":"%","font":{"color":color,"family":"JetBrains Mono","size":24}},
                gauge={"axis":{"range":[0,100],"tickcolor":TEXT3,"tickfont":{"color":TEXT3}},
                       "bar":{"color":color,"thickness":0.25},
                       "bgcolor":"rgba(0,0,0,0)","bordercolor":BORDER,
                       "steps":GSTEPS,
                       "threshold":{"line":{"color":color,"width":2},"thickness":0.75,"value":60}},
                title={"text":lbl,"font":{"color":TEXT3,"size":10}}))
            fg.update_layout(**GX)
            col.plotly_chart(fg, width='stretch')

        st.markdown(f'<div class="section-label">Error Trend — All {len(ml)} Months</div>', unsafe_allow_html=True)
        fig2 = go.Figure()
        fig2.add_trace(go.Scatter(x=ml, y=be, name="Baseline MAE",
            line=dict(color=GREEN, width=2, dash="dot"), marker=dict(size=5)))
        fig2.add_trace(go.Scatter(x=ml, y=ce, name="Current MAE",
            line=dict(color=RED, width=2.5), fill="tonexty",
            fillcolor="rgba(239,68,68,0.05)", marker=dict(size=5)))
        fig2.add_trace(go.Scatter(x=ml, y=ei, name="Error Ratio (x)",
            line=dict(color=ORANGE, width=2), yaxis="y2", marker=dict(size=5)))
        fig2.update_layout(**PLOT, height=300, hovermode="x unified",
            xaxis=dict(gridcolor=GR, tickangle=-45, tickfont=dict(size=9)),
            yaxis=dict(title="MAE ($)", gridcolor=GR),
            yaxis2=dict(title="Error Ratio x", overlaying="y", side="right",
                tickfont=dict(color=ORANGE, size=10), gridcolor="rgba(0,0,0,0)"))
        st.plotly_chart(fig2, width='stretch')

        st.markdown('<div class="section-label">Feature Drift Table — KS Statistics</div>', unsafe_allow_html=True)
        with st.spinner("Computing KS statistics..."):
            train_proc, test_proc, ks_results = load_real_feature_data()

        if ks_results and feat_names:
            st.markdown(f"""<div class="alert alert-b" style="margin-bottom:8px">
              Active thresholds — KS: mild &ge; {ks_mild} · severe &ge; {ks_severe}
              &nbsp;|&nbsp; PSI: mild &ge; {psi_mild} · severe &ge; {psi_severe}
            </div>""", unsafe_allow_html=True)
            rows = []
            for feat in feat_names:
                ks_val = ks_results.get(feat, {}).get("ks", 0.0)
                pval   = ks_results.get(feat, {}).get("pval", 1.0)
                idx    = feat_names.index(feat) if feat in feat_names else -1
                imp    = feat_imp[idx] if 0 <= idx < len(feat_imp) else 0.0
                sev    = "SEVERE" if ks_val >= ks_severe else ("MILD" if ks_val >= ks_mild else "NONE")
                rows.append({"Feature":feat,"KS Stat":ks_val,"P-Value":pval,
                             "Severity":sev,"Importance":round(imp,4)})
            df_drift = pd.DataFrame(rows).sort_values("KS Stat", ascending=False)
            counts   = df_drift["Severity"].value_counts()
            dc1, dc2, dc3 = st.columns(3)
            dc1.metric(f"Severe (KS >= {ks_severe})", counts.get("SEVERE", 0))
            dc2.metric(f"Mild (KS >= {ks_mild})",     counts.get("MILD",   0))
            dc3.metric("No Drift",                    counts.get("NONE",   0))
            def _sc(v):
                if v == "SEVERE": return f"color:{RED};font-weight:600"
                if v == "MILD":   return f"color:{ORANGE}"
                return f"color:{GREEN}"
            st.dataframe(
                df_drift.style
                    .applymap(_sc, subset=["Severity"])
                    .format({"KS Stat":"{:.4f}","P-Value":"{:.4f}","Importance":"{:.4f}"})
                    .background_gradient(subset=["KS Stat"], cmap="RdYlGn_r", vmin=0, vmax=0.5),
                width='stretch', hide_index=True)
            st.download_button("Export CSV", df_drift.to_csv(index=False), "drift_ks.csv", "text/csv")
        else:
            st.info("Run `python main.py` to generate data for KS computation.")
            df_fb = pd.DataFrame([{
                "Month": d["month"], "Severe Features": d["severe_features"],
                "Mild Features": d["mild_features"],
                "Error Ratio": f"{d['error_trend']['error_increase']:.2f}x",
                "Current MAE": f"${d['error_trend']['current_error']:,.0f}",
            } for d in drift_data])
            st.dataframe(df_fb, width='stretch', hide_index=True)

        # ── Feature distribution comparison ──────────────────────────────────
        st.markdown('<div class="section-label">Feature Distribution — Train vs Test</div>', unsafe_allow_html=True)
        if train_proc is not None and feat_names:
            sel_feat = st.selectbox("Select Feature", feat_names, key="drift_feat")
            if sel_feat in train_proc.columns and sel_feat in test_proc.columns:
                tr_v = train_proc[sel_feat].dropna().values
                te_v = test_proc[sel_feat].dropna().values
                ks_v = ks_results.get(sel_feat, {}).get("ks", 0.0) if ks_results else 0.0
                pv   = ks_results.get(sel_feat, {}).get("pval", 1.0) if ks_results else 1.0
                sl   = "SEVERE" if ks_v >= ks_severe else ("MILD" if ks_v >= ks_mild else "NONE")
                sc   = RED if sl == "SEVERE" else (ORANGE if sl == "MILD" else GREEN)
                dc1, dc2 = st.columns(2)
                with dc1:
                    fig3 = go.Figure()
                    fig3.add_trace(go.Histogram(x=tr_v, name=f"Train (n={len(tr_v):,})",
                        nbinsx=40, marker_color=GREEN, opacity=0.65))
                    fig3.add_trace(go.Histogram(x=te_v, name=f"Test (n={len(te_v):,})",
                        nbinsx=40, marker_color=PURPLE, opacity=0.65))
                    fig3.update_layout(**PLOT, height=280, barmode="overlay",
                        title=dict(text=f"KS={ks_v:.4f}  p={pv:.4f}  — {sl}", font=dict(color=sc, size=12)),
                        xaxis=dict(title=sel_feat, gridcolor=GR),
                        yaxis=dict(title="Count", gridcolor=GR))
                    st.plotly_chart(fig3, width='stretch')
                with dc2:
                    # Box plot comparison
                    fig_box = go.Figure()
                    fig_box.add_trace(go.Box(y=tr_v, name="Train", marker_color=GREEN,
                        boxmean=True, line=dict(color=GREEN)))
                    fig_box.add_trace(go.Box(y=te_v, name="Test", marker_color=PURPLE,
                        boxmean=True, line=dict(color=PURPLE)))
                    fig_box.update_layout(**PLOT, height=280,
                        title=dict(text=f"{sel_feat} — Distribution Spread", font=dict(color=TEXT3, size=12)),
                        yaxis=dict(title=sel_feat, gridcolor=GR))
                    st.plotly_chart(fig_box, width='stretch')
        else:
            st.info("Data not available. Run `python main.py` first.")

        # ── KS score bar chart for top drifted features ───────────────────────
        if ks_results and feat_names:
            st.markdown('<div class="section-label">Top 20 Features by KS Score</div>', unsafe_allow_html=True)
            top_ks = sorted(ks_results.items(), key=lambda x: x[1]["ks"], reverse=True)[:20]
            fnames_ks = [x[0] for x in top_ks]
            fvals_ks  = [x[1]["ks"] for x in top_ks]
            fcolors   = [RED if v >= ks_severe else ORANGE if v >= ks_mild else GREEN for v in fvals_ks]
            fig_ks = go.Figure(go.Bar(
                x=fvals_ks, y=fnames_ks, orientation="h",
                marker_color=fcolors, opacity=0.85,
                text=[f"{v:.4f}" for v in fvals_ks], textposition="outside",
                textfont=dict(color=TEXT3, size=10),
                hovertemplate="%{y}: KS=%{x:.4f}<extra></extra>"))
            fig_ks.add_vline(x=ks_severe, line=dict(color=RED, width=1.5, dash="dash"),
                annotation_text=f"Severe ({ks_severe})", annotation_font=dict(color=RED, size=10))
            fig_ks.add_vline(x=ks_mild, line=dict(color=ORANGE, width=1.5, dash="dot"),
                annotation_text=f"Mild ({ks_mild})", annotation_font=dict(color=ORANGE, size=10))
            fig_ks.update_layout(**PLOT, height=max(300, len(fnames_ks)*22),
                xaxis=dict(range=[0, max(fvals_ks)*1.25], gridcolor=GR),
                yaxis=dict(autorange="reversed", gridcolor=GR))
            st.plotly_chart(fig_ks, width='stretch')

        # ── Severe vs Mild feature count over time ────────────────────────────
        st.markdown('<div class="section-label">Drift Feature Count Over Time</div>', unsafe_allow_html=True)
        fig_fc = go.Figure()
        fig_fc.add_trace(go.Scatter(x=ml, y=sf, name="Severe Features",
            mode="lines+markers", line=dict(color=RED, width=2),
            fill="tozeroy", fillcolor="rgba(239,68,68,0.06)", marker=dict(size=5)))
        fig_fc.add_trace(go.Scatter(x=ml, y=mf, name="Mild Features",
            mode="lines+markers", line=dict(color=ORANGE, width=2),
            fill="tozeroy", fillcolor="rgba(245,158,11,0.05)", marker=dict(size=5)))
        tf_list = [d.get("total_features", 49) for d in drift_data]
        fig_fc.add_trace(go.Scatter(x=ml, y=tf_list, name="Total Features",
            mode="lines", line=dict(color=TEXT3, width=1, dash="dot")))
        fig_fc.update_layout(**PLOT, height=260, hovermode="x unified",
            xaxis=dict(gridcolor=GR, tickangle=-45, tickfont=dict(size=9)),
            yaxis=dict(title="Feature Count", gridcolor=GR))
        st.plotly_chart(fig_fc, width='stretch')

        # ── PSI-style drift severity heatmap ──────────────────────────────────
        st.markdown('<div class="section-label">Drift Severity Heatmap — Months vs Metrics</div>', unsafe_allow_html=True)
        hm_metrics = ["Error Ratio", "Severe %", "Mild %"]
        hm_z = [
            [min(d["error_trend"]["error_increase"]/10.0, 1.0)*100 for d in drift_data],
            [d["severe_features"]/max(d.get("total_features",49),1)*100 for d in drift_data],
            [d["mild_features"]/max(d.get("total_features",49),1)*100 for d in drift_data],
        ]
        fig_hm = go.Figure(go.Heatmap(
            z=hm_z, x=ml, y=hm_metrics,
            colorscale=[[0,"rgba(16,185,129,0.7)"],[0.4,"rgba(245,158,11,0.8)"],[1,"rgba(239,68,68,0.95)"]],
            showscale=True, colorbar=dict(thickness=10, tickfont=dict(color=TEXT3, size=10), title="%"),
            text=[[f"{v:.1f}%" for v in row] for row in hm_z],
            texttemplate="%{text}", textfont=dict(size=9, color="white"),
            hovertemplate="Month: %{x}<br>Metric: %{y}<br>Value: %{z:.1f}%<extra></extra>"))
        fig_hm.update_layout(**{**PLOT, "height":180, "margin":dict(t=10,b=30,l=80,r=60)})
        st.plotly_chart(fig_hm, width='stretch')

        # ── Rich Chart Gallery — Trained Data ────────────────────────────────
        st.markdown('<div class="section-label">Trained Data — Chart Gallery</div>', unsafe_allow_html=True)

        # Row 1: Pie + Radar
        rg1, rg2 = st.columns(2)
        with rg1:
            sev_counts = {"Severe": sum(1 for d in drift_data if d.get("severity")=="severe"),
                          "Mild":   sum(1 for d in drift_data if d.get("severity")=="mild"),
                          "None":   sum(1 for d in drift_data if d.get("severity")=="none")}
            fig_pie = go.Figure(go.Pie(
                labels=list(sev_counts.keys()), values=list(sev_counts.values()),
                marker=dict(colors=[RED, ORANGE, GREEN]),
                hole=0.4, textfont=dict(color="white", size=12),
                hovertemplate="%{label}: %{value} months (%{percent})<extra></extra>"))
            fig_pie.update_layout(**PLOT, height=260,
                title=dict(text="Drift Severity Distribution", font=dict(color=TEXT3, size=11)))
            st.plotly_chart(fig_pie, width='stretch')
        with rg2:
            lat_d = drift_data[-1]
            radar_cats = ["Error Ratio","Severe Feat%","Mild Feat%","MAE Ratio","Months Severe"]
            tf_ = lat_d.get("total_features",49)
            sc_ = {"severe":0,"mild":0,"none":0}
            for d in drift_data: sc_[d.get("severity","none")] = sc_.get(d.get("severity","none"),0)+1
            radar_vals = [
                min(lat_d["error_trend"]["error_increase"]/10.0,1.0)*100,
                lat_d["severe_features"]/max(tf_,1)*100,
                lat_d["mild_features"]/max(tf_,1)*100,
                min(lat_d["error_trend"]["current_error"]/max(lat_d["error_trend"]["baseline_error"],1)/5.0,1.0)*100,
                sc_["severe"]/max(len(drift_data),1)*100,
            ]
            fig_rad = go.Figure(go.Scatterpolar(
                r=radar_vals+[radar_vals[0]], theta=radar_cats+[radar_cats[0]],
                fill="toself", fillcolor=f"rgba(239,68,68,0.15)",
                line=dict(color=RED, width=2), name="Latest Month"))
            fig_rad.update_layout(**PLOT, height=260,
                polar=dict(bgcolor=CARD,
                    radialaxis=dict(visible=True, range=[0,100], gridcolor=BORDER, tickfont=dict(color=TEXT3,size=9)),
                    angularaxis=dict(gridcolor=BORDER, tickfont=dict(color=TEXT3,size=10))),
                title=dict(text="Drift Radar — Latest Month", font=dict(color=TEXT3, size=11)))
            st.plotly_chart(fig_rad, width='stretch')

        # Row 2: Waterfall + Column (grouped bar)
        rg3, rg4 = st.columns(2)
        with rg3:
            wf_x = ["Baseline MAE"] + ml[-6:] + ["Net Change"]
            wf_y = [be[0]] + [c-b for c,b in zip(ce[-6:],be[-6:])] + [ce[-1]-be[0]]
            wf_measure = ["absolute"] + ["relative"]*len(ml[-6:]) + ["total"]
            wf_colors = [BLUE] + [RED if v>0 else GREEN for v in wf_y[1:-1]] + [ORANGE]
            fig_wf = go.Figure(go.Waterfall(
                x=wf_x, y=wf_y, measure=wf_measure,
                increasing=dict(marker=dict(color=RED)),
                decreasing=dict(marker=dict(color=GREEN)),
                totals=dict(marker=dict(color=ORANGE)),
                connector=dict(line=dict(color=BORDER, width=1)),
                texttemplate="$%{y:,.0f}", textposition="outside",
                textfont=dict(color=TEXT3, size=9),
                hovertemplate="%{x}<br>$%{y:,.0f}<extra></extra>"))
            fig_wf.update_layout(**PLOT, height=280,
                title=dict(text="MAE Waterfall — Last 6 Months", font=dict(color=TEXT3, size=11)),
                xaxis=dict(gridcolor=GR, tickangle=-30, tickfont=dict(size=9)),
                yaxis=dict(gridcolor=GR))
            st.plotly_chart(fig_wf, width='stretch')
        with rg4:
            fig_grp = go.Figure()
            fig_grp.add_trace(go.Bar(x=ml, y=sf, name="Severe", marker_color=RED, opacity=0.85))
            fig_grp.add_trace(go.Bar(x=ml, y=mf, name="Mild",   marker_color=ORANGE, opacity=0.85))
            fig_grp.add_trace(go.Bar(x=ml, y=[max(0,d.get("total_features",49)-d["severe_features"]-d["mild_features"]) for d in drift_data],
                name="No Drift", marker_color=GREEN, opacity=0.85))
            fig_grp.update_layout(**PLOT, height=280, barmode="group",
                title=dict(text="Feature Drift Count — Grouped Column", font=dict(color=TEXT3, size=11)),
                xaxis=dict(gridcolor=GR, tickangle=-45, tickfont=dict(size=9)),
                yaxis=dict(title="Features", gridcolor=GR))
            st.plotly_chart(fig_grp, width='stretch')

        # Row 3: Box plots + Histogram of errors
        if batches:
            rg5, rg6 = st.columns(2)
            mae_vals = [abs(b.get("mean_actual",0)-b.get("mean_pred",0)) for b in batches]
            with rg5:
                fig_bx = go.Figure()
                fig_bx.add_trace(go.Box(y=ce, name="Current MAE", marker_color=RED, boxmean=True))
                fig_bx.add_trace(go.Box(y=be, name="Baseline MAE", marker_color=GREEN, boxmean=True))
                fig_bx.add_trace(go.Box(y=mae_vals, name="Batch MAE", marker_color=BLUE, boxmean=True))
                fig_bx.update_layout(**PLOT, height=280,
                    title=dict(text="MAE Distribution — Box Plot", font=dict(color=TEXT3, size=11)),
                    yaxis=dict(title="MAE ($)", gridcolor=GR))
                st.plotly_chart(fig_bx, width='stretch')
            with rg6:
                fig_hist = go.Figure()
                fig_hist.add_trace(go.Histogram(x=ei, nbinsx=10, name="Error Ratio",
                    marker_color=ORANGE, opacity=0.8))
                fig_hist.update_layout(**PLOT, height=280,
                    title=dict(text="Error Ratio Histogram", font=dict(color=TEXT3, size=11)),
                    xaxis=dict(title="Error Ratio (x)", gridcolor=GR),
                    yaxis=dict(title="Count", gridcolor=GR))
                st.plotly_chart(fig_hist, width='stretch')

        # Row 4: Pyramid (horizontal bar mirrored) + Line area
        rg7, rg8 = st.columns(2)
        with rg7:
            top5_sev = sorted(drift_data, key=lambda d: d["severe_features"], reverse=True)[:5]
            top5_mil = sorted(drift_data, key=lambda d: d["mild_features"], reverse=True)[:5]
            pyr_months = [d["month"] for d in top5_sev]
            fig_pyr = go.Figure()
            fig_pyr.add_trace(go.Bar(y=pyr_months, x=[-d["severe_features"] for d in top5_sev],
                orientation="h", name="Severe", marker_color=RED, opacity=0.85))
            fig_pyr.add_trace(go.Bar(y=[d["month"] for d in top5_mil],
                x=[d["mild_features"] for d in top5_mil],
                orientation="h", name="Mild", marker_color=ORANGE, opacity=0.85))
            fig_pyr.update_layout(**PLOT, height=280, barmode="overlay",
                title=dict(text="Feature Drift Pyramid — Top 5 Months", font=dict(color=TEXT3, size=11)),
                xaxis=dict(gridcolor=GR, tickvals=[-40,-20,0,20,40],
                    ticktext=["40","20","0","20","40"]),
                yaxis=dict(gridcolor=GR))
            st.plotly_chart(fig_pyr, width='stretch')
        with rg8:
            fig_area = go.Figure()
            fig_area.add_trace(go.Scatter(x=ml, y=ce, name="Current MAE",
                fill="tozeroy", fillcolor="rgba(239,68,68,0.12)",
                line=dict(color=RED, width=2)))
            fig_area.add_trace(go.Scatter(x=ml, y=be, name="Baseline MAE",
                fill="tozeroy", fillcolor="rgba(16,185,129,0.08)",
                line=dict(color=GREEN, width=2, dash="dash")))
            fig_area.update_layout(**PLOT, height=280,
                title=dict(text="MAE Area Chart — All Months", font=dict(color=TEXT3, size=11)),
                xaxis=dict(gridcolor=GR, tickangle=-45, tickfont=dict(size=9)),
                yaxis=dict(title="MAE ($)", gridcolor=GR))
            st.plotly_chart(fig_area, width='stretch')

# ══════════════════════════════════════════════════════════════════════════════
# PAGE: Model Performance (Traces)
# ══════════════════════════════════════════════════════════════════════════════
elif page == "Model Performance":
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("R²",    f"{R2:.4f}")
    c2.metric("MAE",   f"${MAE:,.0f}")
    c3.metric("RMSE",  f"${RMSE:,.0f}")
    c4.metric("MAPE",  f"{MAPE:.2f}%")
    c5.metric("WMAPE", f"{WMAPE:.2f}%")

    if not batches:
        st.warning("No prediction data. Run `python main.py` first.")
    else:
        ml   = [b["month"]       for b in batches]
        ma   = [b["mean_actual"] for b in batches]
        mp_  = [b["mean_pred"]   for b in batches]
        cnt  = [b.get("count",0) for b in batches]
        mae_m = [abs(a-p) for a,p in zip(ma,mp_)]
        dbm  = {d["month"]:d for d in drift_data}
        ei   = [dbm[m]["error_trend"]["error_increase"] if m in dbm else 0.0 for m in ml]

        st.markdown(f'<div class="section-label">Actual vs Predicted — {len(ml)} Months</div>', unsafe_allow_html=True)
        fig1 = go.Figure()
        spread = [abs(a-p)*0.5 for a,p in zip(ma,mp_)]
        fig1.add_trace(go.Scatter(
            x=ml+ml[::-1],
            y=[a+s for a,s in zip(ma,spread)]+[max(0,a-s) for a,s in zip(ma,spread)][::-1],
            fill="toself", fillcolor="rgba(59,130,246,0.07)",
            line=dict(color="rgba(0,0,0,0)"), name="Error Band"))
        fig1.add_trace(go.Scatter(x=ml, y=ma, mode="lines+markers", name="Actual",
            line=dict(color=BLUE, width=2.5), marker=dict(size=6),
            hovertemplate="Month: %{x}<br>Actual: $%{y:,.0f}<extra></extra>"))
        fig1.add_trace(go.Scatter(x=ml, y=mp_, mode="lines+markers", name="Predicted",
            line=dict(color=ORANGE, width=2.5, dash="dot"), marker=dict(size=6, symbol="diamond"),
            hovertemplate="Month: %{x}<br>Predicted: $%{y:,.0f}<extra></extra>"))
        fig1.update_layout(**PLOT, height=320, hovermode="x unified",
            xaxis=dict(gridcolor=GR, tickangle=-45, tickfont=dict(size=9)),
            yaxis=dict(title="Total Monthly Sales ($)", gridcolor=GR))
        st.plotly_chart(fig1, width='stretch')

        col1, col2 = st.columns(2)
        with col1:
            st.markdown('<div class="section-label">Monthly MAE vs Baseline</div>', unsafe_allow_html=True)
            bc = [RED if e>0.5 else ORANGE if e>0.2 else GREEN for e in ei]
            fig2 = go.Figure()
            fig2.add_trace(go.Bar(x=ml, y=mae_m, marker_color=bc, opacity=0.85,
                text=[f"${v:,.0f}" for v in mae_m], textposition="outside",
                textfont=dict(color=TEXT3, size=9),
                hovertemplate="Month: %{x}<br>MAE: $%{y:,.0f}<extra></extra>"))
            fig2.add_hline(y=MAE, line=dict(color=GREEN, width=1.5, dash="dash"),
                annotation_text=f"Baseline ${MAE:,.0f}",
                annotation_font=dict(color=GREEN, size=11))
            fig2.update_layout(**PLOT, height=280,
                xaxis=dict(gridcolor=GR, tickangle=-45, tickfont=dict(size=9)),
                yaxis=dict(gridcolor=GR))
            st.plotly_chart(fig2, width='stretch')

        with col2:
            st.markdown('<div class="section-label">Actual vs Predicted Scatter</div>', unsafe_allow_html=True)
            errs = [a-p for a,p in zip(ma,mp_)]
            cs   = [RED if abs(e)>MAE*3 else ORANGE if abs(e)>MAE else GREEN for e in errs]
            fig3 = go.Figure()
            fig3.add_trace(go.Scatter(x=ma, y=mp_, mode="markers",
                marker=dict(color=cs, size=10, opacity=0.8, line=dict(color=BORDER, width=1)),
                text=ml, hovertemplate="Month: %{text}<br>Actual: $%{x:,.0f}<br>Predicted: $%{y:,.0f}<extra></extra>"))
            mn_v, mx_v = min(ma+mp_), max(ma+mp_)
            fig3.add_trace(go.Scatter(x=[mn_v,mx_v], y=[mn_v,mx_v],
                mode="lines", line=dict(color=GREEN, width=1.5, dash="dash"),
                name="Perfect"))
            fig3.update_layout(**PLOT, height=280,
                xaxis=dict(title="Actual ($)", gridcolor=GR),
                yaxis=dict(title="Predicted ($)", gridcolor=GR))
            st.plotly_chart(fig3, width='stretch')

        st.markdown('<div class="section-label">Monthly Summary Table</div>', unsafe_allow_html=True)
        df_p = pd.DataFrame({
            "Month":         ml,
            "Rows":          [f"{c:,}" for c in cnt],
            "Actual ($)":    [f"{v:,.0f}" for v in ma],
            "Predicted ($)": [f"{v:,.0f}" for v in mp_],
            "MAE ($)":       [f"{v:,.0f}" for v in mae_m],
            "Error Ratio":   [f"{v:.2f}x" for v in ei],
            "Severity":      [dbm[m]["severity"].upper() if m in dbm else "N/A" for m in ml],
        })
        def _sc2(v):
            if v == "SEVERE": return f"color:{RED};font-weight:600"
            if v == "MILD":   return f"color:{ORANGE}"
            return f"color:{GREEN}"
        st.dataframe(df_p.style.applymap(_sc2, subset=["Severity"]),
                     width='stretch', hide_index=True)
        st.download_button("Export CSV", df_p.to_csv(index=False),
                           "predictions_summary.csv", "text/csv")

# ══════════════════════════════════════════════════════════════════════════════
# PAGE: Feature Importance
# ══════════════════════════════════════════════════════════════════════════════
elif page == "Feature Importance":
    if not feat_names:
        st.warning("No feature data. Run `python main.py` first.")
    else:
        top_n      = st.selectbox("Show top N features", [10, 15, 20, len(feat_names)], index=1)
        names_show = feat_names[:top_n]
        imp_show   = feat_imp[:top_n]

        st.markdown('<div class="section-label">Feature Importance Ranking</div>', unsafe_allow_html=True)
        colors = []
        for n in names_show:
            if n.startswith("Lag"):       colors.append(BLUE)
            elif n.startswith("Rolling"): colors.append(PURPLE)
            elif n.startswith("Store"):   colors.append(GREEN)
            elif n in ("CPI","Unemployment","Fuel_Price","Temperature"): colors.append(ORANGE)
            else:                         colors.append(TEXT3)

        fig1 = go.Figure(go.Bar(
            x=imp_show, y=names_show, orientation="h",
            marker=dict(color=colors, opacity=0.85, line=dict(width=0)),
            text=[f"{v:.4f}" for v in imp_show],
            textposition="outside", textfont=dict(color=TEXT3, size=10),
            hovertemplate="%{y}: %{x:.4f}<extra></extra>"))
        fig1.update_layout(**PLOT, height=max(300, top_n*24),
            xaxis=dict(range=[0, max(imp_show)*1.3], gridcolor=GR),
            yaxis=dict(autorange="reversed", gridcolor=GR))
        st.plotly_chart(fig1, width='stretch')

        cumsum = np.cumsum(imp_show) / sum(feat_imp) * 100
        fig_c = go.Figure()
        fig_c.add_trace(go.Scatter(x=list(range(1, len(cumsum)+1)), y=cumsum,
            mode="lines+markers", line=dict(color=BLUE, width=2),
            marker=dict(size=5), fill="tozeroy", fillcolor="rgba(59,130,246,0.08)",
            hovertemplate="Top %{x} features: %{y:.1f}%<extra></extra>"))
        fig_c.add_hline(y=80, line=dict(color=ORANGE, width=1, dash="dash"),
            annotation_text="80% threshold", annotation_font=dict(color=ORANGE, size=11))
        fig_c.update_layout(**PLOT, height=200,
            xaxis=dict(title="Number of Features", gridcolor=GR),
            yaxis=dict(title="Cumulative Importance %", gridcolor=GR))
        st.plotly_chart(fig_c, width='stretch')

        st.markdown(f"""
        <div style="display:flex;gap:16px;flex-wrap:wrap;margin:4px 0 14px;font-size:11px;color:{TEXT3}">
          <span><span style="color:{BLUE}">&#9632;</span> Lag</span>
          <span><span style="color:{PURPLE}">&#9632;</span> Rolling</span>
          <span><span style="color:{GREEN}">&#9632;</span> Store</span>
          <span><span style="color:{ORANGE}">&#9632;</span> Economic</span>
        </div>""", unsafe_allow_html=True)

        col1, col2 = st.columns(2)
        with col1:
            st.markdown('<div class="section-label">Distribution — Train vs Test</div>', unsafe_allow_html=True)
            with st.spinner("Loading data..."):
                train_proc, test_proc, ks_results = load_real_feature_data()
            sel = st.selectbox("Feature", names_show, key="fi_feat")
            if train_proc is not None and sel in train_proc.columns and sel in test_proc.columns:
                tr_v = train_proc[sel].dropna().values
                te_v = test_proc[sel].dropna().values
                ks_v = ks_results.get(sel, {}).get("ks", 0.0) if ks_results else 0.0
                sl   = "SEVERE" if ks_v >= ks_severe else ("MILD" if ks_v >= ks_mild else "NONE")
                sc   = RED if sl == "SEVERE" else (ORANGE if sl == "MILD" else GREEN)
                fig2 = go.Figure()
                fig2.add_trace(go.Histogram(x=tr_v, name=f"Train (n={len(tr_v):,})",
                    nbinsx=35, marker_color=GREEN, opacity=0.65))
                fig2.add_trace(go.Histogram(x=te_v, name=f"Test (n={len(te_v):,})",
                    nbinsx=35, marker_color=PURPLE, opacity=0.65))
                fig2.update_layout(**PLOT, height=280, barmode="overlay",
                    title=dict(text=f"KS={ks_v:.4f} — {sl}", font=dict(color=sc, size=12)),
                    xaxis=dict(title=sel, gridcolor=GR),
                    yaxis=dict(title="Count", gridcolor=GR))
                st.plotly_chart(fig2, width='stretch')
            else:
                st.info("Run `python main.py` to enable real distributions.")

        with col2:
            st.markdown('<div class="section-label">Importance Table</div>', unsafe_allow_html=True)
            df_fi = pd.DataFrame({
                "Feature":    names_show,
                "Importance": [round(v,4) for v in imp_show],
                "Cumulative": [f"{c:.1f}%" for c in np.cumsum(imp_show)/sum(feat_imp)*100],
                "Category":   ["Lag" if n.startswith("Lag") else
                               "Rolling" if n.startswith("Rolling") else
                               "Store" if n.startswith("Store") else
                               "Economic" if n in ("CPI","Unemployment","Fuel_Price","Temperature")
                               else "Other" for n in names_show],
                "KS (real)":  [round(ks_results.get(n,{}).get("ks",0.0),4)
                               if ks_results else 0.0 for n in names_show],
            })
            st.dataframe(df_fi.style.background_gradient(subset=["Importance"], cmap="Blues"),
                         width='stretch', hide_index=True)
            st.download_button("Export CSV", df_fi.to_csv(index=False),
                               "feature_importance.csv", "text/csv")

# ══════════════════════════════════════════════════════════════════════════════
# PAGE: Alerts
# ══════════════════════════════════════════════════════════════════════════════
elif page == "Alerts":
    from datetime import datetime, timedelta

    # Build alerts from real drift data
    alerts = []
    if drift_data:
        # Compute a fake "hours ago" based on month index for display
        now = datetime.now()
        for i, d in enumerate(reversed(drift_data)):
            sev  = d.get("severity", "none")
            if sev not in ("severe", "mild"): continue
            et   = d["error_trend"]
            age  = timedelta(hours=2 + i * 18)
            ts   = (now - age)
            age_str = f"{int(age.total_seconds()//3600)}h ago" if age.days == 0 else f"{age.days}d ago"
            # Top drifted feature for this month (use feat_names[0] as proxy if no per-month data)
            top_feat = feat_names[0] if feat_names else "feature"
            alerts.append({
                "id":      f"ALT-{len(drift_data)-i:03d}",
                "sev":     sev,
                "month":   d["month"],
                "severe_f": d["severe_features"],
                "mild_f":   d["mild_features"],
                "mae":     et["current_error"],
                "ratio":   et["error_increase"],
                "age":     age_str,
                "ts":      ts.strftime("%Y-%m-%d %H:%M"),
            })
        alerts = alerts[:20]  # cap display

    # Summary metrics
    n_severe = sum(1 for a in alerts if a["sev"] == "severe")
    n_mild   = sum(1 for a in alerts if a["sev"] == "mild")
    a1, a2, a3, a4 = st.columns(4)
    a1.metric("Total Alerts",  len(alerts))
    a2.metric("Severe",        n_severe)
    a3.metric("Mild",          n_mild)
    a4.metric("Months Monitored", MONTHS_MON)

    # Acknowledge state
    if "acked" not in st.session_state:
        st.session_state.acked = set()

    # Filter
    st.markdown('<div class="section-label">Active Alerts</div>', unsafe_allow_html=True)
    filt = st.selectbox("Filter by severity", ["All", "Severe", "Mild"], key="alert_filt")
    filtered = [a for a in alerts if filt == "All" or a["sev"] == filt.lower()]

    if not filtered:
        st.markdown(f'<div class="alert alert-g">No alerts match the current filter.</div>', unsafe_allow_html=True)
    else:
        for a in filtered:
            is_acked = a["id"] in st.session_state.acked
            border_c = RED if a["sev"] == "severe" else ORANGE
            bg_c     = "rgba(239,68,68,0.04)" if a["sev"] == "severe" else "rgba(245,158,11,0.04)"
            badge_cls = "b-red" if a["sev"] == "severe" else "b-orange"
            acked_style = f"opacity:0.45;" if is_acked else ""

            st.markdown(f"""
            <div style="background:{CARD};border:1px solid {border_c}33;
              border-left:3px solid {border_c};border-radius:0 8px 8px 0;
              padding:14px 18px;margin-bottom:8px;{acked_style}">
              <div style="display:flex;justify-content:space-between;align-items:flex-start">
                <div style="flex:1">
                  <div style="display:flex;align-items:center;gap:10px;margin-bottom:6px">
                    <span class="badge {badge_cls}">{a['sev'].upper()}</span>
                    <span style="font-size:11px;color:{TEXT3};font-family:'JetBrains Mono',monospace">{a['id']}</span>
                    <span style="font-size:11px;color:{TEXT3}">{a['ts']} &nbsp;·&nbsp; {a['age']}</span>
                    {'<span style="font-size:10px;color:' + TEXT3 + ';border:1px solid ' + BORDER + ';border-radius:4px;padding:1px 7px">Acknowledged</span>' if is_acked else ''}
                  </div>
                  <div style="font-size:13px;font-weight:600;color:{TEXT};margin-bottom:4px">
                    Drift detected — Month {a['month']}
                  </div>
                  <div style="font-size:12px;color:{TEXT2};line-height:1.6">
                    {a['severe_f']} severe features &nbsp;·&nbsp; {a['mild_f']} mild features &nbsp;·&nbsp;
                    MAE <strong style="color:{border_c}">${a['mae']:,.0f}</strong> &nbsp;·&nbsp;
                    Error ratio <strong style="color:{border_c}">{a['ratio']:.2f}x</strong>
                  </div>
                </div>
              </div>
            </div>
            """, unsafe_allow_html=True)

            if not is_acked:
                if st.button(f"Acknowledge {a['id']}", key=f"ack_{a['id']}"):
                    st.session_state.acked.add(a["id"])
                    st.rerun()
            else:
                if st.button(f"Unacknowledge {a['id']}", key=f"unack_{a['id']}"):
                    st.session_state.acked.discard(a["id"])
                    st.rerun()

    # Alert history table
    st.markdown('<div class="section-label">Alert Log</div>', unsafe_allow_html=True)
    if alerts:
        df_al = pd.DataFrame([{
            "ID":      a["id"],
            "Month":   a["month"],
            "Severity": a["sev"].upper(),
            "Severe Features": a["severe_f"],
            "Mild Features":   a["mild_f"],
            "MAE ($)":  f"{a['mae']:,.0f}",
            "Error Ratio": f"{a['ratio']:.2f}x",
            "Timestamp": a["ts"],
            "Status":   "Acknowledged" if a["id"] in st.session_state.acked else "Active",
        } for a in alerts])
        def _ac(v):
            if v == "SEVERE":       return f"color:{RED};font-weight:600"
            if v == "MILD":         return f"color:{ORANGE}"
            if v == "Acknowledged": return f"color:{TEXT3}"
            if v == "Active":       return f"color:{BLUE};font-weight:600"
            return ""
        st.dataframe(
            df_al.style.applymap(_ac, subset=["Severity", "Status"]),
            width='stretch', hide_index=True)
        st.download_button("Export Alert Log CSV", df_al.to_csv(index=False),
                           "alert_log.csv", "text/csv")
    else:
        st.info("No alert data. Run `python main.py` first.")

# ══════════════════════════════════════════════════════════════════════════════
# PAGE: Upload & Monitor
# ══════════════════════════════════════════════════════════════════════════════
elif page == "Upload & Monitor":
    from feature_engineering import FeatureEngineer
    from drift_detector import DriftDetector
    from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
    from datetime import datetime

    _BASE     = os.path.dirname(os.path.abspath(__file__))
    _DATA     = os.path.join(_BASE, "data", "uploaded_data.csv")
    _PROC     = os.path.join(_BASE, "processed")
    _UPL      = os.path.join(_BASE, "uploads")
    _REQUIRED = {"Store","Date","Weekly_Sales","Holiday_Flag","Temperature","Fuel_Price","CPI","Unemployment"}

    @st.cache_resource(show_spinner=False)
    def _model():
        mp = os.path.join(_BASE, "models", "active_model.pkl")
        rp = os.path.join(_BASE, "models", "baseline_model_rf.pkl")
        if not os.path.exists(mp): return None, None
        return joblib.load(mp), joblib.load(rp) if os.path.exists(rp) else joblib.load(mp)

    @st.cache_resource(show_spinner=False)
    def _baseline():
        if not os.path.exists(_DATA): return None, None, None, None
        raw = pd.read_csv(_DATA)
        raw["Date"] = pd.to_datetime(raw["Date"], dayfirst=True)
        cut = raw["Date"].min() + pd.DateOffset(months=12)
        tr  = raw[raw["Date"] < cut].copy()
        eng = FeatureEngineer()
        proc, _ = eng.run_feature_pipeline(tr, fit=True)
        return proc, eng._store_stats, eng, tr.copy()

    _umodel, _urf = _model()
    _uproc, _uss, _ueng, _uhist = _baseline()
    _ufnames = (summary or {}).get("feature_names", [])
    _uok     = _umodel is not None and len(_ufnames) > 0
    _ubm     = (metrics or {}).get("train", {})

    def _predict(df):
        eng = FeatureEngineer()
        eng._store_stats = _uss if _uss is not None else \
            df.groupby("Store")["Weekly_Sales"].agg(
                Store_Mean="mean", Store_Median="median", Store_Std="std").reset_index()
        if _ueng: eng.encoders = _ueng.encoders
        if _uhist is not None:
            upload_dates = set(df["Date"].dt.normalize().unique())
            combined = pd.concat([_uhist, df], ignore_index=True).sort_values(["Store","Date"])
            proc, _ = eng.run_feature_pipeline(combined, fit=False)
            proc = proc[proc["Date"].dt.normalize().isin(upload_dates)].reset_index(drop=True)
        else:
            proc, _ = eng.run_feature_pipeline(df.copy(), fit=False)
        for f in _ufnames:
            if f not in proc.columns: proc[f] = 0
        X = proc[_ufnames]; y = proc["Weekly_Sales"].values
        return proc, X, y, _umodel.predict(X)

    def _calc_metrics(y, p):
        mask = y != 0
        return {"MAE":  float(mean_absolute_error(y, p)),
                "RMSE": float(np.sqrt(mean_squared_error(y, p))),
                "R2":   float(r2_score(y, p)),
                "MAPE": float(np.mean(np.abs((y[mask]-p[mask])/y[mask]))*100) if mask.any() else 0.0}

    def _run_drift(X, y, preds):
        det = DriftDetector()
        if _urf and hasattr(_urf, "feature_importances_"):
            det.set_feature_importance(_urf, _ufnames)
        if _uproc is not None:
            Xtr = _uproc[[f for f in _ufnames if f in _uproc.columns]]
            for f in _ufnames:
                if f not in Xtr.columns: Xtr[f] = 0
            Xtr = Xtr[_ufnames]
            det.set_baseline(Xtr, errors=_uproc["Weekly_Sales"].values - _umodel.predict(Xtr))
        else:
            det.set_baseline(X, errors=np.zeros(len(y)))
        return det.comprehensive_detection(X, y - preds)

    for k, v in [("up_result", None), ("up_udf", None), ("up_history", [])]:
        if k not in st.session_state: st.session_state[k] = v

    _tab_upload, _tab_results = st.tabs(["Upload & Run", "Prediction Results"])

    with _tab_upload:
        st.markdown('<div class="section-label">Upload New Monthly Data</div>', unsafe_allow_html=True)
        ul_col, run_col = st.columns([3, 2])
        with ul_col:
            _uploaded = st.file_uploader("CSV", type=["csv"], label_visibility="collapsed",
                help="Required columns: Store, Date, Weekly_Sales, Holiday_Flag, Temperature, Fuel_Price, CPI, Unemployment")
            if _uploaded:
                try:
                    _df = pd.read_csv(_uploaded)
                    _df["Date"] = pd.to_datetime(_df["Date"], dayfirst=True)
                    _miss = _REQUIRED - set(_df.columns)
                    if _miss:
                        st.markdown(f'<div class="alert alert-r">Missing columns: {", ".join(sorted(_miss))}</div>', unsafe_allow_html=True)
                    else:
                        st.session_state.up_udf = _df
                        st.markdown(f'<div class="alert alert-g">Validated — <strong>{len(_df):,} rows</strong> · <strong>{_df["Store"].nunique()} stores</strong> · {_df["Date"].min().date()} to {_df["Date"].max().date()}</div>', unsafe_allow_html=True)
                        with st.expander("Preview"):
                            st.dataframe(_df.head(6), width='stretch', hide_index=True)
                except Exception as e:
                    st.markdown(f'<div class="alert alert-r">Parse error: {e}</div>', unsafe_allow_html=True)
            with st.expander("Expected format"):
                st.dataframe(pd.DataFrame({
                    "Store":[1,1],"Date":["01-02-2012","08-02-2012"],
                    "Weekly_Sales":[124567.32,134567.89],"Holiday_Flag":[0,0],
                    "Temperature":[45.2,47.1],"Fuel_Price":[3.45,3.52],
                    "CPI":[228.5,229.1],"Unemployment":[8.2,8.1],
                }), width='stretch', hide_index=True)
        with run_col:
            if not _uok:
                st.markdown(f'<div class="alert alert-r">No model found. Run <code>python main.py</code> first.</div>', unsafe_allow_html=True)
            elif st.session_state.up_udf is None:
                st.markdown(f'<div style="text-align:center;padding:28px;color:{TEXT3};font-size:13px">Upload a CSV file to enable predictions.</div>', unsafe_allow_html=True)
            else:
                _dfi = st.session_state.up_udf
                st.markdown(f"""<div class="card">
                <div class="card-title">Ready to Process</div>
                <div class="kv"><span class="k">Rows</span><span class="v">{len(_dfi):,}</span></div>
                <div class="kv"><span class="k">Stores</span><span class="v">{_dfi['Store'].nunique()}</span></div>
                <div class="kv"><span class="k">Date Range</span><span class="v">{_dfi['Date'].min().date()} to {_dfi['Date'].max().date()}</span></div>
                </div>""", unsafe_allow_html=True)
                if st.button("Run Pipeline", type="primary", width='stretch', key="up_run"):
                    _sph = st.empty()
                    def _steps(done, active):
                        lbls = ["Feature Engineering","Prediction","Drift Detection","Saving"]
                        rows = ""
                        for i, l in enumerate(lbls):
                            if i < done:
                                rows += f'<div class="step-row"><span class="dot dot-done">&#10003;</span><span style="color:{TEXT2}">{l}</span></div>'
                            elif i == active:
                                rows += f'<div class="step-row"><span class="dot dot-active">{i+1}</span><span style="color:{TEXT2}">{l}...</span></div>'
                            else:
                                rows += f'<div class="step-row"><span class="dot dot-wait">{i+1}</span><span style="color:{TEXT3}">{l}</span></div>'
                        _sph.markdown(f'<div class="card">{rows}</div>', unsafe_allow_html=True)
                    try:
                        t0 = time.time()
                        _steps(0,0); _proc,_X,_y,_preds = _predict(_dfi.copy())
                        _steps(1,1); _mv = _calc_metrics(_y, _preds)
                        _steps(2,2); _dr = _run_drift(_X, _y, _preds)
                        _steps(3,3); el = time.time()-t0
                        ts  = datetime.now().strftime("%Y%m%d_%H%M%S")
                        lbl = str(_dfi["Date"].dt.to_period("M").iloc[0]) if "Date" in _dfi.columns else ts
                        os.makedirs(_PROC, exist_ok=True); os.makedirs(_UPL, exist_ok=True)
                        pd.DataFrame({"actual":_y,"predicted":_preds,"error":_y-_preds}).to_csv(
                            os.path.join(_PROC, f"predictions_{lbl}_{ts}.csv"), index=False)
                        _dfi.to_csv(os.path.join(_UPL, _uploaded.name), index=False)
                        with open(os.path.join(_PROC, f"summary_{lbl}_{ts}.json"),"w") as jf:
                            json.dump({"month":lbl,"timestamp":ts,"rows":int(len(_y)),
                                "metrics":{k:round(v,4) for k,v in _mv.items()},
                                "drift":{"severity":_dr["severity"],
                                         "severe_features":_dr["severe_features"],
                                         "mild_features":_dr["mild_features"]}},jf,indent=2)
                        st.session_state.up_result = {"metrics":_mv,"drift":_dr,"y":_y,
                                                      "preds":_preds,"proc":_proc,"elapsed":el}
                        st.session_state.up_history.append({
                            "Time":datetime.now().strftime("%Y-%m-%d %H:%M"),
                            "Rows":len(_y),"MAE":f"${_mv['MAE']:,.0f}",
                            "R2":f"{_mv['R2']:.4f}","Drift":_dr["severity"].upper(),
                            "Sec":f"{el:.1f}s"})
                        _sph.markdown(f'<div class="alert alert-g">Done in {el:.1f}s — view results in the <strong>Prediction Results</strong> tab.</div>', unsafe_allow_html=True)
                        st.rerun()
                    except Exception as e:
                        _sph.empty()
                        st.markdown(f'<div class="alert alert-r">Error: {e}</div>', unsafe_allow_html=True)
                if st.session_state.up_result and st.button("Clear Results", key="up_clear"):
                    st.session_state.up_result = None
                    st.session_state.up_udf = None
                    st.rerun()
        if st.session_state.up_history:
            st.markdown('<div class="section-label">Run History</div>', unsafe_allow_html=True)
            st.dataframe(pd.DataFrame(st.session_state.up_history), width='stretch', hide_index=True)
        if not st.session_state.up_result:
            st.markdown(f'<div class="alert alert-b" style="margin-top:12px">Run the pipeline to see results in the <strong>Prediction Results</strong> tab.</div>', unsafe_allow_html=True)

    with _tab_results:
        if not st.session_state.up_result:
            st.markdown(f'<div style="text-align:center;padding:48px;color:{TEXT3};font-size:13px">Upload a CSV and click Run Pipeline in the Upload &amp; Run tab first.</div>', unsafe_allow_html=True)
        else:
            _r = st.session_state.up_result
            _m = _r["metrics"]; _y = _r["y"]; _preds = _r["preds"]
            _proc = _r["proc"]; _dr = _r["drift"]
            _errors = _y - _preds
            _abs_errors = np.abs(_errors)

            # ── Model Accuracy
            st.markdown('<div class="section-label">Model Accuracy on Uploaded Data</div>', unsafe_allow_html=True)
            rc1,rc2,rc3,rc4,rc5 = st.columns(5)
            rc1.metric("R2",   f"{_m['R2']:.4f}",   f"{_m['R2']-_ubm.get('R2',_m['R2']):+.4f}" if _ubm else None)
            rc2.metric("MAE",  f"${_m['MAE']:,.0f}", f"${_m['MAE']-_ubm.get('MAE',_m['MAE']):+,.0f}" if _ubm else None)
            rc3.metric("RMSE", f"${_m['RMSE']:,.0f}",f"${_m['RMSE']-_ubm.get('RMSE',_m['RMSE']):+,.0f}" if _ubm else None)
            rc4.metric("MAPE", f"{_m['MAPE']:.2f}%", f"{_m['MAPE']-_ubm.get('MAPE',_m['MAPE']):+.2f}%" if _ubm else None)
            rc5.metric("Rows", f"{len(_y):,}")

            # ── Predicted values chart
            st.markdown('<div class="section-label">Actual vs Predicted Values</div>', unsafe_allow_html=True)
            xa = _proc["Date"].values if "Date" in _proc.columns else np.arange(len(_y))
        fig_r = go.Figure()
        fig_r.add_trace(go.Scatter(x=xa, y=_y, name="Actual",
            line=dict(color=BLUE, width=2), mode="lines",
            hovertemplate="Date: %{x}<br>Actual: $%{y:,.0f}<extra></extra>"))
        fig_r.add_trace(go.Scatter(x=xa, y=_preds, name="Predicted",
            line=dict(color=ORANGE, width=2, dash="dot"), mode="lines",
            hovertemplate="Date: %{x}<br>Predicted: $%{y:,.0f}<extra></extra>"))
        fig_r.add_trace(go.Scatter(x=xa, y=_abs_errors, name="Abs Error",
            line=dict(color=RED, width=1), mode="lines", yaxis="y2", opacity=0.5))
        fig_r.update_layout(**PLOT, height=300, hovermode="x unified",
            xaxis=dict(gridcolor=GR),
            yaxis=dict(title="Weekly Sales ($)", gridcolor=GR),
            yaxis2=dict(title="Abs Error ($)", overlaying="y", side="right",
                tickfont=dict(color=RED, size=10), gridcolor="rgba(0,0,0,0)"))
        st.plotly_chart(fig_r, width='stretch')

        # ── Demand Forecast ───────────────────────────────────────────────────────────
        st.markdown('<div class="section-label">Demand Forecast — Uploaded Data</div>', unsafe_allow_html=True)

        _forecast_df = _proc.copy()
        _forecast_df["Predicted_Demand"] = _preds
        _forecast_df["Abs_Error"] = _abs_errors
        _forecast_df["Error_Pct"] = np.where(_y != 0, np.abs(_errors / _y) * 100, 0)

        if "Date" in _forecast_df.columns:
            _ftable = (_forecast_df.groupby(["Store", "Date"])
                       .agg({"Weekly_Sales": "mean", "Predicted_Demand": "mean",
                             "Abs_Error": "mean", "Error_Pct": "mean"})
                       .reset_index().sort_values(["Store", "Date"]))
            _ftable["Date"] = pd.to_datetime(_ftable["Date"]).dt.strftime("%Y-%m-%d")
        else:
            _ftable = (_forecast_df.groupby("Store")
                       .agg({"Weekly_Sales": "mean", "Predicted_Demand": "mean",
                             "Abs_Error": "mean", "Error_Pct": "mean"})
                       .reset_index())

        _ftable = _ftable.rename(columns={
            "Weekly_Sales": "Actual ($)", "Predicted_Demand": "Forecast ($)",
            "Abs_Error": "MAE ($)", "Error_Pct": "Error %",
        })
        for c in ["Actual ($)", "Forecast ($)", "MAE ($)"]:
            _ftable[c] = _ftable[c].round(2)
        _ftable["Error %"] = _ftable["Error %"].round(2)

        ft1, ft2 = st.columns([3, 2])
        with ft1:
            st.dataframe(
                _ftable.style
                    .background_gradient(subset=["Forecast ($)"], cmap="Blues")
                    .format({"Actual ($)": "${:,.2f}", "Forecast ($)": "${:,.2f}",
                             "MAE ($)": "${:,.2f}", "Error %": "{:.2f}%"}),
                width='stretch', hide_index=True, height=320
            )
            st.download_button(
                "Download Forecast CSV", _ftable.to_csv(index=False),
                f"demand_forecast_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv", "text/csv"
            )
        with ft2:
            _store_fc = (_forecast_df.groupby("Store")["Predicted_Demand"]
                         .sum().reset_index().sort_values("Predicted_Demand", ascending=False))
            fig_fc_bar = go.Figure(go.Bar(
                x=_store_fc["Store"].astype(str), y=_store_fc["Predicted_Demand"],
                marker_color=BLUE, opacity=0.85,
                text=[f"${v:,.0f}" for v in _store_fc["Predicted_Demand"]],
                textposition="outside", textfont=dict(color=TEXT3, size=9),
                hovertemplate="Store %{x}<br>Total Forecast: $%{y:,.0f}<extra></extra>"
            ))
            fig_fc_bar.update_layout(**PLOT, height=320,
                title=dict(text="Total Forecasted Demand by Store", font=dict(color=TEXT3, size=11)),
                xaxis=dict(title="Store", gridcolor=GR),
                yaxis=dict(title="Total Predicted Sales ($)", gridcolor=GR))
            st.plotly_chart(fig_fc_bar, width='stretch')

        if "Date" in _forecast_df.columns:
            _weekly_fc = (_forecast_df.groupby("Date")
                          .agg(Actual=("Weekly_Sales", "sum"), Forecast=("Predicted_Demand", "sum"))
                          .reset_index().sort_values("Date"))
            fig_fc_line = go.Figure()
            fig_fc_line.add_trace(go.Scatter(
                x=_weekly_fc["Date"], y=_weekly_fc["Actual"],
                name="Actual Demand", line=dict(color=GREEN, width=2),
                hovertemplate="%{x}<br>Actual: $%{y:,.0f}<extra></extra>"
            ))
            fig_fc_line.add_trace(go.Scatter(
                x=_weekly_fc["Date"], y=_weekly_fc["Forecast"],
                name="Forecasted Demand", line=dict(color=BLUE, width=2.5, dash="dot"),
                fill="tonexty", fillcolor="rgba(59,130,246,0.07)",
                hovertemplate="%{x}<br>Forecast: $%{y:,.0f}<extra></extra>"
            ))
            fig_fc_line.update_layout(**PLOT, height=280, hovermode="x unified",
                title=dict(text="Weekly Demand Forecast — All Stores Combined", font=dict(color=TEXT3, size=11)),
                xaxis=dict(title="Date", gridcolor=GR, tickangle=-45, tickfont=dict(size=9)),
                yaxis=dict(title="Total Weekly Sales ($)", gridcolor=GR))
            st.plotly_chart(fig_fc_line, width='stretch')

        # ── Error distribution + scatter ──────────────────────────────────────────────
        ec1, ec2 = st.columns(2)
        with ec1:
            st.markdown('<div class="section-label">Prediction Error Distribution</div>', unsafe_allow_html=True)
            fig_ed = go.Figure()
            fig_ed.add_trace(go.Histogram(x=_errors, nbinsx=40,
                marker_color=BLUE, opacity=0.75, name="Residuals"))
            fig_ed.add_vline(x=0, line=dict(color=GREEN, width=2, dash="dash"))
            fig_ed.add_vline(x=float(np.mean(_errors)), line=dict(color=ORANGE, width=1.5, dash="dot"),
                annotation_text=f"Mean: ${np.mean(_errors):,.0f}",
                annotation_font=dict(color=ORANGE, size=10))
            fig_ed.update_layout(**PLOT, height=260,
                xaxis=dict(title="Residual ($)", gridcolor=GR),
                yaxis=dict(title="Count", gridcolor=GR))
            st.plotly_chart(fig_ed, width='stretch')
        with ec2:
            st.markdown('<div class="section-label">Actual vs Predicted Scatter</div>', unsafe_allow_html=True)
            cs = [RED if abs(e)>_m["MAE"]*3 else ORANGE if abs(e)>_m["MAE"] else GREEN for e in _errors]
            fig_sc = go.Figure()
            fig_sc.add_trace(go.Scatter(x=_y, y=_preds, mode="markers",
                marker=dict(color=cs, size=5, opacity=0.7),
                hovertemplate="Actual: $%{x:,.0f}<br>Predicted: $%{y:,.0f}<extra></extra>"))
            mn_v, mx_v = float(min(_y.min(), _preds.min())), float(max(_y.max(), _preds.max()))
            fig_sc.add_trace(go.Scatter(x=[mn_v,mx_v], y=[mn_v,mx_v],
                mode="lines", line=dict(color=GREEN, width=1.5, dash="dash"), name="Perfect"))
            fig_sc.update_layout(**PLOT, height=260,
                xaxis=dict(title="Actual ($)", gridcolor=GR),
                yaxis=dict(title="Predicted ($)", gridcolor=GR))
            st.plotly_chart(fig_sc, width='stretch')

        # ── Data Drift Report ────────────────────────────────────────────────────────────
        st.markdown('<div class="section-label">Data Drift Report</div>', unsafe_allow_html=True)
        d1, d2, d3, d4 = st.columns(4)
        d1.metric("Drift Severity",    _dr["severity"].upper())
        d2.metric("Severe Features",   _dr.get("severe_features", 0))
        d3.metric("Mild Features",     _dr.get("mild_features", 0))
        d4.metric("Total Features",    len(_ufnames))
        alert_map = {
            "severe": f'<div class="alert alert-r"><strong style="color:{RED}">Severe data drift detected.</strong> Distribution of uploaded data differs significantly from training data. Retraining recommended.</div>',
            "mild":   f'<div class="alert alert-y"><strong style="color:{ORANGE}">Mild data drift detected.</strong> Some features show distribution shift. Monitor closely.</div>',
            "none":   f'<div class="alert alert-g"><strong style="color:{GREEN}">No significant data drift.</strong> Uploaded data is consistent with training distribution.</div>',
        }
        st.markdown(alert_map.get(_dr["severity"], ""), unsafe_allow_html=True)

        # KS drift per feature from uploaded data vs baseline
        if _uproc is not None and len(_ufnames) > 0:
            try:
                from scipy.stats import ks_2samp
                up_ks_rows = []
                for f in _ufnames[:30]:  # top 30 features
                    if f in _proc.columns and f in _uproc.columns:
                        a = _uproc[f].dropna().values
                        b = _proc[f].dropna().values
                        if len(a) > 5 and len(b) > 5:
                            ks_s, ks_p = ks_2samp(a, b)
                            up_ks_rows.append({"Feature": f, "KS": round(float(ks_s),4),
                                               "p-value": round(float(ks_p),4)})
                if up_ks_rows:
                    df_upks = pd.DataFrame(up_ks_rows).sort_values("KS", ascending=False)
                    df_upks["Status"] = df_upks["KS"].apply(
                        lambda v: "SEVERE" if v >= ks_severe else ("MILD" if v >= ks_mild else "NONE"))

                    # KS bar chart
                    top20 = df_upks.head(20)
                    kc = [RED if v=="SEVERE" else ORANGE if v=="MILD" else GREEN for v in top20["Status"]]
                    fig_upks = go.Figure(go.Bar(
                        x=top20["KS"], y=top20["Feature"], orientation="h",
                        marker_color=kc, opacity=0.85,
                        text=[f"{v:.4f}" for v in top20["KS"]], textposition="outside",
                        textfont=dict(color=TEXT3, size=9),
                        hovertemplate="%{y}: KS=%{x:.4f}<extra></extra>"))
                    fig_upks.add_vline(x=ks_severe, line=dict(color=RED, width=1.5, dash="dash"))
                    fig_upks.add_vline(x=ks_mild,   line=dict(color=ORANGE, width=1.5, dash="dot"))
                    fig_upks.update_layout(**PLOT, height=max(280, len(top20)*22),
                        xaxis=dict(range=[0, max(top20["KS"])*1.25], gridcolor=GR),
                        yaxis=dict(autorange="reversed", gridcolor=GR))
                    st.plotly_chart(fig_upks, width='stretch')
            except Exception:
                pass

        # ── Concept Drift Report ─────────────────────────────────────────────────────────
        st.markdown('<div class="section-label">Concept Drift Report</div>', unsafe_allow_html=True)
        # Concept drift = model error pattern change. Show rolling MAE vs baseline.
        window = max(1, len(_errors)//10)
        rolling_mae = pd.Series(_abs_errors).rolling(window, min_periods=1).mean().values
        baseline_mae_line = np.full(len(_errors), _ubm.get("MAE", MAE))
        concept_drift_ratio = float(np.mean(_abs_errors)) / max(_ubm.get("MAE", MAE), 1)
        concept_sev = "SEVERE" if concept_drift_ratio > 2.0 else ("MILD" if concept_drift_ratio > 1.2 else "NONE")
        concept_col = RED if concept_sev == "SEVERE" else (ORANGE if concept_sev == "MILD" else GREEN)

        cc1, cc2, cc3 = st.columns(3)
        cc1.metric("Concept Drift",    concept_sev)
        cc2.metric("Error Ratio",      f"{concept_drift_ratio:.2f}x")
        cc3.metric("Mean Abs Error",   f"${float(np.mean(_abs_errors)):,.0f}")

        fig_cd = go.Figure()
        fig_cd.add_trace(go.Scatter(y=rolling_mae, name=f"Rolling MAE (w={window})",
            line=dict(color=RED, width=2), mode="lines",
            hovertemplate="Row %{x}<br>Rolling MAE: $%{y:,.0f}<extra></extra>"))
        fig_cd.add_trace(go.Scatter(y=baseline_mae_line, name="Train Baseline MAE",
            line=dict(color=GREEN, width=1.5, dash="dash"), mode="lines"))
        fig_cd.add_trace(go.Scatter(y=_abs_errors, name="Abs Error",
            line=dict(color=BLUE, width=1), mode="lines", opacity=0.3))
        fig_cd.update_layout(**PLOT, height=280, hovermode="x unified",
            xaxis=dict(title="Sample Index", gridcolor=GR),
            yaxis=dict(title="MAE ($)", gridcolor=GR))
        st.plotly_chart(fig_cd, width='stretch')

        st.markdown(
            f'<div class="alert" style="border-left:3px solid {concept_col};background:rgba(0,0,0,0.03);padding:10px 14px;font-size:13px;margin:6px 0">'
            f'Concept drift ratio: <strong style="color:{concept_col}">{concept_drift_ratio:.2f}x</strong> — '
            f'Model error on uploaded data is <strong>{concept_drift_ratio:.2f}x</strong> the training baseline. '
            f'Status: <strong style="color:{concept_col}">{concept_sev}</strong></div>',
            unsafe_allow_html=True
        )

        # ── Store-level MAE ───────────────────────────────────────────────────────────────
        if "Store" in _proc.columns:
            st.markdown('<div class="section-label">Store-Level Performance</div>', unsafe_allow_html=True)
            tmp = _proc.copy(); tmp["_e"] = _abs_errors
            sg  = tmp.groupby("Store").agg(MAE=("_e","mean"), Count=("_e","count"),
                                            Actual=("Weekly_Sales","mean")).reset_index().sort_values("MAE",ascending=False)
            q75 = sg["MAE"].quantile(0.75); q50 = sg["MAE"].quantile(0.5)
            sc  = [RED if v>q75 else ORANGE if v>q50 else GREEN for v in sg["MAE"]]
            sl1, sl2 = st.columns(2)
            with sl1:
                fig_s = go.Figure(go.Bar(x=sg["Store"].astype(str), y=sg["MAE"],
                    marker_color=sc, opacity=0.85,
                    text=[f"${v:,.0f}" for v in sg["MAE"]], textposition="outside",
                    textfont=dict(color=TEXT3, size=9),
                    hovertemplate="Store %{x}<br>MAE: $%{y:,.0f}<extra></extra>"))
                fig_s.update_layout(**PLOT, height=260,
                    xaxis=dict(title="Store", gridcolor=GR),
                    yaxis=dict(title="MAE ($)", gridcolor=GR))
                st.plotly_chart(fig_s, width='stretch')
            with sl2:
                fig_s2 = go.Figure(go.Scatter(
                    x=sg["Actual"], y=sg["MAE"], mode="markers+text",
                    text=sg["Store"].astype(str), textposition="top center",
                    textfont=dict(size=9, color=TEXT3),
                    marker=dict(color=sc, size=10, opacity=0.8),
                    hovertemplate="Store %{text}<br>Avg Sales: $%{x:,.0f}<br>MAE: $%{y:,.0f}<extra></extra>"))
                fig_s2.update_layout(**PLOT, height=260,
                    xaxis=dict(title="Avg Actual Sales ($)", gridcolor=GR),
                    yaxis=dict(title="MAE ($)", gridcolor=GR))
                st.plotly_chart(fig_s2, width='stretch')

        # ── Uploaded Data Chart Gallery ────────────────────────────────────────────────────
        st.markdown('<div class="section-label">Uploaded Data — Chart Gallery</div>', unsafe_allow_html=True)

        # Row 1: Pie (error buckets) + Radar (metrics vs baseline)
        ug1, ug2 = st.columns(2)
        with ug1:
            good  = int(np.sum(_abs_errors <= _m["MAE"]))
            warn  = int(np.sum((_abs_errors > _m["MAE"]) & (_abs_errors <= _m["MAE"]*3)))
            bad   = int(np.sum(_abs_errors > _m["MAE"]*3))
            fig_upie = go.Figure(go.Pie(
                labels=["Good","Warning","Bad"],
                values=[good, warn, bad],
                marker=dict(colors=[GREEN, ORANGE, RED]),
                hole=0.4, textfont=dict(color="white", size=12),
                hovertemplate="%{label}: %{value} rows (%{percent})<extra></extra>"))
            fig_upie.update_layout(**PLOT, height=260,
                title=dict(text="Prediction Quality Buckets", font=dict(color=TEXT3, size=11)))
            st.plotly_chart(fig_upie, width='stretch')
        with ug2:
            bm_r2   = _ubm.get("R2",   R2)
            bm_mape = _ubm.get("MAPE", MAPE)
            bm_mae  = _ubm.get("MAE",  MAE)
            bm_rmse = _ubm.get("RMSE", RMSE)
            rad_cats = ["R²","1-MAPE%","MAE Score","RMSE Score","Row Coverage"]
            def _norm(v, best, worst): return max(0, min(100, (v-worst)/(best-worst+1e-9)*100))
            rad_up  = [_m["R2"]*100, max(0,100-_m["MAPE"]),
                       _norm(bm_mae, 0, bm_mae*3)*100 if bm_mae else 50,
                       _norm(bm_rmse, 0, bm_rmse*3)*100 if bm_rmse else 50, 100]
            rad_bl  = [bm_r2*100, max(0,100-bm_mape), 100, 100, 100]
            fig_urad = go.Figure()
            fig_urad.add_trace(go.Scatterpolar(
                r=rad_bl+[rad_bl[0]], theta=rad_cats+[rad_cats[0]],
                fill="toself", fillcolor="rgba(16,185,129,0.1)",
                line=dict(color=GREEN, width=2, dash="dash"), name="Baseline"))
            fig_urad.add_trace(go.Scatterpolar(
                r=rad_up+[rad_up[0]], theta=rad_cats+[rad_cats[0]],
                fill="toself", fillcolor="rgba(59,130,246,0.15)",
                line=dict(color=BLUE, width=2), name="Uploaded"))
            fig_urad.update_layout(**PLOT, height=260,
                polar=dict(bgcolor=CARD,
                    radialaxis=dict(visible=True, range=[0,100], gridcolor=BORDER, tickfont=dict(color=TEXT3,size=9)),
                    angularaxis=dict(gridcolor=BORDER, tickfont=dict(color=TEXT3,size=10))),
                title=dict(text="Model Metrics Radar — Uploaded vs Baseline", font=dict(color=TEXT3, size=11)))
            st.plotly_chart(fig_urad, width='stretch')

        # Row 2: Waterfall (error decomposition) + Grouped column (store top10)
        ug3, ug4 = st.columns(2)
        with ug3:
            pct_err = _errors / np.where(_y != 0, _y, 1) * 100
            buckets = ["<-20%","-20 to -10%","-10 to 0%","0 to 10%","10 to 20%",">20%"]
            cuts    = [-np.inf,-20,-10,0,10,20,np.inf]
            bkt_cnt = [int(np.sum((pct_err>=cuts[i]) & (pct_err<cuts[i+1]))) for i in range(6)]
            wf_meas = ["absolute"]*6
            fig_uwf = go.Figure(go.Waterfall(
                x=buckets, y=bkt_cnt, measure=wf_meas,
                increasing=dict(marker=dict(color=BLUE)),
                decreasing=dict(marker=dict(color=PURPLE)),
                totals=dict(marker=dict(color=ORANGE)),
                connector=dict(line=dict(color=BORDER, width=1)),
                texttemplate="%{y}", textposition="outside",
                textfont=dict(color=TEXT3, size=9)))
            fig_uwf.update_layout(**PLOT, height=280,
                title=dict(text="Error % Bucket Waterfall", font=dict(color=TEXT3, size=11)),
                xaxis=dict(gridcolor=GR, tickfont=dict(size=9)),
                yaxis=dict(title="Row Count", gridcolor=GR))
            st.plotly_chart(fig_uwf, width='stretch')
        with ug4:
            if "Store" in _proc.columns:
                tmp2 = _proc.copy(); tmp2["_e"] = _abs_errors; tmp2["_a"] = _y; tmp2["_p"] = _preds
                sg2  = tmp2.groupby("Store").agg(MAE=("_e","mean"),Actual=("_a","mean"),Pred=("_p","mean")).reset_index()
                sg2  = sg2.sort_values("MAE", ascending=False).head(10)
                fig_grp2 = go.Figure()
                fig_grp2.add_trace(go.Bar(x=sg2["Store"].astype(str), y=sg2["Actual"],
                    name="Avg Actual", marker_color=BLUE, opacity=0.8))
                fig_grp2.add_trace(go.Bar(x=sg2["Store"].astype(str), y=sg2["Pred"],
                    name="Avg Predicted", marker_color=ORANGE, opacity=0.8))
                fig_grp2.update_layout(**PLOT, height=280, barmode="group",
                    title=dict(text="Top 10 Stores — Actual vs Predicted", font=dict(color=TEXT3, size=11)),
                    xaxis=dict(title="Store", gridcolor=GR),
                    yaxis=dict(title="Avg Weekly Sales ($)", gridcolor=GR))
                st.plotly_chart(fig_grp2, width='stretch')

        # Row 3: Box (actual vs predicted) + Histogram (% error)
        ug5, ug6 = st.columns(2)
        with ug5:
            fig_ubx = go.Figure()
            fig_ubx.add_trace(go.Box(y=_y,     name="Actual",    marker_color=BLUE,   boxmean=True))
            fig_ubx.add_trace(go.Box(y=_preds, name="Predicted", marker_color=ORANGE, boxmean=True))
            fig_ubx.add_trace(go.Box(y=_abs_errors, name="Abs Error", marker_color=RED, boxmean=True))
            fig_ubx.update_layout(**PLOT, height=280,
                title=dict(text="Distribution Box Plot", font=dict(color=TEXT3, size=11)),
                yaxis=dict(title="Weekly Sales ($)", gridcolor=GR))
            st.plotly_chart(fig_ubx, width='stretch')
        with ug6:
            fig_uhist = go.Figure()
            fig_uhist.add_trace(go.Histogram(x=pct_err, nbinsx=40,
                marker_color=PURPLE, opacity=0.8, name="% Error"))
            fig_uhist.add_vline(x=0, line=dict(color=GREEN, width=2, dash="dash"))
            fig_uhist.update_layout(**PLOT, height=280,
                title=dict(text="% Error Histogram", font=dict(color=TEXT3, size=11)),
                xaxis=dict(title="% Error", gridcolor=GR),
                yaxis=dict(title="Count", gridcolor=GR))
            st.plotly_chart(fig_uhist, width='stretch')

        # Row 4: Pyramid (store MAE top vs bottom) + Heatmap (store × week)
        ug7, ug8 = st.columns(2)
        with ug7:
            if "Store" in _proc.columns:
                tmp3 = _proc.copy(); tmp3["_e"] = _abs_errors
                sg3  = tmp3.groupby("Store")["_e"].mean().reset_index().sort_values("_e")
                top5s = sg3.tail(5); bot5s = sg3.head(5)
                fig_upyr = go.Figure()
                fig_upyr.add_trace(go.Bar(
                    y=top5s["Store"].astype(str), x=-top5s["_e"],
                    orientation="h", name="Worst 5", marker_color=RED, opacity=0.85))
                fig_upyr.add_trace(go.Bar(
                    y=bot5s["Store"].astype(str), x=bot5s["_e"],
                    orientation="h", name="Best 5", marker_color=GREEN, opacity=0.85))
                fig_upyr.update_layout(**PLOT, height=280, barmode="overlay",
                    title=dict(text="Store MAE Pyramid", font=dict(color=TEXT3, size=11)),
                    xaxis=dict(gridcolor=GR), yaxis=dict(gridcolor=GR))
                st.plotly_chart(fig_upyr, width='stretch')
        with ug8:
            if "Store" in _proc.columns and "Date" in _proc.columns:
                tmp4 = _proc.copy(); tmp4["_e"] = _abs_errors
                tmp4["Week"] = pd.to_datetime(tmp4["Date"]).dt.isocalendar().week.astype(int)
                hm_stores = sorted(tmp4["Store"].unique())[:10]
                hm_weeks  = sorted(tmp4["Week"].unique())[:8]
                hm_z2 = [[tmp4[(tmp4["Store"]==s)&(tmp4["Week"]==w)]["_e"].mean()
                           if len(tmp4[(tmp4["Store"]==s)&(tmp4["Week"]==w)])>0 else 0
                           for w in hm_weeks] for s in hm_stores]
                fig_uhm = go.Figure(go.Heatmap(
                    z=hm_z2, x=[f"W{w}" for w in hm_weeks],
                    y=[f"S{s}" for s in hm_stores],
                    colorscale=[[0,"rgba(16,185,129,0.7)"],[0.5,"rgba(245,158,11,0.8)"],[1,"rgba(239,68,68,0.95)"]],
                    showscale=True, colorbar=dict(thickness=10, tickfont=dict(color=TEXT3,size=9)),
                    hovertemplate="Store %{y} Week %{x}<br>MAE: $%{z:,.0f}<extra></extra>"))
                fig_uhm.update_layout(**{**PLOT,"height":280,"margin":dict(t=36,b=28,l=40,r=40)},
                    title=dict(text="Store × Week MAE Heatmap", font=dict(color=TEXT3, size=11)))
                st.plotly_chart(fig_uhm, width='stretch')

        # ── Export ─────────────────────────────────────────────────────────────────────────
        st.markdown('<div class="section-label">Export</div>', unsafe_allow_html=True)
        ex1, ex2, ex3 = st.columns(3)
        with ex1:
            out = pd.DataFrame({"actual":_y,"predicted":_preds,"error":_errors,"abs_error":_abs_errors})
            st.download_button("Predictions CSV", out.to_csv(index=False),
                               f"predictions_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv","text/csv")
        with ex2:
            if st.session_state.up_history:
                st.download_button("Run History CSV",
                                   pd.DataFrame(st.session_state.up_history).to_csv(index=False),
                                   f"history_{datetime.now().strftime('%Y%m%d')}.csv","text/csv")
        with ex3:
            summary_out = pd.DataFrame([{"Metric":k,"Value":round(v,4)} for k,v in _m.items()] +
                [{"Metric":"Drift Severity","Value":_dr["severity"]},
                 {"Metric":"Concept Drift Ratio","Value":round(concept_drift_ratio,4)},
                 {"Metric":"Concept Drift Status","Value":concept_sev}])
            st.download_button("Summary Report CSV", summary_out.to_csv(index=False),
                               f"summary_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv","text/csv")
