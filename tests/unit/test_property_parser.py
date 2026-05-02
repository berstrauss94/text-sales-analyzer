# -*- coding: utf-8 -*-
"""
Property-based tests for the Parser component.

Validates: Requirements 2.1, 2.3, 2.4
"""
from __future__ import annotations

from hypothesis import given, settings
from hypothesis import strategies as st

from src.components.parser import Parser

parser = Parser()

VALID_TEXTS = st.text(
    min_size=3,
    max_size=500,
    alphabet=st.characters(blacklist_categories=("Cs",)),
).filter(lambda t: t.strip() != "")


# ---------------------------------------------------------------------------
# Property 4: all tokens are normalized (lowercase, stripped)
# ---------------------------------------------------------------------------

@given(text=VALID_TEXTS)
@settings(max_examples=200)
def test_property_tokens_are_normalized(text):
    """Req 2.1: every token satisfies token == token.strip().lower()."""
    parsed = parser.parse(text)
    for token in parsed.tokens:
        assert token == token.strip().lower(), (
            f"Token '{token}' is not normalized"
        )


# ---------------------------------------------------------------------------
# Property 5: round-trip parse → print → parse produces same tokens
# ---------------------------------------------------------------------------

@given(text=VALID_TEXTS)
@settings(max_examples=200)
def test_property_roundtrip_parse_print_parse(text):
    """Req 2.3, 2.4: parse(print(parse(text))).tokens == parse(text).tokens."""
    parsed1 = parser.parse(text)
    printed = parser.print(parsed1)
    parsed2 = parser.parse(printed)
    assert parsed1.tokens == parsed2.tokens, (
        f"Round-trip failed.\n"
        f"Original tokens: {parsed1.tokens}\n"
        f"After round-trip: {parsed2.tokens}"
    )


# ---------------------------------------------------------------------------
# Property: tokens are non-empty strings
# ---------------------------------------------------------------------------

@given(text=VALID_TEXTS)
@settings(max_examples=100)
def test_property_tokens_are_non_empty(text):
    """All tokens in the parsed result are non-empty strings."""
    parsed = parser.parse(text)
    for token in parsed.tokens:
        assert isinstance(token, str)
        assert len(token) > 0, "Token must not be empty"
