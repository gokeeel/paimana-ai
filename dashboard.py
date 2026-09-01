#!/usr/bin/env python3
"""
dashboard.py — PAIMANA-AI Streamlit monitoring dashboard (SIH outcome g).

Reads only pre-computed files (panel.csv, risk_scores.csv, risk_history.csv,
risk_summary.json, shap_global.csv, shap_top50.csv, model_comparison.csv) — no
model inference happens here. Run score_projects.py and explain_risks.py first,
then: streamlit run dashboard.py

Tab structure and fixes follow FRONTEND_CHANGES.md (UX audit against
PAIMANA-AI_PRD_corrected.md). The Module H / LLM Assistant tab from that audit
is intentionally NOT built here — it required a cloud API (Groq), which
conflicts with this project's local-only constraint; skipped by explicit choice.
"""

import json
import os

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from build_panel import mi_to_str  # reuse existing month-index -> date formatter
from score_projects import risk_tier  # single source of truth for tier thresholds
from feature_labels import human_label, field_source, combined_importance

DATA_DIR = "model_data"
# Palette adapted from the GOV.UK Design System (design-system.service.gov.uk/styles/colour) —
# flat, high-contrast, no gradients. Background/text are always set as an explicit pair below
# so nothing depends on the viewer's light/dark preference (that mismatch was the earlier bug).
TEXT = "#0b0c0c"
BLUE = "#1d70b8"        # brand / primary
ORANGE = "#f47738"      # secondary accent
SURFACE = "#f3f2f1"
RED = "#ca3535"
GREEN = "#0f7a52"
TIER_COLORS = {"Red": RED, "Amber": ORANGE, "Green": GREEN}
TIER_TINTS = {"Red": "#fcf5f5", "Amber": "#fef8f5", "Green": "#f3f8f6"}
TIER_ORDER = ["Red", "Amber", "Green"]
ALERT_ACTIONS = {
    "Rapidly Deteriorating": "Escalate to ministry PMU — review the cause of this month's risk jump.",
    "Newly At Risk": "Flag for closer monitoring — risk score crossed the Amber/Red threshold this month.",
    "Stalled and Overdue": "Site inspection recommended — high slip probability, low progress, already past original DoC.",
}


st.set_page_config(page_title="PAIMANA-AI", layout="wide", page_icon="🚧")


REQUIRED_FILES = {
    "panel.csv": "build_panel.py",
    "risk_scores.csv": "score_projects.py",
    "risk_summary.json": "score_projects.py",
    "shap_global.csv": "explain_risks.py",
    "shap_top50.csv": "explain_risks.py",
}


@st.cache_data
def load_data():
    missing = [(f, script) for f, script in REQUIRED_FILES.items()
               if not os.path.exists(f"{DATA_DIR}/{f}")]
    if missing:
        return None, missing

    panel = pd.read_csv(f"{DATA_DIR}/panel.csv", low_memory=False, dtype={"uid": str})
    risk = pd.read_csv(f"{DATA_DIR}/risk_scores.csv", dtype={"uid": str})
    with open(f"{DATA_DIR}/risk_summary.json", encoding="utf-8") as f:
        summary = json.load(f)
    shap_global = pd.read_csv(f"{DATA_DIR}/shap_global.csv")
    shap_top50 = pd.read_csv(f"{DATA_DIR}/shap_top50.csv", dtype={"uid": str})
    history_path = f"{DATA_DIR}/risk_history.csv"
    history = pd.read_csv(history_path, dtype={"uid": str}) if os.path.exists(history_path) else pd.DataFrame()
    comp_path = f"{DATA_DIR}/model_comparison.csv"
    model_comp = pd.read_csv(comp_path) if os.path.exists(comp_path) else pd.DataFrame()
    return (panel, risk, summary, shap_global, shap_top50, history, model_comp), None


loaded, missing = load_data()
if missing:
    st.error("The dashboard can't start — required data files are missing:")
    for fname, script in missing:
        st.markdown(f"- `{DATA_DIR}/{fname}` — run `python {script}` to generate it")
    st.stop()
panel, risk, summary, shap_global, shap_top50, history, model_comp = loaded

st.markdown(
    f"""
    <div style="background:{BLUE}; color:#ffffff; padding:20px 24px; margin:-1rem -1rem 0 -1rem;
                border-bottom:4px solid {TEXT};">
      <div style="font-size:1.7rem; font-weight:700;">PAIMANA-AI</div>
      <div style="font-size:1rem;">Predictive Analytics &amp; Early Warning System for Infrastructure
        Monitoring &nbsp;|&nbsp; SIH26103</div>
    </div>
    """,
    unsafe_allow_html=True,
)

# ───────────────────────────────────────────── F7: persistent report-month banner
# GOV.UK "notification banner" pattern: neutral surface + solid colour left border + explicit
# dark text — background and text colour are always set together so contrast can't break.
st.markdown(
    f"""
    <div style="background:{SURFACE}; color:{TEXT}; border-left:6px solid {BLUE};
                padding:10px 16px; margin:16px 0;">
      📅 Showing data for <strong>{summary['report_month']}</strong> &nbsp;|&nbsp;
      {summary['total_projects']:,} projects &nbsp;|&nbsp;
      {summary['red'] + summary['amber']:,} at Red/Amber risk
    </div>
    """,
    unsafe_allow_html=True,
)

# ───────────────────────────────────────────── F2: sidebar filters (apply to every tab)
FILTER_KEYS = ["sel_ministry", "sel_sector", "sel_state", "sel_tier", "cost_range"]

with st.sidebar:
    st.info(f"📅 Data as of: **{summary['report_month']}**")
    st.caption("Run score_projects.py to refresh with new monthly data.")

    hdr_col, reset_col = st.columns([2, 1])
    hdr_col.header("Filters")
    if reset_col.button("↺ Reset"):
        for k in FILTER_KEYS:
            st.session_state.pop(k, None)
        st.rerun()

    sel_ministry = st.multiselect("Ministry", sorted(risk.ministry.dropna().unique()), key="sel_ministry")
    sel_sector = st.multiselect("Sector", sorted(risk.sector.dropna().unique()), key="sel_sector")
    sel_state = st.multiselect("State", sorted(risk.state.dropna().unique()), key="sel_state")
    sel_tier = st.multiselect("Risk Band", TIER_ORDER, default=TIER_ORDER, key="sel_tier")
    cmin, cmax = float(risk.original_cost.min()), float(risk.original_cost.max())
    cost_range = st.slider("Original Cost (₹ Cr)", cmin, cmax, (cmin, cmax), key="cost_range")

    mask = pd.Series(True, index=risk.index)
    if sel_ministry:
        mask &= risk.ministry.isin(sel_ministry)
    if sel_sector:
        mask &= risk.sector.isin(sel_sector)
    if sel_state:
        mask &= risk.state.isin(sel_state)
    if sel_tier:
        mask &= risk.risk_tier.isin(sel_tier)
    mask &= risk.original_cost.between(*cost_range)
    filtered_risk = risk[mask]

    st.caption(f"{len(filtered_risk):,} of {len(risk):,} projects match filters")
    st.download_button("⬇ Export Filtered List (CSV)", filtered_risk.to_csv(index=False).encode("utf-8"),
                        "paimana_filtered_projects.csv", "text/csv")
    if os.path.exists(f"{DATA_DIR}/risk_report.pdf"):
        with open(f"{DATA_DIR}/risk_report.pdf", "rb") as f:
            st.download_button("⬇ Monthly Risk Report (PDF)", f.read(), "paimana_risk_report.pdf", "application/pdf")
        st.caption("Portfolio-wide summary — not affected by the filters above.")
    else:
        st.caption("Run generate_report.py to enable the PDF report download.")

tab1, tab2, tab3, tab4, tab5 = st.tabs(
    ["📊 Portfolio Overview", "🔍 Project Details", "📈 Sector & Agency Benchmarks",
     "🚨 Early Warning Alerts", "🔬 Model & Field Analysis"]
)

# ───────────────────────────────────────────── Tab 1: Portfolio Overview
with tab1:
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total Projects", f"{len(filtered_risk):,}")
    c2.metric("Total Sanctioned Cost", f"₹{filtered_risk['original_cost'].sum() / 1e5:.2f} Lakh Cr")
    c3.metric("🔴 Red", f"{(filtered_risk.risk_tier == 'Red').sum():,}")
    c4.metric("🟠 Amber", f"{(filtered_risk.risk_tier == 'Amber').sum():,}")

    col1, col2 = st.columns(2)
    with col1:
        tier_df = filtered_risk.risk_tier.value_counts().reindex(TIER_ORDER, fill_value=0).reset_index()
        tier_df.columns = ["tier", "count"]
        fig = px.bar(tier_df, x="tier", y="count", color="tier", color_discrete_map=TIER_COLORS,
                     title="Risk Band Distribution", category_orders={"tier": TIER_ORDER})
        fig.update_layout(showlegend=False)
        st.plotly_chart(fig, width="stretch")
    with col2:
        top_min = (filtered_risk[filtered_risk.risk_tier.isin(["Red", "Amber"])]
                   .ministry.value_counts().nlargest(10).reset_index())
        top_min.columns = ["ministry", "count"]
        fig2 = px.bar(top_min, x="count", y="ministry", orientation="h", color="count",
                      color_continuous_scale="Reds", title="Top 10 Ministries by Red/Amber Projects")
        fig2.update_layout(yaxis={"categoryorder": "total ascending"}, coloraxis_showscale=False)
        st.plotly_chart(fig2, width="stretch")

    if not history.empty:
        prev_month = sorted(history.report_month.unique())[-2] if history.report_month.nunique() > 1 else None
        if prev_month:
            prev_scores = history[history.report_month == prev_month][["uid", "risk_score"]]
            prev_scores = prev_scores.assign(prev_tier=prev_scores.risk_score.apply(risk_tier))
            merged = filtered_risk[["uid", "risk_tier"]].merge(
                prev_scores[["uid", "prev_tier"]], on="uid", how="inner")
            worsened = merged[
                ((merged.prev_tier == "Green") & (merged.risk_tier.isin(["Amber", "Red"])))
                | ((merged.prev_tier == "Amber") & (merged.risk_tier == "Red"))
            ]
            st.metric(f"Moved to a worse risk band since {prev_month}", f"{len(worsened):,}")

    st.subheader("Top 20 Riskiest Projects")
    top20 = filtered_risk.nlargest(20, "risk_score")[
        ["project_name", "risk_score", "risk_tier", "slip_prob", "cost_prob", "ministry", "state"]]
    st.dataframe(top20, width="stretch", hide_index=True)
    st.download_button("⬇ Export Top 20 (CSV)", top20.to_csv(index=False).encode("utf-8"),
                        "top20_riskiest.csv", "text/csv")

# ───────────────────────────────────────────── Tab 2: Project Details
with tab2:
    st.caption(f"Showing the {len(filtered_risk):,} projects matching the sidebar filters. "
               "Narrow further within that set:")
    f_tier = st.selectbox("Risk Band", ["All"] + TIER_ORDER, key="tab2_tier")

    subset = filtered_risk.copy()
    if f_tier != "All":
        subset = subset[subset.risk_tier == f_tier]
    subset = subset.sort_values("risk_score", ascending=False)

    if subset.empty:
        st.warning("No projects match the current filters — adjust them in the sidebar.")
    else:
        labeled = subset.assign(label=subset.project_name.fillna("(unnamed)") +
                                 "  [Score: " + subset.risk_score.round(1).astype(str) + "]")
        sel = st.selectbox("Select a project", labeled.label.tolist())
        row = labeled[labeled.label == sel].iloc[0]

        c1, c2, c3 = st.columns(3)
        with c1:
            st.markdown("**Project Info**")
            st.write(f"Agency: {row.agency}")
            st.write(f"Ministry: {row.ministry}")
            st.write(f"Sector: {row.sector}")
            st.write(f"State: {row.state}")
        with c2:
            st.markdown("**Cost & Progress**")
            st.write(f"Original Cost: ₹{row.original_cost:,.1f} Cr")
            st.write(f"Latest Cost: ₹{row.latest_cost:,.1f} Cr")
            st.write(f"Physical Progress: {row.physical_progress:.1f}%")
        with c3:
            fig_gauge = go.Figure(go.Indicator(
                mode="gauge+number", value=row.risk_score,
                title={"text": f"Risk Score ({row.risk_tier})"},
                gauge={"axis": {"range": [0, 100]},
                       "bar": {"color": TIER_COLORS[row.risk_tier]},
                       "steps": [{"range": [0, 40], "color": TIER_TINTS["Green"]},
                                 {"range": [40, 70], "color": TIER_TINTS["Amber"]},
                                 {"range": [70, 100], "color": TIER_TINTS["Red"]}]},
            ))
            fig_gauge.update_layout(height=220, margin=dict(l=10, r=10, t=40, b=10))
            st.plotly_chart(fig_gauge, width="stretch")

        c4, c5 = st.columns(2)
        c4.metric("Predicted New Slippage (12mo)", f"{row.slip_months_pred:.1f} months")
        c5.metric("Predicted Cost Escalation (p50–p90)", f"{row.cost_q50_pred:.1f}% – {row.cost_q90_pred:.1f}%")

        st.subheader("Why is this project flagged?")
        drivers = shap_top50[shap_top50.uid == row.uid]
        if len(drivers):
            d = drivers.iloc[0]
            feats = [human_label(d[f"driver_{i}_feature"]) for i in range(1, 6)]
            vals = [d[f"driver_{i}_shap"] for i in range(1, 6)]
            fig = go.Figure(go.Bar(x=vals, y=feats, orientation="h",
                                    marker_color=[ORANGE if v > 0 else BLUE for v in vals]))
            fig.update_layout(title="Top 5 reasons this project is flagged",
                              xaxis_title="Contribution to risk score", yaxis={"categoryorder": "total ascending"})
            st.plotly_chart(fig, width="stretch")
        else:
            st.info("Project-level explanation not computed for this project (only the top-50 riskiest "
                     "projects get one each run). Showing the overall top drivers across all projects instead:")
            g = combined_importance(shap_global).sort_values("combined", ascending=False).head(5)
            for _, r in g.iterrows():
                st.write(f"- {human_label(r.feature)}")

        st.subheader("Risk Score Trend")
        if not history.empty:
            proj_hist = history[history.uid == row.uid].sort_values("report_month").tail(6)
            if len(proj_hist) > 1:
                fig_trend = px.line(proj_hist, x="report_month", y="risk_score", markers=True,
                                    title="Risk score, last 6 reports")
                fig_trend.add_hline(y=40, line_dash="dot", line_color=TIER_COLORS["Amber"])
                fig_trend.add_hline(y=70, line_dash="dot", line_color=TIER_COLORS["Red"])
                st.plotly_chart(fig_trend, width="stretch")
            else:
                st.caption("Trend not available — this project has only one scored report so far.")

        st.subheader("Progress: Physical vs. Financial")
        proj_panel = panel[panel.uid == row.uid].sort_values("report_mi")
        if len(proj_panel) > 1:
            fig_prog = px.line(proj_panel, x="report_month", y=["physical_progress", "financial_progress_pct"],
                               markers=True, title="Physical vs. financial progress over time")
            st.plotly_chart(fig_prog, width="stretch")
        else:
            st.caption("Progress trend not available — only one monthly report on record for this project.")

        st.subheader("Project Timeline")
        hist_rows = panel[panel.uid == row.uid].sort_values("report_mi")
        if len(hist_rows):
            last = hist_rows.iloc[-1]
            orig, rev, ant = last.orig_doc_mi, last.rev_doc_mi, last.anticipated_doc_mi
            tl = pd.DataFrame({
                "milestone": ["Original DoC", "Revised DoC", "Current Anticipated DoC"],
                "date": [mi_to_str(pd.Series([orig])).iloc[0],
                         mi_to_str(pd.Series([rev])).iloc[0] if pd.notna(rev) else "—",
                         mi_to_str(pd.Series([ant])).iloc[0] if pd.notna(ant) else "—"],
                "slip_months": [0, (rev - orig) if pd.notna(rev) else 0, (ant - orig) if pd.notna(ant) else 0],
            })
            fig3 = px.bar(tl, x="slip_months", y="milestone", orientation="h", text="date",
                          color_discrete_sequence=[ORANGE], title="Slippage relative to Original DoC (months)")
            st.plotly_chart(fig3, width="stretch")
        else:
            st.caption("Timeline history not available — this project may have been added in the current month only.")

# ───────────────────────────────────────────── Tab 3: Sector & Agency Benchmarks
with tab3:
    st.caption(f"Benchmarks computed over the {len(filtered_risk):,} projects matching the sidebar filters.")
    dim = st.selectbox("Group by", ["ministry", "sector", "state"])
    filtered_panel = panel[panel.uid.isin(filtered_risk.uid)]
    latest_panel = filtered_panel[filtered_panel.report_month == filtered_panel.report_month.max()]
    g = latest_panel.groupby(dim).agg(
        median_cost_overrun_pct=("cost_revision_to_date_pct", "median"),
        median_time_slip_m=("doc_slip_to_date_m", "median"),
        pct_past_orig_doc=("is_past_orig_doc", "mean"),
        n_projects=("uid", "nunique"),
    ).reset_index()
    g = g[g.n_projects >= 3]  # drop tiny groups, unstable medians

    col1, col2 = st.columns(2)
    with col1:
        fig = px.bar(g.sort_values("median_cost_overrun_pct", ascending=False).head(15),
                     x=dim, y="median_cost_overrun_pct", title=f"Median Cost Overrun % by {dim}",
                     color_discrete_sequence=[BLUE])
        st.plotly_chart(fig, width="stretch")
    with col2:
        fig2 = px.bar(g.sort_values("median_time_slip_m", ascending=False).head(15),
                      x=dim, y="median_time_slip_m", title=f"Median Time Slip (months) by {dim}",
                      color_discrete_sequence=[ORANGE])
        st.plotly_chart(fig2, width="stretch")

    fig3 = px.bar(g.sort_values("pct_past_orig_doc", ascending=False).head(15),
                  x=dim, y="pct_past_orig_doc", title=f"Share of Projects Past Original DoC by {dim}")
    st.plotly_chart(fig3, width="stretch")

    st.subheader("Trend Over Time")
    trend = filtered_panel.groupby([dim, "report_month"]).agg(
        median_cost_overrun_pct=("cost_revision_to_date_pct", "median"),
        n_projects=("uid", "nunique"),
    ).reset_index()
    trend = trend[trend.n_projects >= 3]
    top_groups = g.nlargest(8, "n_projects")[dim].tolist()
    trend_top = trend[trend[dim].isin(top_groups)]
    fig_trend = px.line(trend_top, x="report_month", y="median_cost_overrun_pct", color=dim, markers=True,
                        title=f"Cost Overrun Trend Over Time — Top 8 by {dim}")
    st.plotly_chart(fig_trend, width="stretch")

    st.subheader("Comparison Table")
    comp_table = g.sort_values("median_cost_overrun_pct", ascending=False)
    st.dataframe(comp_table, width="stretch", hide_index=True)
    st.download_button("⬇ Export Comparison Table (CSV)", comp_table.to_csv(index=False).encode("utf-8"),
                        f"benchmark_by_{dim}.csv", "text/csv")

    st.subheader("Agency Scorecard")
    st.caption("Minimum 5 projects per agency to avoid unfair ranking of agencies with very few projects.")
    ag = latest_panel.groupby("agency").agg(
        n_projects=("uid", "nunique"),
        pct_on_budget=("cost_revision_to_date_pct", lambda s: (s < 10).mean() * 100),
        pct_on_time=("is_past_orig_doc", lambda s: (s == 0).mean() * 100),
        median_cost_overrun_pct=("cost_revision_to_date_pct", "median"),
        median_time_slip_m=("doc_slip_to_date_m", "median"),
    ).reset_index()
    ag = ag[ag.n_projects >= 5]
    ag["delivery_score"] = (ag.pct_on_budget + ag.pct_on_time) / 2
    ag["score_grade"] = pd.cut(ag.delivery_score, [-1, 25, 50, 75, 101], labels=["D", "C", "B", "A"])
    ag = ag.sort_values("delivery_score", ascending=False)
    st.dataframe(ag, width="stretch", hide_index=True)
    st.download_button("⬇ Export Agency Scorecard (CSV)", ag.to_csv(index=False).encode("utf-8"),
                        "agency_scorecard.csv", "text/csv")

# ───────────────────────────────────────────── Tab 4: Early Warning Alerts
with tab4:
    alert_df = filtered_risk[filtered_risk.alert_type.notna()].copy()
    alert_df["recommended_action"] = alert_df.alert_type.map(ALERT_ACTIONS)

    col1, col2, col3 = st.columns(3)
    col1.metric("🔴 Rapidly Deteriorating", int((alert_df.alert_type == "Rapidly Deteriorating").sum()))
    col2.metric("🟠 Newly At Risk", int((alert_df.alert_type == "Newly At Risk").sum()))
    col3.metric("🟡 Stalled and Overdue", int((alert_df.alert_type == "Stalled and Overdue").sum()))

    sel_type = st.selectbox("Alert Type", ["All"] + list(ALERT_ACTIONS.keys()))
    view = alert_df if sel_type == "All" else alert_df[alert_df.alert_type == sel_type]
    view = view.sort_values("risk_score", ascending=False)

    st.dataframe(
        view[["project_name", "ministry", "sector", "risk_score", "risk_score_delta",
              "alert_type", "recommended_action"]],
        width="stretch", hide_index=True,
    )
    st.download_button("⬇ Export Alerts (CSV)", view.to_csv(index=False).encode("utf-8"),
                        "paimana_alerts.csv", "text/csv")

# ───────────────────────────────────────────── Tab 5: Model & Field Analysis
with tab5:
    if not model_comp.empty:
        st.subheader("Statistical Baseline vs. ML Model Performance")
        st.caption("Evaluated on 5-fold GroupKFold cross-validation (project-level). "
                   "See temporal_eval.txt for a strict future-holdout evaluation.")
        st.dataframe(model_comp, width="stretch", hide_index=True)

        def _auc(target_label, model_label):
            row = model_comp[(model_comp.target == target_label) & (model_comp.model == model_label)]
            return float(row.roc_auc.iloc[0]) if len(row) and row.roc_auc.iloc[0] != "-" else None

        lines = []
        for target_label, name in [("time: y_slippage_flag", "time-slippage"),
                                    ("cost: y_cost_overrun_flag", "cost-overrun")]:
            model_auc = _auc(target_label, "model")
            base_row = model_comp[(model_comp.target == target_label) & model_comp.model.str.startswith("baseline")]
            base_auc = float(base_row.roc_auc.iloc[0]) if len(base_row) else None
            if model_auc and base_auc:
                gain = (model_auc - base_auc) / base_auc * 100
                lines.append(f"- **{name.capitalize()}**: ROC-AUC **{model_auc:.3f}** vs. baseline **{base_auc:.3f}** "
                            f"— a **+{gain:.0f}%** relative improvement in ranking ability.")
        if lines:
            st.markdown("**Key finding:**\n\n" + "\n".join(lines) +
                        "\n\nThis directly addresses Research Dimension B from the hackathon problem statement.")
    else:
        st.info("Run train_models.py to populate model_comparison.csv.")

    st.subheader("Global SHAP Feature Importance")
    st.caption("Computed on a representative sample (top-50 riskiest + random projects), not the full panel — "
               "see explain_risks.py for why.")
    shap_labeled = shap_global.assign(
        feature_label=shap_global.feature.apply(human_label),
        field_source=shap_global.feature.apply(field_source),
    )
    col1, col2 = st.columns(2)
    with col1:
        g1 = shap_labeled.sort_values("mean_abs_shap_time", ascending=False).head(15)
        fig = px.bar(g1, x="mean_abs_shap_time", y="feature_label", orientation="h", color="field_source",
                     color_discrete_map={"CUF Field": BLUE, "Engineered Feature": ORANGE},
                     title="Time Model — Top Drivers")
        fig.update_layout(yaxis={"categoryorder": "total ascending"})
        st.plotly_chart(fig, width="stretch")
    with col2:
        g2 = shap_labeled.sort_values("mean_abs_shap_cost", ascending=False).head(15)
        fig2 = px.bar(g2, x="mean_abs_shap_cost", y="feature_label", orientation="h", color="field_source",
                      color_discrete_map={"CUF Field": BLUE, "Engineered Feature": ORANGE},
                      title="Cost Model — Top Drivers")
        fig2.update_layout(yaxis={"categoryorder": "total ascending"})
        st.plotly_chart(fig2, width="stretch")

    combined = combined_importance(shap_labeled).sort_values("combined", ascending=False)
    top5 = combined.head(5).feature_label.tolist()
    share = combined.head(5).combined.sum() / combined.combined.sum() * 100 if combined.combined.sum() else 0

    st.markdown(
        f"""
        **~{share:.0f}%** of the models' predictive signal (mean |SHAP|) comes from the top 5 fields:
        **{", ".join(top5)}**.

        The current monitoring framework (CUF) already captures the most predictive signals available.
        Fields that would likely improve prediction further but are **not** currently in the CUF:
        delay-reason codes, milestone-level completion data, and land-acquisition status.

        See `feature_summary.txt` for the full feature list and `temporal_eval.txt` for the strict
        future-holdout evaluation (recall, base rate, lead time, sector breakdown).
        """
    )
