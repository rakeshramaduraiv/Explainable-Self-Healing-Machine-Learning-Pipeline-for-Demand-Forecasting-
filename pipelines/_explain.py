"""
_explain.py - SHAP Explainability + Logbook
Explains WHY drift happened, WHY action was taken, feature contributions, stores history.
"""
import os, sys, io, base64, json
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import joblib
from datetime import datetime

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from pipelines.utils import PROCESSED_DIR, MODEL_DIR, logger

REPORT_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "reports")
LOGBOOK    = os.path.join(REPORT_DIR, "logbook.json")

FEATURE_DESC = {
    "lag_1"      : "Yesterday's sales",
    "lag_7"      : "Sales same day last week",
    "lag_14"     : "Sales 2 weeks ago",
    "lag_28"     : "Sales same day last month",
    "rmean_7"    : "Average sales last 7 days",
    "rmean_14"   : "Average sales last 14 days",
    "rmean_28"   : "Average sales last 28 days",
    "rstd_7"     : "Sales variability last 7 days",
    "rstd_14"    : "Sales variability last 14 days",
    "rstd_28"    : "Sales variability last 28 days",
    "sell_price" : "Current selling price",
    "price_norm" : "Normalized price (0=cheapest, 1=most expensive)",
    "price_max"  : "Maximum historical price",
    "price_min"  : "Minimum historical price",
    "snap_CA"    : "SNAP benefit day in California",
    "snap_TX"    : "SNAP benefit day in Texas",
    "snap_WI"    : "SNAP benefit day in Wisconsin",
    "dayofweek"  : "Day of the week",
    "weekofyear" : "Week number in the year",
    "month"      : "Month of the year",
    "year"       : "Year",
    "is_weekend" : "Weekend flag",
    "dow_sin"    : "Cyclic day encoding (sine)",
    "dow_cos"    : "Cyclic day encoding (cosine)",
    "item_id"    : "Product identifier",
    "dept_id"    : "Department identifier",
    "cat_id"     : "Category (HOBBIES/FOODS/HOUSEHOLD)",
    "store_id"   : "Store identifier",
    "state_id"   : "State identifier",
    "wm_yr_wk"   : "Walmart week number",
}

THRESHOLD_EXPLAIN = {
    "low": {
        "range": "below 0.1",
        "meaning": "The model predictions closely match actual sales patterns.",
    },
    "medium": {
        "range": "between 0.1 and 0.3",
        "meaning": "Some features have shifted — predictions are slightly off.",
    },
    "high": {
        "range": "above 0.3 (or PSI > 0.2)",
        "meaning": "Major distribution shift — predictions are significantly wrong.",
    },
}

ACTION_EXPLAIN = {
    "monitor": {
        "label": "Monitor Only",
        "what": "No changes made to the model.",
        "why": "Drift is minimal — the model is still accurate enough.",
        "detail": "We continue using the current model and will check again next month.",
    },
    "fine_tune": {
        "label": "Fine-Tune (Incremental Learning)",
        "what": "Added 500 new decision trees on top of the existing model.",
        "why": "Moderate drift detected — the model needs to learn new patterns without forgetting old ones.",
        "detail": "Fine-tuning uses a low learning rate (0.01-0.02) to gently adapt the model. "
                  "It keeps all existing knowledge and adds new trees trained on recent + new data.",
    },
    "sliding_window": {
        "label": "Full Retrain (Sliding Window)",
        "what": "Rebuilt the entire model using the last 6 months of data.",
        "why": "Severe drift detected — old patterns are no longer relevant.",
        "detail": "The model is retrained from scratch on a 6-month window. "
                  "Old data beyond 6 months is discarded. If the new model is worse, we roll back automatically.",
    },
    "rollback": {
        "label": "Rollback",
        "what": "Reverted to the previous model version.",
        "why": "The retrained/fine-tuned model performed worse than the original.",
        "detail": "Automatic safety check detected regression — the old model was restored.",
    },
}


def _fig_to_b64(fig):
    buf = io.BytesIO()
    fig.savefig(buf, format="png", bbox_inches="tight", dpi=110)
    buf.seek(0)
    enc = base64.b64encode(buf.read()).decode()
    plt.close(fig)
    return enc


def _dark(fig, axes):
    fig.patch.set_facecolor("#1e1e2e")
    for ax in (axes if hasattr(axes, "__iter__") else [axes]):
        ax.set_facecolor("#1e1e2e")
        ax.tick_params(colors="#cdd6f4")
        ax.xaxis.label.set_color("#cdd6f4")
        ax.yaxis.label.set_color("#cdd6f4")
        for sp in ax.spines.values():
            sp.set_edgecolor("#45475a")


# ── SHAP Analysis ────────────────────────────────────────
def _run_shap_analysis(month_label):
    """Run SHAP on actual month features, return top features + chart."""
    model_path = f"{MODEL_DIR}/model.pkl"
    feat_path  = f"{PROCESSED_DIR}/actual_month_features.parquet"
    if not os.path.exists(model_path) or not os.path.exists(feat_path):
        return None, None, None

    try:
        import shap
        model   = joblib.load(model_path)
        feat_df = pd.read_parquet(feat_path)
        drop    = ["id", "date", "sales"] + list(feat_df.select_dtypes(include="object").columns)
        X_cols  = [c for c in feat_df.columns if c not in drop]
        X_samp  = feat_df[X_cols].dropna().sample(min(200, len(feat_df)), random_state=42)

        exp = shap.TreeExplainer(model)
        sv  = exp.shap_values(X_samp)

        # Mean absolute SHAP per feature
        mean_abs = np.abs(sv).mean(axis=0)
        shap_df  = pd.DataFrame({"feature": X_cols, "shap_importance": mean_abs})
        shap_df  = shap_df.sort_values("shap_importance", ascending=False)
        top15    = shap_df.head(15)

        # Bar chart
        fig, ax = plt.subplots(figsize=(10, 6))
        _dark(fig, ax)
        colors = ["#89b4fa" if i < 5 else "#a6e3a1" if i < 10 else "#fab387"
                  for i in range(len(top15))]
        ax.barh(
            [FEATURE_DESC.get(f, f) for f in top15["feature"].values[::-1]],
            top15["shap_importance"].values[::-1],
            color=colors[::-1]
        )
        ax.set_title(f"SHAP Feature Impact — {month_label}", color="#cba6f7", fontsize=14)
        ax.set_xlabel("Mean |SHAP value| (impact on prediction)", color="#cdd6f4")
        plt.tight_layout()
        shap_chart = _fig_to_b64(fig)

        # Beeswarm chart
        beeswarm_chart = None
        try:
            fig2, ax2 = plt.subplots(figsize=(10, 6))
            _dark(fig2, ax2)
            shap.summary_plot(sv, X_samp, plot_type="dot", show=False, max_display=15)
            ax2 = plt.gca()
            _dark(fig2, ax2)
            ax2.set_title(f"SHAP Beeswarm — {month_label}", color="#cba6f7", fontsize=14)
            plt.tight_layout()
            beeswarm_chart = _fig_to_b64(fig2)
        except Exception as e:
            logger.warning(f"Beeswarm chart failed: {e}")

        # Top features with human descriptions
        top_shap = []
        for _, row in top15.iterrows():
            fname = row["feature"]
            top_shap.append({
                "feature": fname,
                "desc": FEATURE_DESC.get(fname, fname),
                "shap_importance": round(float(row["shap_importance"]), 4),
            })

        return top_shap, shap_chart, beeswarm_chart

    except Exception as e:
        logger.warning(f"SHAP analysis failed: {e}")
        return None, None, None


# ── Feature Drift Contribution Analysis ──────────────────
def _analyze_drift_contributions(feature_drift):
    """Rank features by drift contribution and explain each."""
    if not feature_drift:
        return [], None

    sorted_fd = sorted(feature_drift.items(), key=lambda x: x[1], reverse=True)
    total_psi = sum(v for _, v in sorted_fd) or 1.0

    contributions = []
    for feat, psi_val in sorted_fd:
        desc = FEATURE_DESC.get(feat, feat)
        pct  = round(psi_val / total_psi * 100, 1)

        if psi_val > 0.2:
            severity = "HIGH"
            impact   = f"This feature changed drastically (PSI={psi_val:.3f}). It is a major driver of drift."
            suggestion = _get_feature_suggestion(feat, "high")
        elif psi_val > 0.1:
            severity = "MEDIUM"
            impact   = f"This feature shifted moderately (PSI={psi_val:.3f}). It contributes to drift."
            suggestion = _get_feature_suggestion(feat, "medium")
        else:
            severity = "LOW"
            impact   = f"This feature is stable (PSI={psi_val:.3f}). Not a significant drift driver."
            suggestion = "No action needed for this feature."

        contributions.append({
            "feature": feat,
            "desc": desc,
            "psi": round(psi_val, 4),
            "contribution_pct": pct,
            "severity": severity,
            "impact": impact,
            "suggestion": suggestion,
        })

    # Drift contribution pie chart
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 5))
    _dark(fig, [ax1, ax2])

    # Bar chart with severity colors
    feats  = [FEATURE_DESC.get(c["feature"], c["feature"]) for c in contributions]
    vals   = [c["psi"] for c in contributions]
    colors = ["#f38ba8" if c["severity"] == "HIGH" else "#fab387" if c["severity"] == "MEDIUM"
              else "#a6e3a1" for c in contributions]

    ax1.barh(feats[::-1], vals[::-1], color=colors[::-1])
    ax1.axvline(0.1, color="#fab387", ls="--", lw=1.5, label="Medium threshold (0.1)")
    ax1.axvline(0.2, color="#f38ba8", ls="--", lw=1.5, label="High threshold (0.2)")
    ax1.set_title("Feature Drift (PSI)", color="#cba6f7", fontsize=13)
    ax1.set_xlabel("PSI Score", color="#cdd6f4")
    ax1.legend(facecolor="#313244", labelcolor="#cdd6f4", fontsize=9)

    # Contribution pie
    top5 = contributions[:5]
    pie_labels = [FEATURE_DESC.get(c["feature"], c["feature"]) for c in top5]
    pie_vals   = [c["contribution_pct"] for c in top5]
    pie_colors = ["#f38ba8", "#fab387", "#fbbf24", "#a6e3a1", "#89b4fa"][:len(top5)]
    wedges, texts, autotexts = ax2.pie(
        pie_vals, labels=pie_labels, autopct="%1.0f%%",
        colors=pie_colors, textprops={"color": "#cdd6f4", "fontsize": 10}
    )
    for t in autotexts:
        t.set_color("#1e1e2e")
        t.set_fontweight("bold")
    ax2.set_title("Drift Contribution Share", color="#cba6f7", fontsize=13)

    plt.tight_layout()
    chart = _fig_to_b64(fig)

    return contributions, chart


def _get_feature_suggestion(feat, severity):
    """Human-readable suggestion per feature."""
    suggestions = {
        "sell_price": {
            "high": "Prices changed significantly. Check for promotions, markdowns, or supplier price changes.",
            "medium": "Minor price shifts detected. Monitor for ongoing pricing strategy changes.",
        },
        "lag_7": {
            "high": "Weekly sales pattern broke down. Possible event, holiday, or supply disruption last week.",
            "medium": "Slight change in weekly rhythm. Could be seasonal transition.",
        },
        "lag_28": {
            "high": "Monthly sales pattern changed drastically. Major demand shift or external event.",
            "medium": "Monthly pattern shifting. Seasonal change or gradual trend.",
        },
        "rmean_7": {
            "high": "Short-term average sales changed a lot. Sudden demand spike or drop.",
            "medium": "Short-term trend shifting slightly.",
        },
        "rmean_28": {
            "high": "Long-term average sales changed significantly. Structural demand change.",
            "medium": "Long-term trend is evolving. Normal seasonal movement.",
        },
    }
    default = {
        "high": f"This feature ({FEATURE_DESC.get(feat, feat)}) changed significantly. Investigate the root cause.",
        "medium": f"This feature ({FEATURE_DESC.get(feat, feat)}) shifted moderately. Keep monitoring.",
    }
    return suggestions.get(feat, default).get(severity, "No specific suggestion.")


# ── Main Explanation Builder ─────────────────────────────
def get_shap_explanation(drift_result, month_label):
    level = drift_result.get("level", "unknown")
    ks    = drift_result.get("ks_stat") or 0
    psi   = drift_result.get("psi") or 0
    mae   = drift_result.get("mae") or 0
    score = drift_result.get("drift_score") or 0
    fd    = drift_result.get("feature_drift") or {}

    # ── Threshold explanation ──
    thresh = THRESHOLD_EXPLAIN.get(level, {"range": "unknown", "meaning": "Could not determine."})

    # ── Action decision explanation ──
    if level == "low":
        action_key = "monitor"
        decision_reasoning = (
            f"The drift score ({score:.3f}) is {thresh['range']}. "
            f"KS statistic ({ks:.3f}) shows actual sales distribution closely matches training data. "
            f"PSI ({psi:.3f}) confirms feature distributions are stable. "
            f"Current MAE ({mae:.4f}) is within acceptable range. "
            f"Conclusion: Model is performing well — no intervention needed."
        )
        plain_english = (
            "Your model is working great this month! "
            "The sales patterns haven't changed much from what the model learned. "
            "No updates needed — we'll check again when you upload next month's data."
        )
    elif level == "medium":
        action_key = "fine_tune"
        decision_reasoning = (
            f"The drift score ({score:.3f}) is {thresh['range']}. "
            f"KS statistic ({ks:.3f}) shows a moderate shift in sales distribution. "
            f"PSI ({psi:.3f}) indicates some features have changed. "
            f"This level of drift means the model is slightly off but not completely wrong. "
            f"Fine-tuning is chosen over full retrain because: "
            f"(1) The existing model still has useful knowledge, "
            f"(2) Only incremental adaptation is needed, "
            f"(3) Fine-tuning is faster and less risky than full retrain."
        )
        plain_english = (
            "The model's predictions are a bit off this month. "
            "Some things have changed — maybe prices shifted, buying patterns changed slightly, "
            "or seasonal effects kicked in. "
            "We'll fine-tune the model: keep everything it already knows, "
            "but teach it the new patterns from this month's data."
        )
    elif level == "high":
        action_key = "sliding_window"
        decision_reasoning = (
            f"The drift score ({score:.3f}) is {thresh['range']}. "
            f"KS statistic ({ks:.3f}) shows actual sales are very different from what the model expected. "
            f"PSI ({psi:.3f}) shows major feature distribution changes. "
            f"Fine-tuning won't be enough because the underlying patterns have changed too much. "
            f"Full retrain is chosen because: "
            f"(1) Old patterns are no longer relevant, "
            f"(2) The model needs to learn from scratch on recent data, "
            f"(3) A 6-month sliding window captures current trends while discarding stale data."
        )
        plain_english = (
            "The model's predictions are significantly wrong this month. "
            "Major changes happened — could be big price changes, new products, store changes, "
            "economic shifts, or a major event. "
            "We need to rebuild the model from scratch using the last 6 months of data "
            "so it learns the new reality."
        )
    else:
        action_key = "monitor"
        decision_reasoning = "Could not determine drift — data alignment issue. Check id and date format."
        plain_english = "We couldn't compare predictions with actual data. Please check the upload format."

    # ── Feature drift contributions ──
    contributions, drift_contrib_chart = _analyze_drift_contributions(fd)

    # ── SHAP analysis ──
    top_shap, shap_chart, beeswarm_chart = _run_shap_analysis(month_label)

    # ── Build drift summary sentence ──
    high_drift_feats = [c for c in contributions if c["severity"] == "HIGH"]
    med_drift_feats  = [c for c in contributions if c["severity"] == "MEDIUM"]

    if high_drift_feats:
        drift_summary = (
            f"The main drivers of drift are: "
            + ", ".join(f"{c['desc']} (PSI={c['psi']:.3f})" for c in high_drift_feats[:3])
            + ". These features changed significantly compared to training data."
        )
    elif med_drift_feats:
        drift_summary = (
            f"Moderate shifts detected in: "
            + ", ".join(f"{c['desc']} (PSI={c['psi']:.3f})" for c in med_drift_feats[:3])
            + ". No single feature dominates — drift is spread across multiple features."
        )
    else:
        drift_summary = "All tracked features are stable. No significant feature-level drift detected."

    # ── Threshold breakdown ──
    threshold_breakdown = {
        "drift_score": {"value": round(score, 4), "thresholds": {"low": "< 0.1", "medium": "0.1 - 0.3", "high": "> 0.3"},
                        "your_level": level},
        "ks_stat":     {"value": round(ks, 4), "meaning": "Measures how different actual vs training sales distributions are (0=identical, 1=completely different)"},
        "psi":         {"value": round(psi, 4), "meaning": "Population Stability Index — measures feature distribution shift (>0.2 = significant)"},
        "mae":         {"value": round(mae, 4), "meaning": "Mean Absolute Error — average prediction error in units"},
    }

    return {
        "month"               : month_label,
        "drift_level"         : level,
        "drift_score"         : round(score, 4),
        "ks_stat"             : round(ks, 4),
        "psi"                 : round(psi, 4),
        "mae"                 : round(mae, 4),
        "recommended_action"  : action_key,
        "action_info"         : ACTION_EXPLAIN.get(action_key, {}),
        "decision_reasoning"  : decision_reasoning,
        "plain_english"       : plain_english,
        "drift_summary"       : drift_summary,
        "threshold_breakdown" : threshold_breakdown,
        "feature_contributions": contributions,
        "drift_contrib_chart" : drift_contrib_chart,
        "shap_top_features"   : top_shap or [],
        "shap_chart"          : shap_chart,
        "beeswarm_chart"      : beeswarm_chart,
    }


# ── Logbook ──────────────────────────────────────────────
def save_to_logbook(entry):
    os.makedirs(REPORT_DIR, exist_ok=True)
    logs = []
    if os.path.exists(LOGBOOK):
        try:
            with open(LOGBOOK, "r", encoding="utf-8") as f:
                logs = json.load(f)
        except Exception:
            logs = []
    logs.append(entry)
    with open(LOGBOOK, "w", encoding="utf-8") as f:
        json.dump(logs, f, indent=2, default=str)
    logger.info(f"📝 Logbook entry saved → {entry.get('month', 'unknown')}")


def load_logbook():
    if not os.path.exists(LOGBOOK):
        return []
    try:
        with open(LOGBOOK, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []


def build_logbook_entry(month_label, drift_result, action_taken,
                        metrics_before, metrics_after, explanation):
    level = drift_result.get("level", "unknown")
    contributions = explanation.get("feature_contributions", [])[:5]

    # Build human-readable narrative
    action_info = ACTION_EXPLAIN.get(action_taken, {})
    narrative_parts = [
        f"📅 Month: {month_label}",
        f"📊 Drift Level: {level.upper()} (score: {drift_result.get('drift_score', 'N/A')})",
        f"",
        f"🔍 What happened: {explanation.get('drift_summary', 'N/A')}",
        f"",
        f"⚡ Action taken: {action_info.get('label', action_taken)}",
        f"   Why: {action_info.get('why', 'N/A')}",
        f"   What it does: {action_info.get('what', 'N/A')}",
    ]

    if metrics_before and metrics_after:
        mae_b = metrics_before.get("MAE", "N/A")
        mae_a = metrics_after.get("MAE", "N/A")
        rmse_b = metrics_before.get("RMSE", "N/A")
        rmse_a = metrics_after.get("RMSE", "N/A")
        narrative_parts.append(f"")
        narrative_parts.append(f"📈 Performance change:")
        narrative_parts.append(f"   MAE:  {mae_b} → {mae_a}")
        narrative_parts.append(f"   RMSE: {rmse_b} → {rmse_a}")

    if contributions:
        narrative_parts.append(f"")
        narrative_parts.append(f"🔥 Top drift features:")
        for c in contributions:
            narrative_parts.append(
                f"   • {c['desc']} — PSI={c['psi']:.3f} ({c['severity']}) — {c.get('contribution_pct', 0)}% of total drift"
            )

    narrative = "\n".join(narrative_parts)

    return {
        "id"           : datetime.now().strftime("%Y%m%d_%H%M%S"),
        "timestamp"    : datetime.now().strftime("%d %b %Y %H:%M"),
        "month"        : month_label,
        "drift_level"  : level.upper(),
        "drift_score"  : drift_result.get("drift_score"),
        "ks_stat"      : drift_result.get("ks_stat"),
        "psi"          : drift_result.get("psi"),
        "mae_before"   : metrics_before.get("MAE") if metrics_before else None,
        "rmse_before"  : metrics_before.get("RMSE") if metrics_before else None,
        "mae_after"    : metrics_after.get("MAE") if metrics_after else None,
        "rmse_after"   : metrics_after.get("RMSE") if metrics_after else None,
        "action_taken" : action_taken,
        "action_label" : action_info.get("label", action_taken),
        "action_why"   : action_info.get("why", ""),
        "action_what"  : action_info.get("what", ""),
        "action_detail": action_info.get("detail", ""),
        "decision_reasoning": explanation.get("decision_reasoning", ""),
        "plain_english": explanation.get("plain_english", ""),
        "drift_summary": explanation.get("drift_summary", ""),
        "narrative"    : narrative,
        "top_drift_features": [
            {"feature": c["feature"], "desc": c["desc"],
             "psi": c["psi"], "severity": c["severity"],
             "contribution_pct": c.get("contribution_pct", 0),
             "impact": c.get("impact", ""),
             "suggestion": c.get("suggestion", "")}
            for c in contributions
        ],
    }
