"""Feature -> plain-English sentence templates. This is the only code
standing between a SHAP driver row and the officer's screen — every
officer-facing endpoint must go through driver_to_sentence(), never expose
a raw feature name or SHAP value directly."""

TIER_TO_STATUS = {"Green": "On Track", "Amber": "Needs Attention", "Red": "Critical"}

NUMERIC_TEMPLATES = {
    "elapsed_ratio": lambda v: f"The project has used up {v * 100:.0f}% of its planned schedule.",
    "doc_slip_to_date_m": lambda v: f"The completion date has already slipped by {v:.0f} months.",
    "progress_gap_pct": lambda v: f"Physical progress is {v:.0f} percentage points behind financial progress.",
    "cost_revision_to_date_pct": lambda v: f"The project cost has already been revised up by {v:.0f}%.",
    "months_past_orig_doc": lambda v: f"The project is {v:.0f} months past its original completion date.",
    "physical_progress": lambda v: f"Physical progress stands at {v:.0f}%.",
    "financial_progress_pct": lambda v: f"{v:.0f}% of the sanctioned budget has been spent.",
    "d_physical_progress": lambda v: f"Physical progress changed by {v:+.1f} points since last month.",
    "progress_velocity_3m": lambda v: (
        f"Progress has been trending {'downward' if v < 0 else 'upward'} over the last 3 months."
    ),
    "orig_duration_m": lambda v: f"The project's original planned duration was {v:.0f} months.",
    "approval_to_start_lag_m": lambda v: (
        f"There was a {v:.0f}-month gap between approval and the actual start."
    ),
}

CATEGORICAL_TEMPLATES = {
    "agency": lambda v: f"The implementing agency is {v}.",
    "ministry": lambda v: f"This falls under {v}.",
    "sector": lambda v: f"This is a {v} sector project.",
    "state": lambda v: f"Located in {v}.",
}


def driver_to_sentence(feature, feature_value):
    """feature_value is the raw value as stored in risk_drivers.feature_value
    (string form, or None). Returns a plain-English sentence, or None if
    this feature has no template — callers must skip None, never fall back
    to showing the raw feature name."""
    if feature_value is None:
        return None
    if feature in NUMERIC_TEMPLATES:
        try:
            v = float(feature_value)
        except (TypeError, ValueError):
            return None
        return NUMERIC_TEMPLATES[feature](v)
    if feature in CATEGORICAL_TEMPLATES:
        return CATEGORICAL_TEMPLATES[feature](feature_value)
    return None
