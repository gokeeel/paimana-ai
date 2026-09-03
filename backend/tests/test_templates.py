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
