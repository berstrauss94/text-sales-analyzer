# -*- coding: utf-8 -*-
"""
Integration tests for the full analysis pipeline.

Tests the complete analyze() pipeline end-to-end using property-based
and example-based tests.

Validates: Requirements 3.1, 4.1, 5.1, 6.1, 7.1, 8.1, 8.3,
           9.4, 10.2, 10.4, 10.5, 11.1-11.4, 12.1-12.5
"""
from __future__ import annotations

import re
import time
from datetime import datetime

import pytest
from hypothesis import given, settings, HealthCheck
from hypothesis import strategies as st

from src.factory import create_analyzer
from src.models.data_models import AnalysisError, AnalysisReport

# ---------------------------------------------------------------------------
# Shared fixture — create analyzer once for all tests in this module
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def analyzer():
    return create_analyzer()


# ---------------------------------------------------------------------------
# Property test 6: vocabulary of classifications
# ---------------------------------------------------------------------------

VALID_INTENTS = {"OFFER", "INQUIRY", "NEGOTIATION", "CLOSING", "DESCRIPTION", "UNKNOWN"}
VALID_SENTIMENTS = {"POSITIVE", "NEUTRAL", "NEGATIVE"}

VALID_TEXTS = st.text(
    min_size=3,
    max_size=500,
    alphabet=st.characters(blacklist_categories=("Cs",)),
).filter(lambda t: t.strip() != "")


@given(text=VALID_TEXTS)
@settings(max_examples=50, suppress_health_check=[HealthCheck.too_slow], deadline=None)
def test_intent_and_sentiment_vocabulary(text):
    """Property 6: intent and sentiment are always valid vocabulary values."""
    anlzr = create_analyzer()
    result = anlzr.analyze(text)
    if isinstance(result, AnalysisReport):
        assert result.intent in VALID_INTENTS, f"Invalid intent: {result.intent}"
        assert result.sentiment in VALID_SENTIMENTS, f"Invalid sentiment: {result.sentiment}"


# ---------------------------------------------------------------------------
# Property test 7: confidence scores in [0, 1]
# ---------------------------------------------------------------------------

@given(text=VALID_TEXTS)
@settings(max_examples=50, suppress_health_check=[HealthCheck.too_slow])
def test_confidence_scores_in_range(text):
    """Property 7: all confidence scores are in [0.0, 1.0]."""
    anlzr = create_analyzer()
    result = anlzr.analyze(text)
    if isinstance(result, AnalysisReport):
        assert 0.0 <= result.intent_confidence <= 1.0
        assert 0.0 <= result.sentiment_confidence <= 1.0
        for c in result.sales_concepts:
            assert 0.0 <= c.confidence <= 1.0, f"Sales concept confidence out of range: {c}"
        for c in result.real_estate_concepts:
            assert 0.0 <= c.confidence <= 1.0, f"RE concept confidence out of range: {c}"


# ---------------------------------------------------------------------------
# Property test 8: raw_value is a substring of the original text
# ---------------------------------------------------------------------------

@given(text=VALID_TEXTS)
@settings(max_examples=50, suppress_health_check=[HealthCheck.too_slow])
def test_entity_raw_value_is_substring(text):
    """Property 8: every Entity.raw_value is a substring of the original text."""
    anlzr = create_analyzer()
    result = anlzr.analyze(text)
    if isinstance(result, AnalysisReport):
        for entity in result.entities:
            assert entity.raw_value in result.input_text, (
                f"Entity raw_value '{entity.raw_value}' not found in original text"
            )


# ---------------------------------------------------------------------------
# Property test 10: complete report structure
# ---------------------------------------------------------------------------

ISO_8601_RE = re.compile(
    r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$"
)


@given(text=VALID_TEXTS)
@settings(max_examples=50, suppress_health_check=[HealthCheck.too_slow])
def test_report_structure_complete(text):
    """Property 10: all required fields present, non-None, analyzed_at is ISO 8601."""
    anlzr = create_analyzer()
    result = anlzr.analyze(text)
    if isinstance(result, AnalysisReport):
        assert result.input_text is not None
        assert result.intent is not None
        assert result.sentiment is not None
        assert result.sales_concepts is not None
        assert result.real_estate_concepts is not None
        assert result.entities is not None
        assert result.analyzed_at is not None
        assert ISO_8601_RE.match(result.analyzed_at), (
            f"analyzed_at is not ISO 8601: {result.analyzed_at}"
        )


# ---------------------------------------------------------------------------
# Property test 11: no unhandled exceptions for any string input
# ---------------------------------------------------------------------------

@given(text=st.text(max_size=1000))
@settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
def test_no_unhandled_exceptions(text):
    """Property 11: analyze() never raises — always returns Report or Error."""
    anlzr = create_analyzer()
    try:
        result = anlzr.analyze(text)
        assert isinstance(result, (AnalysisReport, AnalysisError)), (
            f"analyze() returned unexpected type: {type(result)}"
        )
    except Exception as exc:
        pytest.fail(f"analyze() raised an exception: {exc}")


# ---------------------------------------------------------------------------
# Property test 12: determinism and statelessness
# ---------------------------------------------------------------------------

@given(text=VALID_TEXTS)
@settings(max_examples=30, suppress_health_check=[HealthCheck.too_slow])
def test_determinism(text):
    """Property 12a: same text always produces same intent, sentiment, concepts."""
    anlzr = create_analyzer()
    r1 = anlzr.analyze(text)
    r2 = anlzr.analyze(text)
    if isinstance(r1, AnalysisReport) and isinstance(r2, AnalysisReport):
        assert r1.intent == r2.intent
        assert r1.sentiment == r2.sentiment
        assert [c.concept for c in r1.sales_concepts] == [c.concept for c in r2.sales_concepts]
        assert [c.concept for c in r1.real_estate_concepts] == [c.concept for c in r2.real_estate_concepts]


@given(
    text_a=VALID_TEXTS,
    text_b=VALID_TEXTS,
)
@settings(max_examples=20, suppress_health_check=[HealthCheck.too_slow])
def test_statelessness_no_cross_contamination(text_a, text_b):
    """Property 12b: analyze(tA), analyze(tB), analyze(tA) → same result for tA."""
    anlzr = create_analyzer()
    r1 = anlzr.analyze(text_a)
    anlzr.analyze(text_b)  # intermediate call with different text
    r3 = anlzr.analyze(text_a)
    if isinstance(r1, AnalysisReport) and isinstance(r3, AnalysisReport):
        assert r1.intent == r3.intent
        assert r1.sentiment == r3.sentiment


# ---------------------------------------------------------------------------
# Example-based integration tests
# ---------------------------------------------------------------------------

def test_offer_text_returns_report(analyzer):
    """A clear offer text returns a valid AnalysisReport."""
    result = analyzer.analyze("Ofrezco apartamento de 3 habitaciones en USD 180,000 negociable.")
    assert isinstance(result, AnalysisReport)
    assert result.intent in VALID_INTENTS
    assert result.sentiment in VALID_SENTIMENTS


def test_invalid_short_text_returns_error(analyzer):
    """Text shorter than 3 chars returns AnalysisError."""
    result = analyzer.analyze("Hi")
    assert isinstance(result, AnalysisError)
    assert result.error_code == "INPUT_TOO_SHORT"


def test_whitespace_only_returns_error(analyzer):
    """Whitespace-only text returns AnalysisError."""
    result = analyzer.analyze("     ")
    assert isinstance(result, AnalysisError)
    assert result.error_code == "INPUT_EMPTY"


def test_too_long_text_returns_error(analyzer):
    """Text over 50,000 chars returns AnalysisError."""
    result = analyzer.analyze("a" * 50_001)
    assert isinstance(result, AnalysisError)
    assert result.error_code == "INPUT_TOO_LONG"


def test_english_text_produces_valid_report(analyzer):
    """English text produces a valid report (Req 12.3)."""
    result = analyzer.analyze("This 3-bedroom house is for sale at USD 250,000.")
    assert isinstance(result, AnalysisReport)
    assert result.intent in VALID_INTENTS


def test_mixed_language_text(analyzer):
    """Mixed Spanish/English text produces a valid report (Req 12.3)."""
    result = analyzer.analyze("Apartment for sale, precio negociable, 3 habitaciones.")
    assert isinstance(result, AnalysisReport)


def test_numeric_entities_extracted(analyzer):
    """Text with price and area produces corresponding entities."""
    result = analyzer.analyze(
        "Vendo casa de 95 m2 en USD 180,000, zona norte, 3 habitaciones."
    )
    assert isinstance(result, AnalysisReport)
    entity_concepts = [e.concept for e in result.entities]
    assert "price" in entity_concepts
    assert "area_sqm" in entity_concepts


def test_input_text_preserved_in_report(analyzer):
    """The input_text field matches the original text exactly (Req 7.1)."""
    text = "Ofrezco apartamento en USD 200,000."
    result = analyzer.analyze(text)
    assert isinstance(result, AnalysisReport)
    assert result.input_text == text


def test_analyzed_at_is_iso8601(analyzer):
    """analyzed_at is a valid ISO 8601 UTC timestamp (Req 7.1)."""
    result = analyzer.analyze("Casa de 3 habitaciones en venta.")
    assert isinstance(result, AnalysisReport)
    assert ISO_8601_RE.match(result.analyzed_at)
