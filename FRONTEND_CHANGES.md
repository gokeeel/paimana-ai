# PAIMANA-AI — Frontend Changes & UX Audit

**Prepared as:** UI/UX Design Review  
**Against:** PRD v1.0 (PAIMANA-AI_PRD_corrected.md)  
**Audience:** Ministry-level presentation + Hackathon Jury  
**Stack:** Streamlit (dashboard.py)

---

## Part 1 — Process Plan: What to Build Before the LLM

### Step 1 — Complete Module E (Benchmarking)

The Benchmarking tab exists but is **partial**. The PRD requires three things currently missing:

**FR-E2 — Trend over time (missing entirely)**  
The current tab only shows the *latest* snapshot grouped by ministry/sector/state. There is no year-over-year or month-over-month trend. A ministry person needs to see "is Transport & Logistics getting better or worse?"

Fix: add a line chart of `median_cost_overrun_pct` and `median_time_slip_m` over all available `report_month` values, grouped by the selected dimension.

```python
# Add to Tab 3 after the snapshot charts
trend = panel.groupby([dim, "report_month"]).agg(
    median_cost_overrun_pct=("cost_revision_to_date_pct", "median"),
    median_time_slip_m=("doc_slip_to_date_m", "median"),
    n_projects=("uid", "nunique"),
).reset_index()
trend = trend[trend.n_projects >= 3]
top_groups = g.nlargest(8, "n_projects")[dim].tolist()
trend_top = trend[trend[dim].isin(top_groups)]

fig_trend = px.line(
    trend_top, x="report_month", y="median_cost_overrun_pct",
    color=dim, markers=True,
    title=f"Cost Overrun Trend Over Time — Top 8 by {dim}",
)
st.plotly_chart(fig_trend, use_container_width=True)
```

**FR-E3 — Agency Scorecard (missing entirely)**  
No agency-level on-time / on-budget delivery rate exists anywhere in the dashboard. This is a Must requirement from the PRD.

Fix: build an agency scorecard table from `panel.csv` grouped by `agency`:
- Columns: `agency`, `n_projects`, `pct_on_budget` (cost overrun < 10%), `pct_on_time` (not past orig_doc), `median_cost_overrun_pct`, `median_time_slip_m`, `score_grade` (A/B/C/D)
- Min sample guard: only show agencies with ≥ 5 projects
- Sort by composite delivery score descending

**model_comparison.csv is never shown**  
`train_models.py` saves `model_comparison.csv` with ML-vs-baseline results. This is the core of Research Dimension B (FR-6.10) — the PRD says it must be benchmarked and shown. It is currently invisible.

Fix: add a **new tab "Model Comparison"** (or sub-section under Benchmarking) that loads and displays `model_comparison.csv` as a formatted table with context.

---

### Step 2 — Build Module H (LLM Assistant with Groq)

**Process:**

1. **Install dependencies**
   ```
   pip install groq chromadb sentence-transformers
   ```

2. **Build the RAG context layer** (`llm_context.py`)  
   At startup, embed a flattened text representation of each project's risk row into ChromaDB. Each document = one project's key fields as plain text. Keep it simple — no PDF parsing, just structured data converted to sentences.

3. **Build the query engine** — user question → ChromaDB similarity search → top-5 matching project chunks → assemble prompt → Groq API call → display answer + source rows

4. **Groq setup**  
   - API key via `st.secrets["GROQ_API_KEY"]` or `.env`  
   - Model: `llama-3.3-70b-versatile` (free tier, fast)  
   - Every numeric answer must be sourced from a pandas query result, NOT from the LLM's generation (FR-H3)

5. **Add as a new Streamlit tab** — "AI Assistant"

The LLM must never generate numbers on its own. The architecture:
```
User question → pandas query (structured) → answer table → LLM narrates the table → show both
```

---

## Part 2 — UI/UX Audit: Flaws, Mistakes, and Fixes

### Flaw 1 — Wrong Risk Banding (Critical PRD Mismatch)

**What the code does:**  
```python
def risk_tier(score):
    if score >= 75: return "Critical"
    if score >= 50: return "High"
    if score >= 25: return "Medium"
    return "Low"
```
Four tiers: Critical / High / Medium / Low.

**What the PRD requires (FR-C2):**  
Three bands — **Green (0–39)**, **Amber (40–69)**, **Red (70–100)**.

**Why this matters for a ministry person:**  
A ministry administrator ("Meera") expects traffic-light language — Green/Amber/Red — because that's the vocabulary used in PAIMANA/OCMS reporting and Cabinet/Parliament briefings. "Critical" and "High" are developer vocabulary, not policy vocabulary. When Meera sees a "High" project, she doesn't immediately know if it needs action today or next quarter.

**Fix:**  
In `score_projects.py`, change `risk_tier` to:
```python
def risk_tier(score):
    if score >= 70: return "Red"
    if score >= 40: return "Amber"
    return "Green"
```
Update `TIER_COLORS` in `dashboard.py`:
```python
TIER_COLORS = {"Red": "#d32f2f", "Amber": "#ff6f00", "Green": "#43a047"}
```
Update every reference to "Critical/High/Medium/Low" across the dashboard and summary JSON. The metric card should say "Projects in Red/Amber" not "Projects At Risk".

---

### Flaw 2 — No Filters Anywhere in the Dashboard

**What the code does:**  
Every tab renders a fixed, global view. The portfolio overview shows ALL projects. Tab 2 requires you to scroll a dropdown of all ~1,981 projects. Tab 3 shows all ministries.

**What the PRD requires (FR-G2):**  
"Dashboard shall provide a sortable/filterable project table (by ministry, sector, state, agency, risk band, cost band)."

**Why this matters for a ministry person:**  
Meera from Ministry of Road Transport has zero interest in Railway or Power projects. When she opens the dashboard, she sees 1,981 projects and has no way to see only her 200. This is the most fundamental usability failure for the named persona. She will close the tab.

**Fix:**  
Add a **sidebar filter panel** visible on all tabs:
```python
with st.sidebar:
    st.header("Filters")
    sel_ministry = st.multiselect("Ministry", sorted(risk.ministry.dropna().unique()))
    sel_sector   = st.multiselect("Sector",   sorted(risk.sector.dropna().unique()))
    sel_state    = st.multiselect("State",     sorted(risk.state.dropna().unique()))
    sel_tier     = st.multiselect("Risk Band", ["Red", "Amber", "Green"], default=["Red","Amber","Green"])
    cost_min, cost_max = st.slider("Original Cost (₹ Cr)", 150, 50000, (150, 50000))

# Apply filters once, reuse across all tabs
mask = pd.Series([True] * len(risk))
if sel_ministry: mask &= risk.ministry.isin(sel_ministry)
if sel_sector:   mask &= risk.sector.isin(sel_sector)
if sel_state:    mask &= risk.state.isin(sel_state)
if sel_tier:     mask &= risk.risk_tier.isin(sel_tier)
mask &= (risk.original_cost >= cost_min) & (risk.original_cost <= cost_max)
filtered_risk = risk[mask]
```
All tabs then operate on `filtered_risk` instead of `risk`.

---

### Flaw 3 — Project Deep Dive is Broken for Non-Top-50 Projects

**What the code does:**  
In Tab 2, when a user selects a project that is NOT in the top-50 riskiest, the SHAP section shows:
> "SHAP explanations are only computed for the top-50 riskiest projects in this run."

And the Timeline section silently shows nothing if the project has no `report_mi` data.

**Why this matters:**  
For Ravi (IPMD Monitoring Officer), if he wants to investigate a specific project that was flagged in an alert but ranks 200th overall, he gets a half-empty detail page with no explanation. This destroys trust in the tool.

**Fix — two-part:**  
1. For the SHAP section: when the project is not in top-50, fall back to the global SHAP feature importances and display them as a note: "Project-level explanation not computed for this project. Global top drivers shown below." Don't show a dead end.

2. For the Timeline: if `hist` is empty, explain why with a clear message: "Timeline history not available — this project may have been added in the current month only."

3. Add a **Risk Score Trend** line chart using the panel history: `physical_progress` and `cost_revision_to_date_pct` over time for that project. This is more useful than the current milestone bar chart for a ministry person reviewing progress.

---

### Flaw 4 — Early Warning Alerts Tab is a Wall of Text

**What the code does:**  
Tab 4 renders a flat, unstyled markdown bullet list of alert text like:
```
- **National Highway 58** (Ministry of Road Transport) — risk 87.3, Δ+19.2 pts. *Escalate to ministry PMU...*
- **Bharat Mala Pariyojana...** ...
```
There's no way to filter, sort, or export the alerts. With 50+ alerts, this is completely unusable.

**What the PRD requires (FR-D3, FR-D4, FR-D5):**  
Plain-language explanation ✓, viewable in-app ✓, **exportable (CSV/PDF)** ✗.

**Why this matters for a ministry person:**  
Meera's job is to take this list to a review meeting. She needs to export it. She also needs to see only alerts for her ministry, not all 17. And she cannot act on a bullet point — she needs the project name, ministry, risk score, and action item in a structured table she can download.

**Fix:**  
Replace the markdown list with a styled dataframe + export button:
```python
with tab4:
    alert_df = filtered_risk[filtered_risk.alert_type.notna()].copy()
    alert_df["recommended_action"] = alert_df.alert_type.map(ALERT_ACTIONS)

    # Summary cards per alert type
    col1, col2, col3 = st.columns(3)
    col1.metric("🔴 Rapidly Deteriorating", len(alert_df[alert_df.alert_type=="Rapidly Deteriorating"]))
    col2.metric("🟠 Newly At Risk",         len(alert_df[alert_df.alert_type=="Newly At Risk"]))
    col3.metric("🟡 Stalled and Overdue",   len(alert_df[alert_df.alert_type=="Stalled and Overdue"]))

    # Filterable table
    sel_type = st.selectbox("Alert Type", ["All"] + list(ALERT_ACTIONS.keys()))
    view = alert_df if sel_type == "All" else alert_df[alert_df.alert_type == sel_type]

    st.dataframe(
        view[["project_name","ministry","sector","risk_score","risk_score_delta","alert_type","recommended_action"]],
        use_container_width=True, hide_index=True
    )

    # Export
    csv = view.to_csv(index=False).encode("utf-8")
    st.download_button("⬇ Export Alerts (CSV)", csv, "paimana_alerts.csv", "text/csv")
```

---

### Flaw 5 — Traffic Light Colours Used Inconsistently

**What the code does:**  
- Alert text for "Rapidly Deteriorating" uses `:red[...]` Streamlit colour markup  
- Alert text for everything else uses `:orange[...]`  
- But the bar charts use `#1a237e` (dark navy) and `#ff6f00` (orange) regardless of risk level  
- The risk tier bar chart uses `TIER_COLORS` correctly but the ministry chart uses `[BLUE]` — so a "Critical" ministry bar is navy, same as a "Low" bar

**Why this matters:**  
Colour is the primary pre-attentive signal in a dashboard. When a ministry person scans charts, they expect red = danger, green = safe. A navy bar meaning "most dangerous ministry" and a navy bar meaning "on-track" creates cognitive load and distrust.

**Fix:**  
- Colour every project-count bar chart by risk tier using `TIER_COLORS` (after fixing to Red/Amber/Green)
- Use a consistent colour scale for all ministry/sector aggregate charts: red end = most overrun, green end = least overrun
- Use `color_continuous_scale="RdYlGn_r"` on all performance charts:
```python
fig2 = px.bar(top_min, x="count", y="ministry", orientation="h",
              color="count", color_continuous_scale="Reds",
              title="Ministries with Most Red/Amber Projects")
```

---

### Flaw 6 — No Export Anywhere Except Alerts

**What the PRD requires (FR-D5 and implied by Personas 1 & 2):**  
Monitoring Officer Ravi needs to "export a shortlist for the monthly review meeting." Meera needs a "monthly digest."

**What the code does:**  
Zero export buttons anywhere. The only table that could be exported (Tab 1's Top 20 Riskiest) has no download option.

**Fix:**  
Add a download button below every major table:
```python
# After every st.dataframe() call
csv_bytes = df_to_export.to_csv(index=False).encode("utf-8")
st.download_button("⬇ Export as CSV", csv_bytes, f"{table_name}.csv", "text/csv")
```
Also add a **"Generate Monthly Report (PDF)"** button in the sidebar that calls `generate_report.py`'s logic inline.

---

### Flaw 7 — Report Month Context is Missing Everywhere

**What the code does:**  
The sidebar or header shows nothing about which month's data is loaded. The only place the report month appears is Tab 4: "X active alerts for report month 2026-07."

**Why this matters:**  
A ministry person opening the dashboard has no idea if they're looking at April 2026 or July 2026 data. If they make a decision based on stale data thinking it's current, that's a trust and safety issue.

**Fix:**  
Add a persistent banner at the top of every page and in the sidebar:
```python
with st.sidebar:
    st.info(f"📅 Data as of: **{summary['report_month']}**")
    st.caption("Run score_projects.py to refresh with new monthly data.")

# Also in the header section:
st.markdown(f"""
<div style="background:#e3f2fd;padding:8px 16px;border-radius:6px;margin-bottom:12px;">
  📅 Showing data for <strong>{summary['report_month']}</strong> &nbsp;|&nbsp;
  {summary['total_projects']:,} projects &nbsp;|&nbsp;
  {summary['critical'] + summary['high']} at Red/Amber risk
</div>
""", unsafe_allow_html=True)
```

---

### Flaw 8 — CUF Field Attribution Tab is for Technical Audiences Only

**What the PRD says about Persona 2 (Meera):**  
She needs to know "what 2-3 factors contribute" to her project's risk. The CUF tab currently shows raw SHAP variable names like `elapsed_ratio`, `doc_slip_to_date_m`, `cost_revision_to_date_pct` — these mean nothing to a ministry administrator.

**What the PRD says about Persona 3 (Dr. Anand):**  
He needs to cite findings in policy recommendations. He needs the CUF vs. non-CUF breakdown with a clear take-away.

**Why this matters:**  
The CUF tab currently serves neither persona well. Meera sees jargon. Dr. Anand sees no explicit CUF vs. non-CUF split — just a SHAP bar chart and a paragraph.

**Fix — two parts:**

**Part A — Human-readable feature labels:**  
Create a mapping dictionary:
```python
FEATURE_LABELS = {
    "elapsed_ratio":              "Time elapsed vs. planned duration",
    "doc_slip_to_date_m":         "Months already slipped from original completion date",
    "cost_revision_to_date_pct":  "Cost already revised upward (%)",
    "physical_progress":          "Physical progress (%)",
    "months_past_orig_doc":       "Months past original completion date",
    "is_past_orig_doc":           "Currently past original completion date (Yes/No)",
    "progress_gap_pct":           "Progress gap (financial ahead/behind physical)",
    "orig_duration_m":            "Original planned project duration (months)",
    "log_original_cost":          "Project size (log of sanctioned cost)",
    "sanction_year":              "Year project was sanctioned",
    "ministry":                   "Ministry / Department",
    "sector":                     "Infrastructure sector",
    "agency":                     "Implementing agency",
    # ...
}
shap_global["feature_label"] = shap_global["feature"].map(FEATURE_LABELS).fillna(shap_global["feature"])
```

**Part B — Explicit CUF vs. Engineered split:**  
Tag every feature as `CUF Field` or `Engineered Feature`:
```python
CUF_FIELDS = {
    "original_cost", "physical_progress", "ministry", "sector",
    "state", "agency", "approval_date", "expenditure",
    # ... fields directly from the CUF form
}
shap_global["field_source"] = shap_global["feature"].apply(
    lambda f: "CUF Field" if f in CUF_FIELDS else "Engineered Feature"
)
fig = px.bar(shap_global.head(15), x="combined", y="feature_label",
             orientation="h", color="field_source",
             color_discrete_map={"CUF Field": BLUE, "Engineered Feature": ORANGE},
             title="What drives risk predictions? (CUF fields vs. engineered features)")
```
This directly answers Dimension C and gives Dr. Anand something citable.

---

### Flaw 9 — Project Deep Dive Selectbox is Unusable at Scale

**What the code does:**  
```python
labeled = risk.assign(label=...)
sel = st.selectbox("Select a project", labeled.label.tolist())
```
This loads ALL 1,981 project names into a single dropdown. Users cannot search by ministry first. There's no way to navigate to "show me the riskiest project in Railways."

**Fix:**  
Use a two-step filter-then-select pattern:
```python
with tab2:
    col_f1, col_f2, col_f3 = st.columns(3)
    f_ministry = col_f1.selectbox("Filter by Ministry", ["All"] + sorted(risk.ministry.dropna().unique()))
    f_sector   = col_f2.selectbox("Filter by Sector",   ["All"] + sorted(risk.sector.dropna().unique()))
    f_tier     = col_f3.selectbox("Filter by Risk Band", ["All", "Red", "Amber", "Green"])

    subset = risk.copy()
    if f_ministry != "All": subset = subset[subset.ministry == f_ministry]
    if f_sector   != "All": subset = subset[subset.sector   == f_sector]
    if f_tier     != "All": subset = subset[subset.risk_tier == f_tier]
    subset = subset.sort_values("risk_score", ascending=False)

    labeled = subset.assign(label=subset.project_name.fillna("(unnamed)") + 
                                   "  [Score: " + subset.risk_score.round(1).astype(str) + "]")
    sel = st.selectbox("Select a project", labeled.label.tolist())
```

---

### Flaw 10 — Tab Labels Don't Match Ministry Vocabulary

**What the code does:**  
Tab labels: `Portfolio Overview | Project Deep Dive | Benchmarking | Early Warning Alerts | CUF Field Attribution`

**Why this matters:**  
"CUF Field Attribution" means nothing to Meera. "Project Deep Dive" is developer language. A ministry person presenting to a Secretary or Joint Secretary will not use these words.

**Fix — rename tabs:**
```python
tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
    "📊 Portfolio Overview",
    "🔍 Project Details",
    "📈 Sector & Agency Benchmarks",
    "🚨 Early Warning Alerts",
    "🤖 AI Assistant",          # new LLM tab
    "🔬 Model & Field Analysis"  # renamed, combines comparison + CUF attribution
])
```

---

### Flaw 11 — Benchmarking Tab Missing the model_comparison.csv (Research Dimension B)

The PRD explicitly requires benchmarking ≥ 3 statistical baselines vs ≥ 2 ML models (FR-6.10). The `model_comparison.csv` exists but is never surfaced. This is the most important thing for Persona 3 (Dr. Anand) and the Jury.

**Fix — add a "Model Comparison" section to the new "Model & Field Analysis" tab:**
```python
model_comp = pd.read_csv(f"{DATA_DIR}/model_comparison.csv")
st.subheader("Statistical Baseline vs. ML Model Performance")
st.caption("Evaluated on 5-fold GroupKFold cross-validation (project-level). "
           "Temporal holdout evaluation is the next step before production deployment.")
st.dataframe(model_comp, use_container_width=True, hide_index=True)

# Highlight the ML gain clearly
st.markdown("""
**Key finding:** The ML model (HistGradientBoosting) achieves ROC-AUC of **0.857** vs. the 
statistical baseline's **0.594** on time-slippage prediction — a **+44% relative improvement** 
in ranking ability. For cost overrun, the gain is **0.838 vs. 0.612** (+37%).

This directly addresses Research Dimension B from the hackathon problem statement.
""")
```

---

## Part 3 — Ministry Presentation: How to Present This Correctly

### Who is in the room
A ministry presentation typically has: Joint Secretary (JS) or Additional Secretary (AS), Project Director/PMU Head, and possibly a Cabinet Secretariat or PRAGATI review officer. They are NOT data scientists. They use Excel and attend monthly review meetings.

### What they need to see in 5 minutes

**Slide 1 / Dashboard Entry — The number they care about first**  
> "Of your 312 Road projects, **47 are in Red risk** this month. That's 4 more than last month."

Show: the filtered portfolio (their ministry only), the 3-band traffic light count, and the month-over-month change. Nothing else on this screen.

**Slide 2 — Which projects need action TODAY**  
The Early Warning Alerts tab, filtered to their ministry, exported as a PDF table. Each row: Project Name, State, Cost (₹ Cr), Risk Score, Alert Type, Recommended Action. This is what they take into the review meeting.

**Slide 3 — Why is this project flagged (1 project, the worst one)**  
The Project Details tab for their riskiest project. Show: the risk score as a gauge/dial, the top 3 reasons in plain English (using the human-readable feature labels from Flaw 8), and the timeline bar. Do NOT show SHAP jargon.

**Slide 4 — Is the sector improving or getting worse**  
The Benchmarking trend chart for their sector over the last 12 months. One line chart. This is what they report upward.

### Language to use / avoid

| ❌ Don't say | ✅ Say instead |
|---|---|
| "SHAP values indicate..." | "The main reason this project is flagged is..." |
| "ROC-AUC of 0.857" | "The system correctly identifies 9 out of 10 projects that later encountered delays" |
| "Critical / High / Medium" | "Red / Amber / Green" |
| "HistGradientBoosting classifier" | "AI model trained on 20 years of OCMS/PAIMANA data" |
| "elapsed_ratio feature" | "The project has used 80% of its planned time but completed only 55% of work" |
| "cost_revision_to_date_pct" | "Cost has already been revised upward by 23%" |
| "Slip probability: 84%" | "84% chance of missing the completion target" |
| "uid: 612786" | "Project: [full name]" |
| "predict_proba" | never say this |

### What NOT to claim in the room
- Do not say "the system predicted this 6 months in advance" unless you have the temporal lead-time analysis from Section 9.5 of the PRD to back it up. The current model uses GroupKFold, not strict temporal holdout.
- Do not say risk score = probability. Say it is a 0–100 indicator based on AI model outputs.
- Do say: "This is a decision-support tool. The model ranks projects by risk. The ministry's team takes the intervention decision."

---

## Part 4 — Summary of All Changes Required

### Priority 1 — Must fix before any ministry demo

| # | Issue | File | Effort |
|---|---|---|---|
| F1 | Fix risk banding to Green/Amber/Red (PRD FR-C2) | `score_projects.py`, `dashboard.py` | 30 min |
| F2 | Add sidebar filters (ministry, sector, state, risk band) | `dashboard.py` | 1 hr |
| F4 | Replace alert bullet list with structured table + export button | `dashboard.py` | 1 hr |
| F7 | Add persistent report-month banner | `dashboard.py` | 20 min |
| F10 | Rename tabs to plain-English ministry vocabulary | `dashboard.py` | 10 min |

### Priority 2 — Must complete to satisfy PRD requirements

| # | Issue | File | Effort |
|---|---|---|---|
| E-trend | Add time-trend chart to Benchmarking | `dashboard.py` | 1 hr |
| E-agency | Add Agency Scorecard section | `dashboard.py` | 2 hr |
| E-model | Surface model_comparison.csv in new tab | `dashboard.py` | 45 min |
| F3 | Fix empty SHAP fallback in Project Details | `dashboard.py` | 30 min |
| F8 | Human-readable feature labels + CUF vs. engineered tagging | `dashboard.py` | 2 hr |
| F9 | Two-step filter-then-select for Project Details | `dashboard.py` | 45 min |
| F11 | Model comparison display (Dimension B research deliverable) | `dashboard.py` | 45 min |

### Priority 3 — Polish before hackathon submission

| # | Issue | File | Effort |
|---|---|---|---|
| F5 | Consistent colour semantics on all charts | `dashboard.py` | 1 hr |
| F6 | Export buttons on all major tables | `dashboard.py` | 30 min |
| LLM | Module H — Groq RAG assistant tab | new `llm_assistant.py` | 4–6 hr |

---

## Part 5 — Correct Tab Structure After All Fixes

```
┌─────────────────────────────────────────────────────────────────────┐
│  SIDEBAR                                                             │
│  📅 Data as of: July 2026                                            │
│  ─────────────────────────────────────────────────────              │
│  Filter by Ministry: [multiselect]                                   │
│  Filter by Sector:   [multiselect]                                   │
│  Filter by State:    [multiselect]                                   │
│  Filter by Risk Band:[Red ✓] [Amber ✓] [Green ✓]                    │
│  Cost Range:         [₹150 Cr ────────── ₹50,000 Cr]               │
│  ─────────────────────────────────────────────────────              │
│  [Generate PDF Report]  [Export Full List CSV]                       │
└─────────────────────────────────────────────────────────────────────┘

TABS:
📊 Portfolio Overview  |  🔍 Project Details  |  📈 Benchmarks  |
🚨 Early Warning Alerts  |  🤖 AI Assistant  |  🔬 Model & Field Analysis
```

### Tab 1 — Portfolio Overview
- 4 KPI metric cards: Total Projects | Total Cost | 🔴 Red | 🟠 Amber (filtered)
- Risk band distribution bar chart (Green/Amber/Red, filtered)
- Top 10 Ministries by Red+Amber count (horizontal bar, coloured red)
- Filterable Top 20 Riskiest table + export button
- Month-over-month comparison: how many moved Green→Amber or Amber→Red this month

### Tab 2 — Project Details
- 3-column filter bar (Ministry / Sector / Risk Band) narrows the dropdown
- Dropdown shows: "Project Name [Risk Score]" sorted by risk descending
- Project info card + risk gauge (not just a number — use a gauge/speedometer)
- Risk score trend line (last 6 months of scores for that project)
- Top 3 risk drivers in plain English (no SHAP jargon)
- Timeline slippage bar
- Physical progress vs. financial progress comparison
- Export project detail as PDF button

### Tab 3 — Sector & Agency Benchmarks
- Group-by selector: Ministry / Sector / State
- Snapshot bar charts (cost overrun % + time slip months)
- **NEW: Trend over time** line chart for top 8 groups
- **NEW: Agency Scorecard** table with delivery grade (A/B/C/D)
- Comparison table with export button

### Tab 4 — Early Warning Alerts
- 3 summary metric cards (one per alert type)
- Alert type filter dropdown
- Structured table: Project | Ministry | Risk Score | Change | Alert Type | Action
- Export alerts as CSV button
- Each alert row expandable to show top 3 risk drivers

### Tab 5 — AI Assistant (NEW — Groq RAG)
- Chat input box
- Response area showing: LLM narrative answer + source data table
- Suggested questions: "Which Road sector projects are Red risk?" / "What are the top delay drivers this month?" / "Compare Railways vs. Roads overrun rate"
- Disclaimer: "Answers are grounded in PAIMANA-AI data for [report_month]. Numbers come from the database, not AI generation."

### Tab 6 — Model & Field Analysis (renamed from CUF Field Attribution)
- **NEW: Model Comparison table** (model_comparison.csv) with plain-English interpretation
- SHAP importance chart with human-readable labels and CUF vs. Engineered colour coding
- CUF attribution summary paragraph (already exists, keep it)
- Link to feature_summary.txt for Dr. Anand / researchers

---

*End of FRONTEND_CHANGES.md*
