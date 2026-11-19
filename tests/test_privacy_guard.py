import pytest
from fastapi import HTTPException

from app.services.privacy_guard import find_residual_categories, require_sanitized_text


def test_detects_obvious_residual_identifiers_without_returning_values():
    categories = find_residual_categories([
        "Employee email jane@example.ca",
        "SIN 130 692 544",
        "Phone 416-555-0134",
        "Postal code M5V 2T6",
    ])
    assert categories == ["email", "SIN-like number", "phone number", "Canadian postal code"]


def test_sanitized_tokens_are_accepted():
    require_sanitized_text(["Employee [DOC_NAME_1], email [DOC_EMAIL_1], phone [DOC_PHONE_1]"], "en")


def test_residual_pii_blocks_cloud_analysis_with_non_sensitive_message():
    with pytest.raises(HTTPException) as exc:
        require_sanitized_text(["Contact Jane at jane@example.ca"], "en")
    assert exc.value.status_code == 422
    assert "jane@example.ca" not in exc.value.detail


def test_residual_pii_message_is_french_when_selected():
    with pytest.raises(HTTPException) as exc:
        require_sanitized_text(["Courriel: jane@example.ca"], "fr")
    assert "renseignements personnels" in exc.value.detail
