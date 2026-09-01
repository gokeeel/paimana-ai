#!/usr/bin/env python3
"""
feature_labels.py — shared helpers used by multiple scripts, kept in one place
so a fix here doesn't need repeating everywhere:

  - plain-English feature names + CUF/engineered tagging, so SHAP's raw column
    names (elapsed_ratio, doc_slip_to_date_m, ...) never reach a ministry
    audience in the dashboard or the PDF report (PRD Persona 2 / F8)
  - build_X(): reindex a DataFrame to a model's feature columns, bucket rare
    agencies, cast categoricals — was duplicated in score_projects.py and
    explain_risks.py
  - combined_importance(): the SHAP time/cost averaging formula, was
    duplicated in 5 places
"""

FEATURE_LABELS = {
    "original_cost": "Sanctioned project cost",
    "log_original_cost": "Project size (log of sanctioned cost)",
    "orig_duration_m": "Original planned duration (months)",
    "approval_to_start_lag_m": "Delay between approval and start (months)",
    "sanction_year": "Year project was sanctioned",
    "cost_per_month_planned": "Planned spend rate (cost / month)",
    "scope_km": "Project length (km)",
    "months_elapsed": "Months elapsed since start",
    "elapsed_ratio": "Time elapsed vs. planned duration",
    "physical_progress": "Physical progress (%)",
    "financial_progress_pct": "Financial progress (spend as % of sanctioned cost)",
    "progress_gap_pct": "Gap between financial and physical progress",
    "months_past_orig_doc": "Months past original completion date",
    "is_past_orig_doc": "Currently past original completion date (Yes/No)",
    "cost_revision_to_date_pct": "Cost already revised upward (%)",
    "doc_slip_to_date_m": "Months already slipped from original completion date",
    "d_physical_progress": "Change in physical progress since last report",
    "d_expenditure": "Change in expenditure since last report",
    "progress_velocity_3m": "3-month rolling progress trend",
    "is_stalled": "Progress and spending both stalled this month",
    "snapshot_index": "Number of monthly reports seen so far",
    "ministry": "Ministry / Department",
    "sector": "Infrastructure sector",
    "state": "State",
    "agency": "Implementing agency",
}
for _kw in ["bridge", "tunnel", "bypass", "greenfield", "upgrade", "epc", "ham",
            "bot", "doubling", "electrification", "metro", "pipeline", "terminal"]:
    FEATURE_LABELS[f"kw_{_kw}"] = f"Project scope mentions '{_kw}'"

CUF_FIELDS = {"original_cost", "physical_progress", "ministry", "sector", "state", "agency"}


def human_label(feature):
    return FEATURE_LABELS.get(feature, feature)


def field_source(feature):
    return "CUF Field" if feature in CUF_FIELDS else "Engineered Feature"


def build_X(df, features, categorical, top_agency):
    """Reindex to a model's exact feature order, bucket rare agencies as
    'Other', cast categorical columns to pandas 'category' dtype."""
    X = df[features].copy()
    if "agency" in X.columns:
        X["agency"] = X["agency"].where(X["agency"].isin(top_agency), "Other")
    for c in categorical:
        X[c] = X[c].astype("category")
    return X


def combined_importance(shap_global):
    """Attach a 'combined' column averaging the time- and cost-model mean |SHAP|."""
    return shap_global.assign(
        combined=(shap_global.mean_abs_shap_time + shap_global.mean_abs_shap_cost) / 2
    )
