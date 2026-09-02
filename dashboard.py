#!/usr/bin/env python3
"""
dashboard.py — PAIMANA-AI Streamlit monitoring dashboard (SIH outcome g).

Reads pre-computed files (panel.csv, risk_scores.csv, risk_history.csv,
risk_summary.json, shap_global.csv, shap_top50.csv, shap_sample.csv,
model_comparison.csv, risk_archetypes.csv) — no model inference at page load.
Run score_projects.py, explain_risks.py, cluster_archetypes.py first, then:
streamlit run dashboard.py

One deliberate exception to "no model inference": the What-if lever in
Project Details loads the 2 classifiers (cached, loaded once) and reruns
them ONLY when you move a what-if slider — that's inherently live by design,
since you can't precompute every hypothetical input.
"""

import io
import json
import os

import joblib
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from build_panel import mi_to_str  # reuse existing month-index -> date formatter
from score_projects import risk_tier  # single source of truth for tier thresholds
from feature_labels import human_label, field_source, combined_importance, build_X

DATA_DIR = "model_data"
TEXT = "#0b0c0c"
SURFACE = "#f3f2f1"
BLUE = "#1976D2"     # CUF fields / informational
ORANGE = "#FB8C00"   # Amber / Newly At Risk / Engineered features
YELLOW = "#FBC02D"   # Stalled and Overdue
RED = "#E24B4A"       # Red / Rapidly Deteriorating
GREEN = "#43A047"     # On track
TIER_COLORS = {"Red": RED, "Amber": ORANGE, "Green": GREEN}
TIER_TINTS = {"Red": "#fcebea", "Amber": "#fff3e0", "Green": "#e8f5e9"}
TIER_BADGE = {"Red": "🔴 Red", "Amber": "🟠 Amber", "Green": "🟢 Green"}
TIER_ORDER = ["Red", "Amber", "Green"]
ALERT_BADGE = {
    "Rapidly Deteriorating": "🔴 Rapidly deteriorating",
    "Newly At Risk": "🟠 Newly at risk",
    "Stalled and Overdue": "🟡 Stalled and overdue",
}
ALERT_ACTIONS = {
    "Rapidly Deteriorating": "Escalate to ministry PMU — review the cause of this month's risk jump.",
    "Newly At Risk": "Flag for closer monitoring — risk score crossed the Amber/Red threshold this month.",
    "Stalled and Overdue": "Site inspection recommended — high slip probability, low progress, already past original DoC.",
}

# Display-column labels (distinct from feature_labels.FEATURE_LABELS, which covers
# SHAP model-input names like elapsed_ratio -- this covers dashboard/table columns).
COLUMN_LABELS = {
    "risk_score": "Risk score", "risk_tier": "Risk tier", "slip_prob": "Slippage probability",
    "cost_prob": "Cost escalation probability", "slip_months_pred": "Predicted slippage (months)",
    "cost_q50_pred": "Cost escalation (p50)", "cost_q90_pred": "Cost escalation (p90)",
    "risk_score_delta": "Risk score change", "project_name": "Project", "ministry": "Ministry",
    "sector": "Sector", "state": "State", "agency": "Agency",
    "original_cost": "Sanctioned cost (₹ Cr)", "latest_cost": "Latest revised cost (₹ Cr)",
    "physical_progress": "Physical progress (%)", "financial_progress_pct": "Financial progress (%)",
    "expenditure": "Expenditure (₹ Cr)", "median_cost_overrun_pct": "Median cost overrun (%)",
    "median_time_slip_m": "Median time slip (months)", "pct_past_orig_doc": "Past original completion (%)",
    "n_projects": "Projects monitored", "pct_on_budget": "On budget (%)", "pct_on_time": "On time (%)",
    "delivery_score": "Delivery score", "score_grade": "Grade", "alert_type": "Alert type",
}

CONFIG_STATIC = {"displayModeBar": False}

# Sector categories + colours matching the official PAIMANA portal (ipm.mospi.gov.in) —
# verified against reference screenshots, not guessed. Sectors outside this named set are
# bucketed as "Others", same as the portal's own donut chart does.
SECTOR_COLORS = {
    "Roads & Highways": "#1a237e", "Railways": "#2e7d32", "Coal": "#f9a825",
    "Oil & Gas": "#e65100", "Transmission & Distribution": "#4527a0",
    "Electricity Generation": "#283593", "Water Resources": "#d81b60",
    "Healthcare": "#f48fb1", "Education": "#f8bbd0", "Urban Public Transport": "#b3e5fc",
}
OTHERS_COLOR = "#80cbc4"


def bucket_sector(s):
    return s if s in SECTOR_COLORS else "Others"


def nested_donut(labels, counts, costs):
    """Two-ring donut matching the portal's 'Outer: Count :: Inner: Cost' chart."""
    colors = [SECTOR_COLORS.get(l, OTHERS_COLOR) for l in labels]
    fig = go.Figure()
    fig.add_trace(go.Pie(labels=labels, values=counts, sort=False, hole=0.72,
                         domain={"x": [0.06, 0.94], "y": [0.06, 0.94]},
                         marker=dict(colors=colors, line=dict(color="white", width=1)),
                         textinfo="percent", textfont_size=10,
                         hovertemplate="<b>%{label}</b><br>%{value} projects (%{percent})<extra></extra>"))
    fig.add_trace(go.Pie(labels=labels, values=costs, sort=False, hole=0.35,
                         domain={"x": [0.27, 0.73], "y": [0.27, 0.73]},
                         marker=dict(colors=colors, line=dict(color="white", width=1)),
                         textinfo="none",
                         hovertemplate="<b>%{label}</b><br>₹%{value:,.0f} Cr (%{percent})<extra></extra>"))
    fig.update_layout(showlegend=False, height=360, margin=dict(t=20, b=10, l=10, r=10),
                      annotations=[dict(text="Outer: Count<br>Inner: Cost", x=0.5, y=0.5,
                                        font=dict(size=10, color="#666"), showarrow=False)])
    return fig


def color_legend(color_map, others_color):
    items = list(color_map.items()) + [("Others", others_color)]
    swatches = "".join(
        f"<div style='display:flex;align-items:center;gap:6px;'>"
        f"<span style='width:12px;height:12px;background:{c};display:inline-block;"
        f"border-radius:2px;'></span>{l}</div>"
        for l, c in items
    )
    st.markdown(f"<div style='display:flex;flex-wrap:wrap;gap:6px 20px;font-size:12px;"
               f"margin-top:6px;color:{TEXT};'>{swatches}</div>", unsafe_allow_html=True)


def panel_toggle(title, key):
    c1, c2 = st.columns([3, 1])
    c1.markdown(f"#### {title}")
    return c2.radio("view", ["Charts", "Data"], horizontal=True, key=f"mode_{key}", label_visibility="collapsed")


def export_buttons(df, stem):
    c1, c2, _ = st.columns([1, 1, 5])
    c1.download_button("⬇ CSV", df.to_csv(index=False).encode("utf-8"), f"{stem}.csv", "text/csv", key=f"csv_{stem}")
    buf = io.BytesIO()
    df.to_excel(buf, index=False, engine="openpyxl")
    c2.download_button("⬇ Excel", buf.getvalue(), f"{stem}.xlsx",
                       "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", key=f"xlsx_{stem}")


def metric_card(icon, label, value, bg_color):
    st.markdown(f"""
    <div style="background:{bg_color}; border-radius:12px; padding:18px 22px;
                display:flex; align-items:center; gap:14px; height:100px;">
        <div style="font-size:32px;">{icon}</div>
        <div>
            <div style="font-size:12px; color:#333; opacity:0.75; font-weight:600; margin-bottom:2px;">{label}</div>
            <div style="font-size:24px; font-weight:700; color:#1a1a2e;">{value}</div>
        </div>
    </div>
    """, unsafe_allow_html=True)


def fmt_score(x):
    return "—" if pd.isna(x) else f"{int(round(x))}"


def fmt_prob(x):
    return "—" if pd.isna(x) else f"{x:.2f}"


def fmt_pct1(x):
    return "—" if pd.isna(x) else f"{x:.1f}%"


def fmt_months(x):
    return "—" if pd.isna(x) else f"{int(round(x))}"


def fmt_delta(x):
    return "—" if pd.isna(x) else f"{x:+.1f}"


def fmt_cr(x):
    return "—" if pd.isna(x) else f"₹{x:,.0f} Cr"


st.set_page_config(page_title="PAIMANA-AI | SIH26103", layout="wide", page_icon="📊",
                   initial_sidebar_state="collapsed")


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
    arch_path = f"{DATA_DIR}/risk_archetypes.csv"
    archetypes = pd.read_csv(arch_path, dtype={"uid": str}) if os.path.exists(arch_path) else pd.DataFrame()
    summ_path = f"{DATA_DIR}/archetype_summary.csv"
    archetype_summary = pd.read_csv(summ_path) if os.path.exists(summ_path) else pd.DataFrame()
    return (panel, risk, summary, shap_global, shap_top50, history, model_comp,
            archetypes, archetype_summary), None


@st.cache_resource
def load_whatif_models():
    # joblib.load executes pickle bytecode; safe here — these files were produced
    # locally by train_models.py in this same pipeline, not from an untrusted source.
    return {
        "slip": joblib.load(f"{DATA_DIR}/model1_slippage_clf.joblib"),
        "cost": joblib.load(f"{DATA_DIR}/model2_cost_clf.joblib"),
    }


loaded, missing = load_data()
if missing:
    st.error("The dashboard can't start — required data files are missing:")
    for fname, script in missing:
        st.markdown(f"- `{DATA_DIR}/{fname}` — run `python {script}` to generate it")
    st.stop()
(panel, risk, summary, shap_global, shap_top50, history, model_comp,
 archetypes, archetype_summary) = loaded

st.markdown(f"""
<div style="background:#1a237e; padding:18px 28px; border-radius:10px; margin-bottom:16px;
            display:flex; align-items:center; justify-content:space-between;">
  <div>
    <div style="color:white; font-size:22px; font-weight:700; letter-spacing:0.5px;">PAIMANA-AI</div>
    <div style="color:#90CAF9; font-size:13px; margin-top:2px;">
      Predictive Analytics &amp; Early Warning System for Infrastructure Monitoring &nbsp;|&nbsp; SIH26103
    </div>
    <div style="color:#90CAF9; font-size:11px; margin-top:4px; opacity:0.85;">
      Built on PAIMANA flash report data. Designed for PAIMANA-CRIP API integration when the portal goes live.
    </div>
  </div>
  <div style="color:#90CAF9; font-size:13px; text-align:right;">
    Data as of <b style="color:white;">{summary['report_month']}</b><br>
    <span style="font-size:11px;">Run score_projects.py to refresh</span>
  </div>
</div>
""", unsafe_allow_html=True)

# ───────────────────────────────────────────── top filter bar (replaces sidebar; layout
# matches the official PAIMANA portal, ipm.mospi.gov.in). Filters apply live as changed
# (an improvement over the portal's click-to-apply) -- "Show Data" is kept for visual
# parity and just forces a rerun.
fc1, fc2, fc3, fc4, fc5, fc6 = st.columns([2, 2, 2, 2, 2, 1])
with fc1:
    f_ministry = st.selectbox("Ministry / Department", ["All"] + sorted(risk.ministry.dropna().unique()),
                              key="f_ministry")
with fc2:
    f_sector = st.selectbox("Sector", ["All"] + sorted(risk.sector.dropna().unique()), key="f_sector")
with fc3:
    f_state = st.selectbox("State / UT", ["All"] + sorted(risk.state.dropna().unique()), key="f_state")
with fc4:
    f_tier = st.selectbox("Risk band", ["All"] + TIER_ORDER, key="f_tier")
with fc5:
    cmin, cmax = float(risk.original_cost.min()), float(risk.original_cost.max())
    cost_range = st.slider("Project Cost (₹ Cr)", cmin, cmax, (cmin, cmax), key="f_cost")
with fc6:
    st.markdown("<div style='height:28px'></div>", unsafe_allow_html=True)
    st.button("Show Data", type="primary", use_container_width=True)
st.markdown("---")

mask = pd.Series(True, index=risk.index)
if f_ministry != "All":
    mask &= risk.ministry == f_ministry
if f_sector != "All":
    mask &= risk.sector == f_sector
if f_state != "All":
    mask &= risk.state == f_state
if f_tier != "All":
    mask &= risk.risk_tier == f_tier
mask &= risk.original_cost.between(*cost_range)
filtered_risk = risk[mask]

with st.sidebar:
    st.caption(f"{len(filtered_risk):,} of {len(risk):,} projects match the top filter bar.")
    st.download_button("⬇ Export Filtered List (CSV)", filtered_risk.to_csv(index=False).encode("utf-8"),
                       "paimana_filtered_projects.csv", "text/csv")
    if os.path.exists(f"{DATA_DIR}/risk_report.pdf"):
        with open(f"{DATA_DIR}/risk_report.pdf", "rb") as f:
            st.download_button("⬇ Monthly Risk Report (PDF)", f.read(), "paimana_risk_report.pdf", "application/pdf")
        st.caption("Portfolio-wide summary — not affected by filters.")
    else:
        st.caption("Run generate_report.py to enable the PDF report download.")

tab1, tab2, tab3, tab4, tab5 = st.tabs(
    ["📊 Portfolio Overview", "🔍 Project Details", "📈 Sector & Agency Benchmarks",
     "🚨 Early Warning Alerts", "🔬 Model & Field Analysis"]
)

# ───────────────────────────────────────────── Tab 1: Portfolio Overview
with tab1:
    var_mask = filtered_risk.risk_tier.isin(["Red", "Amber"])
    value_at_risk = filtered_risk.loc[var_mask, "original_cost"].sum()
    red_amber_n = int(var_mask.sum())

    mc1, mc2, mc3, mc4 = st.columns(4)
    with mc1:
        metric_card("📋", "Projects monitored (in no.)", f"{len(filtered_risk):,}", "#E0F7FA")
    with mc2:
        metric_card("💰", "Sanctioned cost (in cr.)", f"₹{filtered_risk['original_cost'].sum():,.0f}", "#FFF8E1")
    with mc3:
        metric_card("⚠️", "Value at risk — Red+Amber (in cr.)", f"₹{value_at_risk:,.0f}", "#FFEBEE")
    with mc4:
        metric_card("🔺", "Red + Amber projects (in no.)", f"{red_amber_n:,}", "#F1F8E9")
    st.markdown("<br>", unsafe_allow_html=True)

    # Row A: sector-wise nested donut | cost overview funnel
    rowA1, rowA2 = st.columns(2, gap="medium")
    with rowA1:
        with st.container(border=True):
            mode = panel_toggle("Sector-wise Distribution *(project count)*", "sector_dist")
            sec = filtered_risk.assign(sector_g=filtered_risk.sector.apply(bucket_sector)).groupby("sector_g").agg(
                n_projects=("uid", "count"), total_cost=("original_cost", "sum")).reset_index()
            sec = sec.sort_values("n_projects", ascending=False)
            if mode == "Charts":
                st.plotly_chart(nested_donut(sec.sector_g, sec.n_projects, sec.total_cost),
                                width="stretch", config=CONFIG_STATIC)
                color_legend(SECTOR_COLORS, OTHERS_COLOR)
            else:
                sec_table = sec.rename(columns={"sector_g": "Sector", "n_projects": "Projects",
                                                "total_cost": "Cost (₹ Cr)"})
                st.dataframe(sec_table, width="stretch", hide_index=True)
                export_buttons(sec_table, "sector_distribution")
    with rowA2:
        with st.container(border=True):
            mode = panel_toggle("Cost Overview", "cost_overview")
            tot_original = filtered_risk.original_cost.sum()
            tot_revised = filtered_risk.latest_cost.sum()
            tot_expenditure = filtered_risk.get("expenditure", pd.Series(dtype=float)).sum() \
                if "expenditure" in filtered_risk.columns else None
            cost_labels = ["Original sanctioned cost", "Latest revised cost"]
            cost_values = [tot_original, tot_revised]
            if tot_expenditure and tot_expenditure > 0:
                cost_labels.append("Cumulative expenditure")
                cost_values.append(tot_expenditure)
            if mode == "Charts":
                fig_funnel = go.Figure(go.Funnel(
                    y=cost_labels, x=cost_values, textposition="inside",
                    text=[f"₹ {v:,.0f} Cr" for v in cost_values],
                    textfont=dict(color="white", size=13),
                    marker=dict(color=["#1a237e", "#283593", "#3949ab"][:len(cost_values)]),
                    connector=dict(line=dict(color="#c5cae9", width=1)),
                ))
                fig_funnel.update_layout(margin=dict(t=10, b=10, l=10, r=10), height=280)
                st.plotly_chart(fig_funnel, width="stretch", config=CONFIG_STATIC)
            else:
                cost_table = pd.DataFrame({"Metric": cost_labels, "₹ Cr": cost_values})
                st.dataframe(cost_table, width="stretch", hide_index=True)
                export_buttons(cost_table, "cost_overview")

    # Row B: physical progress slab table | risk by ministry
    rowB1, rowB2 = st.columns(2, gap="medium")
    with rowB1:
        with st.container(border=True):
            mode = panel_toggle("Physical Progress *[Project Count]*", "phys_progress")
            bins = list(range(0, 101, 10)) + [101]
            slab_labels = [f"{b}-{b+10}" for b in bins[:-2]] + ["100"]
            pp = filtered_risk.copy()
            pp["progress_slab"] = pd.cut(pp.physical_progress, bins=bins, labels=slab_labels, right=False,
                                         include_lowest=True)
            slab = pp.groupby("progress_slab", observed=True).agg(
                n_projects=("uid", "count"), original_cost=("original_cost", "sum"),
                revised_cost=("latest_cost", "sum"), avg_risk=("risk_score", "mean"),
            ).reindex(slab_labels).reset_index()
            if mode == "Charts":
                fig_slab = px.bar(slab, x="progress_slab", y="n_projects", color_discrete_sequence=["#1a237e"],
                                  labels={"progress_slab": "Physical progress (%)", "n_projects": "Projects"})
                fig_slab.update_layout(margin=dict(t=10, b=10, l=10, r=10), height=280)
                st.plotly_chart(fig_slab, width="stretch", config=CONFIG_STATIC)
            else:
                slab_table = slab.rename(columns={
                    "progress_slab": "Physical progress (%)", "n_projects": "Projects",
                    "original_cost": "Original cost (₹ Cr)", "revised_cost": "Revised cost (₹ Cr)",
                    "avg_risk": "Avg. risk score"})
                slab_table["Avg. risk score"] = slab_table["Avg. risk score"].apply(fmt_score)
                st.dataframe(slab_table, width="stretch", hide_index=True)
                export_buttons(slab_table, "physical_progress")
    with rowB2:
        with st.container(border=True):
            mode = panel_toggle("Risk by Ministry *(Red+Amber count)*", "ministry_risk")
            top_min = (filtered_risk[filtered_risk.risk_tier.isin(["Red", "Amber"])]
                      .ministry.value_counts().nlargest(10).reset_index())
            top_min.columns = ["ministry", "count"]
            if mode == "Charts":
                fig2 = px.bar(top_min.sort_values("count"), x="count", y="ministry", orientation="h",
                             color_discrete_sequence=[RED])
                fig2.update_layout(yaxis_title=None, xaxis_title="Red/Amber projects",
                                   height=max(280, len(top_min) * 28), margin=dict(t=10, l=10))
                st.plotly_chart(fig2, width="stretch", config=CONFIG_STATIC)
            else:
                min_table = top_min.rename(columns={"ministry": "Ministry", "count": "Red/Amber projects"})
                st.dataframe(min_table, width="stretch", hide_index=True)
                export_buttons(min_table, "ministry_risk")

    # Top 20 riskiest, with the risk-band distribution folded into its own Charts view
    with st.container(border=True):
        mode = panel_toggle("Top 20 Riskiest Projects", "top20")
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
                st.caption(f"{len(worsened):,} projects moved to a worse risk band since {prev_month}.")
        if mode == "Charts":
            tier_df = filtered_risk.risk_tier.value_counts().reindex(TIER_ORDER, fill_value=0).reset_index()
            tier_df.columns = ["tier", "count"]
            fig = px.bar(tier_df, x="tier", y="count", color="tier", color_discrete_map=TIER_COLORS,
                        title="Risk Band Distribution", category_orders={"tier": TIER_ORDER})
            fig.update_layout(showlegend=False, height=320, margin=dict(t=40))
            st.plotly_chart(fig, width="stretch", config=CONFIG_STATIC)
        else:
            top20 = filtered_risk.nlargest(20, "risk_score").copy()
            top20["Risk score"] = top20.risk_score.apply(fmt_score)
            top20["Risk tier"] = top20.risk_tier.map(TIER_BADGE)
            top20["Slip prob."] = top20.slip_prob.apply(fmt_prob)
            top20["Cost prob."] = top20.cost_prob.apply(fmt_prob)
            top20_display = top20.rename(columns={"project_name": "Project", "ministry": "Ministry", "state": "State"})
            st.dataframe(
                top20_display[["Project", "Ministry", "Risk score", "Risk tier", "Slip prob.", "Cost prob.", "State"]],
                width="stretch", hide_index=True, height=400,
            )
            export_buttons(top20, "top20_riskiest")

# ───────────────────────────────────────────── Tab 2: Project Details
with tab2:
    st.caption(f"Showing the {len(filtered_risk):,} projects matching the top filter bar. "
               "Narrow further within that set:")
    f_tier = st.selectbox("Risk Band", ["All"] + TIER_ORDER, key="tab2_tier")

    subset = filtered_risk.copy()
    if f_tier != "All":
        subset = subset[subset.risk_tier == f_tier]
    subset = subset.sort_values("risk_score", ascending=False)

    if subset.empty:
        st.warning("No projects match the current filters — adjust the filters above.")
    else:
        labeled = subset.assign(label=subset.project_name.fillna("(unnamed)") +
                                 "  [Score: " + subset.risk_score.round(0).astype(int).astype(str) + "]")
        sel = st.selectbox("Select a project", labeled.label.tolist())
        row = labeled[labeled.label == sel].iloc[0]

        # Row 1: name, score pill, tier
        st.markdown(f"## {row.project_name}")
        pill_color = TIER_COLORS[row.risk_tier]
        st.markdown(
            f"<span style='background:{pill_color}; color:#fff; padding:4px 14px; "
            f"border-radius:4px; font-size:1.3rem; font-weight:700;'>{fmt_score(row.risk_score)}</span> "
            f"&nbsp; {TIER_BADGE[row.risk_tier]} risk",
            unsafe_allow_html=True,
        )
        st.markdown("")

        # Row 2: three columns
        c1, c2, c3 = st.columns(3)
        with c1:
            st.markdown("**Project Info**")
            st.write(f"Agency: {row.agency}")
            st.write(f"Ministry: {row.ministry}")
            st.write(f"Sector: {row.sector}")
            st.write(f"State: {row.state}")
        with c2:
            st.markdown("**Cost & Progress**")
            st.write(f"Original Cost: {fmt_cr(row.original_cost)}")
            st.write(f"Latest Cost: {fmt_cr(row.latest_cost)}")
            st.write(f"Physical Progress: {fmt_pct1(row.physical_progress)}")
        with c3:
            st.markdown("**Predictions**")
            st.write(f"Predicted new slippage (12mo): {fmt_months(row.slip_months_pred)} months")
            st.write(f"Cost escalation (p50–p90): {fmt_pct1(row.cost_q50_pred)} – {fmt_pct1(row.cost_q90_pred)}")
            st.write(f"Slippage probability: {fmt_prob(row.slip_prob)}")
            st.write(f"Cost escalation probability: {fmt_prob(row.cost_prob)}")

        # Row 3: SHAP, full width
        st.subheader("Why is this project flagged?")
        drivers = shap_top50[shap_top50.uid == row.uid]
        if len(drivers):
            d = drivers.iloc[0]
            feats = [human_label(d[f"driver_{i}_feature"]) for i in range(1, 6)]
            raw_feats = [d[f"driver_{i}_feature"] for i in range(1, 6)]
            vals = [d[f"driver_{i}_shap"] for i in range(1, 6)]
            colors = [BLUE if f in {"ministry", "sector", "state", "agency", "original_cost",
                                     "physical_progress"} else ORANGE for f in raw_feats]
            fig = go.Figure(go.Bar(x=vals, y=feats, orientation="h", marker_color=colors))
            fig.update_layout(title="Top 5 reasons this project is flagged",
                              xaxis_title="Contribution to risk score", yaxis={"categoryorder": "total ascending"},
                              height=280, margin=dict(t=40, b=10))
            st.plotly_chart(fig, width="stretch", config=CONFIG_STATIC)
            st.caption("🔵 CUF field &nbsp;&nbsp; 🟠 Engineered feature")
        else:
            st.info("Project-level explanation not computed for this project (only a sample of projects "
                     "gets one each run). Showing the overall top drivers across all projects instead:")
            g = combined_importance(shap_global).sort_values("combined", ascending=False).head(5)
            for _, r in g.iterrows():
                st.write(f"- {human_label(r.feature)}")

        # What-if lever
        st.subheader("🔧 What-if: what would move this project's risk?")
        st.caption("Adjusts two key factors and reruns the trained models live to show the effect. "
                   "This does not change any saved data — it's a hypothetical.")
        base_rows = panel[panel.uid == row.uid].sort_values("report_mi")
        if base_rows.empty:
            st.caption("No panel data available for this project.")
        else:
            base_row = base_rows.iloc[-1].copy()
            wc1, wc2 = st.columns(2)
            d_progress = wc1.slider("Physical progress change (pts)", -30, 30, 0, key=f"wi_prog_{row.uid}")
            d_cost = wc2.slider("Cost revision change (pts)", -30, 30, 0, key=f"wi_cost_{row.uid}")
            if d_progress or d_cost:
                models = load_whatif_models()
                top_agency_wi = panel["agency"].value_counts().nlargest(200).index
                wi_row = base_row.copy()
                wi_row["physical_progress"] = min(100.0, max(0.0, wi_row["physical_progress"] + d_progress))
                wi_row["cost_revision_to_date_pct"] = wi_row["cost_revision_to_date_pct"] + d_cost
                wi_row["progress_gap_pct"] = wi_row["financial_progress_pct"] - wi_row["physical_progress"]
                wi_df = pd.DataFrame([wi_row])
                slip_bundle, cost_bundle = models["slip"], models["cost"]
                X_wi = build_X(wi_df, slip_bundle["features"], slip_bundle["categorical"], top_agency_wi)
                new_slip = float(slip_bundle["model"].predict_proba(X_wi)[:, 1][0])
                new_cost = float(cost_bundle["model"].predict_proba(X_wi)[:, 1][0])
                new_score = (0.5 * new_slip + 0.5 * new_cost) * 100
                delta = new_score - row.risk_score
                wr1, wr2 = st.columns(2)
                wr1.metric("Hypothetical risk score", fmt_score(new_score), fmt_delta(delta))
                wr2.write(f"Current: **{fmt_score(row.risk_score)}** → What-if: **{fmt_score(new_score)}**")
            else:
                st.caption("Move a slider to see the effect.")

        # Row 4: trend + progress side by side
        r4c1, r4c2 = st.columns(2)
        with r4c1:
            st.subheader("Risk Score Trend")
            if not history.empty:
                proj_hist = history[history.uid == row.uid].sort_values("report_month").tail(6)
                if len(proj_hist) > 1:
                    fig_trend = px.line(proj_hist, x="report_month", y="risk_score", markers=True,
                                        title="Risk score, last 6 reports")
                    fig_trend.add_hline(y=40, line_dash="dot", line_color=TIER_COLORS["Amber"])
                    fig_trend.add_hline(y=70, line_dash="dot", line_color=TIER_COLORS["Red"])
                    st.plotly_chart(fig_trend, width="stretch", config=CONFIG_STATIC)
                else:
                    st.caption("Trend not available — this project has only one scored report so far.")
        with r4c2:
            st.subheader("Progress: Physical vs. Financial")
            proj_panel = panel[panel.uid == row.uid].sort_values("report_mi")
            if len(proj_panel) > 1:
                fig_prog = px.line(proj_panel, x="report_month",
                                   y=["physical_progress", "financial_progress_pct"],
                                   markers=True, title="Physical vs. financial progress",
                                   labels={"value": "%", "report_month": "Month", "variable": "Series"})
                months_dt = pd.to_datetime(proj_panel.report_month + "-01")
                gap_mask = months_dt.diff().dt.days > 90
                st.plotly_chart(fig_prog, width="stretch")  # toolbar kept -- zoom is genuinely useful here
                if gap_mask.any():
                    gap_at = proj_panel.report_month[gap_mask].iloc[0]
                    st.caption(f"⚠️ Data gap detected before {gap_at} — this project wasn't reported in "
                               "the intervening months, so the jump above reflects missing reports, not "
                               "actual month-to-month progress.")
                if (proj_panel.physical_progress == 0).sum() > 2:
                    st.caption("⚠️ Physical progress was reported as 0% in several legacy-format reports "
                               "(pre-portal). Actual progress may have been higher than shown.")
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
            fig3.update_layout(height=260)
            st.plotly_chart(fig3, width="stretch", config=CONFIG_STATIC)
        else:
            st.caption("Timeline history not available — this project may have been added in the current month only.")

# ───────────────────────────────────────────── Tab 3: Sector & Agency Benchmarks
with tab3:
    st.caption(f"Benchmarks computed over the {len(filtered_risk):,} projects matching the top filter bar.")
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

    def hbar(df, metric, title, color):
        d = df.sort_values(metric, ascending=True).tail(15)
        fig = px.bar(d, x=metric, y=dim, orientation="h", color_discrete_sequence=[color],
                     title=title, labels=COLUMN_LABELS)
        fig.update_layout(yaxis_title=None, height=max(400, len(d) * 28), margin=dict(l=10))
        return fig

    col1, col2 = st.columns(2)
    with col1:
        st.plotly_chart(hbar(g, "median_cost_overrun_pct", "Median Cost Overrun %", BLUE),
                        width="stretch", config=CONFIG_STATIC)
    with col2:
        st.plotly_chart(hbar(g, "median_time_slip_m", "Median Time Slip (months)", ORANGE),
                        width="stretch", config=CONFIG_STATIC)
    st.plotly_chart(hbar(g, "pct_past_orig_doc", "Share of Projects Past Original DoC", RED),
                    width="stretch", config=CONFIG_STATIC)

    st.subheader("Trend Over Time")
    trend = filtered_panel.groupby([dim, "report_month"]).agg(
        median_cost_overrun_pct=("cost_revision_to_date_pct", "median"),
        n_projects=("uid", "nunique"),
    ).reset_index()
    trend = trend[trend.n_projects >= 3]
    top_groups = g.nlargest(8, "n_projects")[dim].tolist()
    trend_top = trend[trend[dim].isin(top_groups)]
    fig_trend = px.line(trend_top, x="report_month", y="median_cost_overrun_pct", color=dim, markers=True,
                        title=f"Cost Overrun Trend Over Time — Top 8 by {dim}", labels=COLUMN_LABELS)
    st.plotly_chart(fig_trend, width="stretch")  # toolbar kept -- time series, zoom useful

    st.subheader("Comparison Table")
    comp_table = g.sort_values("median_cost_overrun_pct", ascending=False).copy()
    comp_table["median_cost_overrun_pct"] = comp_table.median_cost_overrun_pct.apply(fmt_pct1)
    comp_table["median_time_slip_m"] = comp_table.median_time_slip_m.apply(fmt_months)
    comp_table["pct_past_orig_doc"] = (g.pct_past_orig_doc * 100).apply(lambda x: f"{x:.0f}%")
    st.dataframe(comp_table.rename(columns=COLUMN_LABELS), width="stretch", hide_index=True, height=400)
    st.download_button("⬇ Export Comparison Table (CSV)", g.to_csv(index=False).encode("utf-8"),
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
    ag_display = ag.copy()
    ag_display["pct_on_budget"] = ag.pct_on_budget.apply(lambda x: f"{x:.0f}%")
    ag_display["pct_on_time"] = ag.pct_on_time.apply(lambda x: f"{x:.0f}%")
    ag_display["median_cost_overrun_pct"] = ag.median_cost_overrun_pct.apply(fmt_pct1)
    ag_display["median_time_slip_m"] = ag.median_time_slip_m.apply(fmt_months)
    ag_display["delivery_score"] = ag.delivery_score.round(0).astype(int)
    st.dataframe(ag_display.rename(columns=COLUMN_LABELS), width="stretch", hide_index=True, height=400)
    st.download_button("⬇ Export Agency Scorecard (CSV)", ag.to_csv(index=False).encode("utf-8"),
                        "agency_scorecard.csv", "text/csv")

# ───────────────────────────────────────────── Tab 4: Early Warning Alerts
with tab4:
    alert_df = filtered_risk[filtered_risk.alert_type.notna()].copy()
    # Deterioration alerts only make sense with a positive delta; stalled/overdue
    # doesn't depend on delta at all (it's a status check, not a month-over-month one).
    keep = (alert_df.alert_type == "Stalled and Overdue") | (alert_df.risk_score_delta > 0)
    alert_df = alert_df[keep]
    alert_df["recommended_action"] = alert_df.alert_type.map(ALERT_ACTIONS)

    n_rapid = int((alert_df.alert_type == "Rapidly Deteriorating").sum())
    n_new = int((alert_df.alert_type == "Newly At Risk").sum())
    n_stalled = int((alert_df.alert_type == "Stalled and Overdue").sum())
    col1, col2, col3 = st.columns(3)
    with col1:
        st.markdown("**Rapidly deteriorating**")
        st.markdown(f"<h1 style='color:{RED};margin:0'>{n_rapid}</h1>", unsafe_allow_html=True)
    with col2:
        st.markdown("**Newly at risk**")
        st.markdown(f"<h1 style='color:{ORANGE};margin:0'>{n_new}</h1>", unsafe_allow_html=True)
    with col3:
        st.markdown("**Stalled and overdue**")
        st.markdown(f"<h1 style='color:{YELLOW};margin:0'>{n_stalled}</h1>", unsafe_allow_html=True)

    sel_type = st.selectbox("Alert Type", ["All"] + list(ALERT_ACTIONS.keys()))
    view = alert_df if sel_type == "All" else alert_df[alert_df.alert_type == sel_type]
    view = view.sort_values("risk_score", ascending=False).copy()
    view["Alert"] = view.alert_type.map(ALERT_BADGE)
    view["Risk score"] = view.risk_score.apply(fmt_score)
    view["Change"] = view.risk_score_delta.apply(fmt_delta)

    view_display = view.rename(columns={"project_name": "Project", "ministry": "Ministry",
                                        "sector": "Sector", "recommended_action": "Recommended action",
                                        "state": "State"})
    st.dataframe(
        view_display[["Alert", "Project", "Ministry", "Sector", "Risk score", "Change",
                      "Recommended action", "State"]],
        width="stretch", hide_index=True, height=400,
    )
    st.download_button("⬇ Export Alerts (CSV)", view.to_csv(index=False).encode("utf-8"),
                        "paimana_alerts.csv", "text/csv")

# ───────────────────────────────────────────── Tab 5: Model & Field Analysis
with tab5:
    # Section 1 (lead): what drives risk -- the plain-language story first
    st.subheader("What drives project risk?")
    shap_labeled = shap_global.assign(
        feature_label=shap_global.feature.apply(human_label),
        field_source=shap_global.feature.apply(field_source),
    )
    col1, col2 = st.columns(2)
    with col1:
        g1 = shap_labeled.sort_values("mean_abs_shap_time", ascending=False).head(15)
        fig = px.bar(g1.sort_values("mean_abs_shap_time"), x="mean_abs_shap_time", y="feature_label",
                     orientation="h", color="field_source",
                     color_discrete_map={"CUF Field": BLUE, "Engineered Feature": ORANGE},
                     title="Time Model — Top Drivers")
        fig.update_layout(yaxis_title=None, height=460, margin=dict(l=10))
        st.plotly_chart(fig, width="stretch", config=CONFIG_STATIC)
    with col2:
        g2 = shap_labeled.sort_values("mean_abs_shap_cost", ascending=False).head(15)
        fig2 = px.bar(g2.sort_values("mean_abs_shap_cost"), x="mean_abs_shap_cost", y="feature_label",
                      orientation="h", color="field_source",
                      color_discrete_map={"CUF Field": BLUE, "Engineered Feature": ORANGE},
                      title="Cost Model — Top Drivers")
        fig2.update_layout(yaxis_title=None, height=460, margin=dict(l=10))
        st.plotly_chart(fig2, width="stretch", config=CONFIG_STATIC)
    st.caption("🔵 CUF field (already collected)  &nbsp;&nbsp; 🟠 Engineered feature (derived from CUF data)")

    combined = combined_importance(shap_labeled).sort_values("combined", ascending=False)
    top5 = combined.head(5).feature_label.tolist()
    share = combined.head(5).combined.sum() / combined.combined.sum() * 100 if combined.combined.sum() else 0
    st.markdown(
        f"**~{share:.0f}%** of the models' predictive signal comes from the top 5 fields: **{', '.join(top5)}**. "
        "The current monitoring framework (CUF) already captures the most predictive signals available. "
        "Fields that would likely improve prediction further but are **not** currently in the CUF: "
        "planned quarterly expenditure, mode of implementation (EPC/HAM/BOT/PPP), Brown/Green field, "
        "PM GatiShakti flag, and milestone data from PMG integration.\n\n"
        "PAIMANA-CRIP's new Common Upload Form will add quarterly planned expenditure, district "
        "location, project stage, and GatiShakti flag — currently absent from flash reports. These "
        "are next-priority features for model improvement."
    )

    # Risk archetypes
    if not archetype_summary.empty:
        st.subheader("Risk Archetypes — how do the riskiest projects fail?")
        st.caption("Clustered from the SHAP driver pattern of a sample of scored projects — groups "
                   "projects by WHY they're risky, not just how risky. See cluster_archetypes.py.")
        arc_display = archetype_summary.rename(columns={
            "archetype_label": "Dominant pattern", "n_projects": "Projects", "avg_risk_score": "Avg. risk score"})
        arc_display["Avg. risk score"] = arc_display["Avg. risk score"].apply(fmt_score)
        st.dataframe(arc_display[["Dominant pattern", "Projects", "Avg. risk score"]],
                    width="stretch", hide_index=True)

    # Section 2: simplified ML-vs-statistical comparison
    if not model_comp.empty:
        st.subheader("How does ML compare to simple rules?")

        def _auc(target_label, model_label):
            r = model_comp[(model_comp.target == target_label) & (model_comp.model == model_label)]
            return float(r.roc_auc.iloc[0]) if len(r) and r.roc_auc.iloc[0] != "-" else None

        def _p10(target_label, model_label):
            r = model_comp[(model_comp.target == target_label) & (model_comp.model == model_label)]
            col = "precision@top10%"
            return float(r[col].iloc[0]) if len(r) and r[col].iloc[0] != "-" else None

        colA, colB = st.columns(2)
        t_auc, t_base = _auc("time: y_slippage_flag", "model"), _auc("time: y_slippage_flag", "baseline(is_past_orig_doc)")
        t_p10, t_bp10 = _p10("time: y_slippage_flag", "model"), _p10("time: y_slippage_flag", "baseline(is_past_orig_doc)")
        c_auc, c_base = _auc("cost: y_cost_overrun_flag", "model"), _auc("cost: y_cost_overrun_flag", "baseline(is_past_orig_doc)")
        c_p10, c_bp10 = _p10("cost: y_cost_overrun_flag", "model"), _p10("cost: y_cost_overrun_flag", "baseline(is_past_orig_doc)")
        with colA:
            st.markdown("#### Time overrun prediction")
            if t_p10 and t_bp10:
                st.markdown(f"**ML model:** catches {t_p10*100:.0f}% of projects that slip, at the top decile")
                st.markdown(f"**Simple rule** (flag if past deadline): catches {t_bp10*100:.0f}%")
            if t_auc and t_base:
                gain = (t_auc - t_base) / t_base * 100
                st.markdown(f"**Improvement: +{gain:.0f}%** ranking ability (AUC {t_auc:.3f} vs {t_base:.3f})")
        with colB:
            st.markdown("#### Cost overrun prediction")
            if c_p10 and c_bp10:
                st.markdown(f"**ML model:** catches {c_p10*100:.0f}% of cost escalations, at the top decile")
                st.markdown(f"**Simple rule** (flag if past deadline): catches {c_bp10*100:.0f}%")
            if c_auc and c_base:
                gain = (c_auc - c_base) / c_base * 100
                st.markdown(f"**Improvement: +{gain:.0f}%** ranking ability (AUC {c_auc:.3f} vs {c_base:.3f})")

        with st.expander("Technical evaluation details (for audit/review)"):
            st.dataframe(model_comp, width="stretch", hide_index=True)
            st.caption("Evaluated on 5-fold GroupKFold cross-validation (project-level). "
                       "See temporal_eval.txt for a strict future-holdout evaluation.")
    else:
        st.info("Run train_models.py to populate model_comparison.csv.")
