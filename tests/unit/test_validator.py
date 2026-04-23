"""
Unit tests for the Validator component.

Covers the four validation rules in order:
  1. INPUT_TOO_SHORT  – text shorter than 3 characters
  2. INPUT_TOO_LONG   – text longer than 50,000 characters
  3. INPUT_EMPTY      – text that is only whitespace
  4. Valid text       – text that passes all rules
"""
import pytest

from src.components.validator import Validator


@pytest.fixture
def validator() -> Validator:
    return Validator()


# ---------------------------------------------------------------------------
# Rule 1: INPUT_TOO_SHORT
# ---------------------------------------------------------------------------

class TestInputTooShort:
    def test_empty_string_is_too_short(self, validator):
        result = validator.validate("")
        assert result.ok is False
        assert result.error_code == "INPUT_TOO_SHORT"
        assert result.error_message == "Input text is too short to analyze"

    def test_one_char_is_too_short(self, validator):
        result = validator.validate("a")
        assert result.ok is False
        assert result.error_code == "INPUT_TOO_SHORT"

    def test_two_chars_is_too_short(self, validator):
        result = validator.validate("ab")
        assert result.ok is False
        assert result.error_code == "INPUT_TOO_SHORT"

    def test_three_chars_is_not_too_short(self, validator):
        result = validator.validate("abc")
        # Should not fail with INPUT_TOO_SHORT (may still be valid)
        assert result.error_code != "INPUT_TOO_SHORT"


# ---------------------------------------------------------------------------
# Rule 2: INPUT_TOO_LONG
# ---------------------------------------------------------------------------

class TestInputTooLong:
    def test_text_over_50000_chars_is_too_long(self, validator):
        long_text = "a" * 50_001
        result = validator.validate(long_text)
        assert result.ok is False
        assert result.error_code == "INPUT_TOO_LONG"
        assert result.error_message == "Input text exceeds maximum allowed length"

    def test_text_at_exactly_50000_chars_is_valid(self, validator):
        text = "a" * 50_000
        result = validator.validate(text)
        assert result.error_code != "INPUT_TOO_LONG"

    def test_text_at_50001_chars_is_too_long(self, validator):
        text = "x" * 50_001
        result = validator.validate(text)
        assert result.ok is False
        assert result.error_code == "INPUT_TOO_LONG"


# ---------------------------------------------------------------------------
# Rule 3: INPUT_EMPTY (whitespace-only)
# ---------------------------------------------------------------------------

class TestInputEmpty:
    def test_spaces_only_is_empty(self, validator):
        result = validator.validate("   ")
        assert result.ok is False
        assert result.error_code == "INPUT_EMPTY"
        assert result.error_message == "Input text contains no analyzable content"

    def test_tabs_only_is_empty(self, validator):
        result = validator.validate("\t\t\t")
        assert result.ok is False
        assert result.error_code == "INPUT_EMPTY"

    def test_newlines_only_is_empty(self, validator):
        result = validator.validate("\n\n\n")
        assert result.ok is False
        assert result.error_code == "INPUT_EMPTY"

    def test_mixed_whitespace_is_empty(self, validator):
        result = validator.validate("  \t \n \r  ")
        assert result.ok is False
        assert result.error_code == "INPUT_EMPTY"


# ---------------------------------------------------------------------------
# Rule 4: Valid text
# ---------------------------------------------------------------------------

class TestValidText:
    def test_normal_sentence_is_valid(self, validator):
        result = validator.validate("Ofrezco el apartamento en USD 180,000.")
        assert result.ok is True
        assert result.error_code is None
        assert result.error_message is None

    def test_minimum_valid_text(self, validator):
        result = validator.validate("abc")
        assert result.ok is True

    def test_text_at_max_length_is_valid(self, validator):
        result = validator.validate("a" * 50_000)
        assert result.ok is True

    def test_text_with_leading_trailing_spaces_but_content_is_valid(self, validator):
        result = validator.validate("  hello world  ")
        assert result.ok is True

    def test_english_text_is_valid(self, validator):
        result = validator.validate("This property is for sale.")
        assert result.ok is True

    def test_mixed_language_text_is_valid(self, validator):
        result = validator.validate("Apartment for sale, precio negociable.")
        assert result.ok is True
