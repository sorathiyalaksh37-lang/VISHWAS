"""
Task 1: Tests for verification schema validation.

Tests ensure verification_obj matches Verification schema contract:
- action: Optional[str] (e.g. "CALL_BACK", "VERIFY_SAFE_WORD")
- target: Optional[str] (formatted contact info)
- safe_word_prompt: Optional[bool]

All fields are optional per schema definition, but type validation applies when provided.

Testing scenarios:
1. Valid verification object creation with all fields
2. Valid verification with only some fields
3. Valid verification with no fields (all None)
4. Invalid field types when provided
5. Edge cases (empty strings, unknown caller scenarios)
"""
import pytest
from app.schemas.report import Verification
from pydantic import ValidationError


def test_verification_valid_with_all_fields():
    """Test valid verification object with all required fields."""
    verification = Verification(
        action="CALL_BACK",
        target="Mom (saved: +91-98xxxx)",
        safe_word_prompt=True
    )
    assert verification.action == "CALL_BACK"
    assert verification.target == "Mom (saved: +91-98xxxx)"
    assert verification.safe_word_prompt is True


def test_verification_valid_minimal():
    """Test valid verification with minimal fields."""
    verification = Verification(
        action="VERIFY_SAFE_WORD",
        target="Unknown caller",
        safe_word_prompt=False
    )
    assert verification.action == "VERIFY_SAFE_WORD"
    assert verification.target == "Unknown caller"
    assert verification.safe_word_prompt is False


def test_verification_all_fields_none():
    """Test valid verification with all fields as None (optional schema)."""
    verification = Verification(
        action=None,
        target=None,
        safe_word_prompt=None
    )
    assert verification.action is None
    assert verification.target is None
    assert verification.safe_word_prompt is None


def test_verification_partial_fields():
    """Test valid verification with only some fields provided."""
    verification = Verification(
        action="CALL_BACK",
        target="Mom (saved: +91-98xxxx)"
        # safe_word_prompt omitted
    )
    assert verification.action == "CALL_BACK"
    assert verification.target == "Mom (saved: +91-98xxxx)"
    assert verification.safe_word_prompt is None


def test_verification_empty_dict():
    """Test verification can be created with no arguments (all optional)."""
    verification = Verification()
    assert verification.action is None
    assert verification.target is None
    assert verification.safe_word_prompt is None


def test_verification_invalid_action_type():
    """Test that non-string action raises validation error."""
    with pytest.raises(ValidationError) as exc_info:
        Verification(
            action=123,  # Should be string or None
            target="Mom (saved: +91-98xxxx)",
            safe_word_prompt=True
        )
    errors = exc_info.value.errors()
    assert any("action" in e["loc"] for e in errors)


def test_verification_invalid_target_type():
    """Test that non-string target raises validation error."""
    with pytest.raises(ValidationError) as exc_info:
        Verification(
            action="CALL_BACK",
            target=["Mom", "+91-98xxxx"],  # Should be string or None
            safe_word_prompt=True
        )
    errors = exc_info.value.errors()
    assert any("target" in e["loc"] for e in errors)


def test_verification_invalid_safe_word_prompt_type():
    """Test that invalid safe_word_prompt type coerces or raises error."""
    # Pydantic may coerce "yes" to bool, so test with clearly invalid type
    with pytest.raises(ValidationError) as exc_info:
        Verification(
            action="CALL_BACK",
            target="Mom (saved: +91-98xxxx)",
            safe_word_prompt=["invalid"]  # Should be bool or None
        )
    errors = exc_info.value.errors()
    assert any("safe_word_prompt" in e["loc"] for e in errors)


def test_verification_empty_strings():
    """Test verification with empty strings (valid but possibly problematic)."""
    verification = Verification(
        action="",
        target="",
        safe_word_prompt=False
    )
    assert verification.action == ""
    assert verification.target == ""
    assert verification.safe_word_prompt is False


def test_verification_unknown_caller_scenario():
    """Test verification for unknown caller scenario."""
    verification = Verification(
        action="VERIFY_IDENTITY",
        target="Unknown number (+91-98xxxxxx)",
        safe_word_prompt=False
    )
    assert verification.action == "VERIFY_IDENTITY"
    assert "Unknown" in verification.target
    assert verification.safe_word_prompt is False


def test_verification_safe_word_available_scenario():
    """Test verification when safe word is enrolled for contact."""
    verification = Verification(
        action="VERIFY_SAFE_WORD",
        target="Dad (saved: +91-99xxxx)",
        safe_word_prompt=True
    )
    assert verification.action == "VERIFY_SAFE_WORD"
    assert verification.safe_word_prompt is True


def test_verification_no_contact_match_scenario():
    """Test verification when no contact match found."""
    verification = Verification(
        action="BLOCK",
        target="Unrecognized caller",
        safe_word_prompt=False
    )
    assert verification.action == "BLOCK"
    assert "Unrecognized" in verification.target or "Unknown" in verification.target or verification.target == "Unrecognized caller"


def test_verification_dict_construction():
    """Test that verification can be constructed from dict (for JSON deserialization)."""
    data = {
        "action": "CALL_BACK",
        "target": "Sister (saved: +91-97xxxx)",
        "safe_word_prompt": True
    }
    verification = Verification(**data)
    assert verification.action == "CALL_BACK"
    assert verification.target == "Sister (saved: +91-97xxxx)"
    assert verification.safe_word_prompt is True


def test_verification_dict_partial():
    """Test verification from dict with missing fields."""
    data = {
        "action": "VERIFY_IDENTITY"
        # target and safe_word_prompt missing
    }
    verification = Verification(**data)
    assert verification.action == "VERIFY_IDENTITY"
    assert verification.target is None
    assert verification.safe_word_prompt is None
