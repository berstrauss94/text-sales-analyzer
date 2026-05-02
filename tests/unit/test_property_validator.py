# -*- coding: utf-8 -*-
"""
Property-based tests for the Validator component.

Validates: Requirements 1.1, 1.2, 1.3, 1.4
"""
from __future__ import annotations

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from src.components.validator import Validator, MIN_LENGTH, MAX_LENGTH

validator = Validator()


# ---------------------------------------------------------------------------
# Property 1: texts shorter than MIN_LENGTH are always rejected
# ---------------------------------------------------------------------------

@given(text=st.text(max_size=MIN_LENGTH - 1))
@settings(max_examples=200)
def test_property_too_short_always_rejected(text):
    """Req 1.1: any text with len < 3 is rejected with INPUT_TOO_SHORT."""
    result = validator.validate(text)
    assert result.ok is False
    assert result.error_code == "INPUT_TOO_SHORT"


# ---------------------------------------------------------------------------
# Property 2: texts longer than MAX_LENGTH are always rejected
# ---------------------------------------------------------------------------

@given(extra=st.integers(min_value=1, max_value=100))
@settings(max_examples=50)
def test_property_too_long_always_rejected(extra):
    """Req 1.2: any text with len > 50,000 is rejected with INPUT_TOO_LONG.

    Hypothesis cannot generate strings of 50,001+ characters directly, so we
    build the oversized text programmatically using a small random offset.
    """
    text = "a" * (MAX_LENGTH + extra)
    result = validator.validate(text)
    assert result.ok is False
    assert result.error_code == "INPUT_TOO_LONG"


# ---------------------------------------------------------------------------
# Property 3: whitespace-only texts are always rejected
# ---------------------------------------------------------------------------

@given(
    text=st.text(
        alphabet=st.sampled_from([" ", "\t", "\n", "\r"]),
        min_size=MIN_LENGTH,  # ensure length passes the too-short check first
        max_size=100,
    )
)
@settings(max_examples=200)
def test_property_whitespace_only_rejected(text):
    """Req 1.3: whitespace-only text of sufficient length is rejected with INPUT_EMPTY.

    We use min_size=MIN_LENGTH so the text is long enough to pass the
    INPUT_TOO_SHORT check and reach the whitespace-only check.
    """
    result = validator.validate(text)
    assert result.ok is False
    assert result.error_code == "INPUT_EMPTY"


# ---------------------------------------------------------------------------
# Property 4: valid texts pass through unchanged
# ---------------------------------------------------------------------------

@given(
    text=st.text(
        min_size=MIN_LENGTH,
        max_size=5000,
        alphabet=st.characters(blacklist_categories=("Cs",)),
    ).filter(lambda t: t.strip() != "")
)
@settings(max_examples=200)
def test_property_valid_text_passes_unchanged(text):
    """Req 1.4: valid text passes validation with ok=True and no error fields."""
    result = validator.validate(text)
    assert result.ok is True
    assert result.error_code is None
    assert result.error_message is None
