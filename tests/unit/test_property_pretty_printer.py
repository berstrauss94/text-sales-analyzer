# -*- coding: utf-8 -*-
"""
Property-based tests for the PrettyPrinter component.

Validates: Requirements 7.2, 7.4
"""
from __future__ import annotations

from hypothesis import given, settings
from hypothesis import strategies as st

from src.components.pretty_printer import PrettyPrinter
from src.models.data_models import AnalysisReport, ConceptMatch, Entity

printer = PrettyPrinter()

INTENTS = ["OFFER", "INQUIRY", "NEGOTIATION", "CLOSING", "DESCRIPTION", "UNKNOWN"]
SENTIMENTS = ["POSITIVE", "NEUTRAL", "NEGATIVE"]

concept_match_strategy = st.builds(
    ConceptMatch,
    concept=st.sampled_from(["offer", "discount", "closing", "price", "location"]),
    confidence=st.floats(min_value=0.0, max_value=1.0, allow_nan=False),
    source_text=st.text(min_size=1, max_size=50),
)

entity_strategy = st.builds(
    Entity,
    concept=st.sampled_from(["price", "area_sqm", "bedrooms", "location"]),
    raw_value=st.text(min_size=1, max_size=30),
    numeric_value=st.one_of(st.none(), st.floats(min_value=0.0, max_value=1e9, allow_nan=False)),
    unit=st.one_of(st.none(), st.sampled_from(["USD", "m2", "sqft"])),
)

report_strategy = st.builds(
    AnalysisReport,
    input_text=st.text(min_size=3, max_size=200),
    intent=st.sampled_from(INTENTS),
    intent_confidence=st.floats(min_value=0.0, max_value=1.0, allow_nan=False),
    sentiment=st.sampled_from(SENTIMENTS),
    sentiment_confidence=st.floats(min_value=0.0, max_value=1.0, allow_nan=False),
    sales_concepts=st.lists(concept_match_strategy, max_size=5),
    real_estate_concepts=st.lists(concept_match_strategy, max_size=5),
    entities=st.lists(entity_strategy, max_size=5),
    analyzed_at=st.just("2026-01-01T00:00:00Z"),
)


# ---------------------------------------------------------------------------
# Property 9: JSON round-trip
# ---------------------------------------------------------------------------

@given(report=report_strategy)
@settings(max_examples=100)
def test_property_json_roundtrip(report):
    """Req 7.2, 7.4: to_json(from_json(to_json(r))) == to_json(r)."""
    json1 = printer.to_json(report)
    json2 = printer.to_json(printer.from_json(json1))
    assert json1 == json2, (
        f"JSON round-trip failed.\nFirst:  {json1[:200]}\nSecond: {json2[:200]}"
    )


@given(report=report_strategy)
@settings(max_examples=100)
def test_property_to_json_is_valid_json(report):
    """Req 7.2: to_json() always produces valid JSON."""
    import json
    json_str = printer.to_json(report)
    # Should not raise
    parsed = json.loads(json_str)
    assert isinstance(parsed, dict)


@given(report=report_strategy)
@settings(max_examples=50)
def test_property_to_text_contains_intent_and_sentiment(report):
    """Req 7.3: to_text() always contains intent and sentiment values."""
    text_output = printer.to_text(report)
    assert report.intent in text_output, f"Intent '{report.intent}' not in to_text() output"
    assert report.sentiment in text_output, f"Sentiment '{report.sentiment}' not in to_text() output"
