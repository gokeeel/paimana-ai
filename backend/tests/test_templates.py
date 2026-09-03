from backend.app.templates import TIER_TO_STATUS, driver_to_sentence


def test_numeric_template_formats_percentage():
    result = driver_to_sentence("elapsed_ratio", "0.5")
    assert result == "The project has used up 50% of its planned schedule."


def test_categorical_template():
    result = driver_to_sentence("agency", "NHAI")
    assert result == "The implementing agency is NHAI."


def test_unknown_feature_returns_none():
    assert driver_to_sentence("kw_bridge", "1") is None


def test_non_numeric_value_for_numeric_template_returns_none():
    assert driver_to_sentence("elapsed_ratio", "not-a-number") is None


def test_missing_value_returns_none():
    assert driver_to_sentence("elapsed_ratio", None) is None


def test_tier_to_status_mapping():
    assert TIER_TO_STATUS == {"Green": "On Track", "Amber": "Needs Attention", "Red": "Critical"}


def test_cost_revision_negative_value_says_revised_down():
    """When cost revision is negative (revised down), assert the right wording."""
    result = driver_to_sentence("cost_revision_to_date_pct", "-27")
    assert result is not None
    assert "-27" not in result  # never show a raw negative number
    assert "27" in result
    assert "down" in result.lower()


def test_doc_slip_negative_value_says_ahead():
    """When doc slip is negative (completion date moved earlier), assert the right wording."""
    result = driver_to_sentence("doc_slip_to_date_m", "-12")
    assert result is not None
    assert "-12" not in result  # never show a raw negative number
    assert "12" in result
    # Should indicate ahead, not behind / slipped
    assert ("ahead" in result.lower()) or ("earlier" in result.lower())


def test_progress_gap_negative_value_says_ahead():
    """When progress gap is negative (physical ahead of financial), assert the right wording."""
    result = driver_to_sentence("progress_gap_pct", "-15")
    assert result is not None
    assert "-15" not in result  # never show a raw negative number
    assert "15" in result
    assert "ahead" in result.lower()
