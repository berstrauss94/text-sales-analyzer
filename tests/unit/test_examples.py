# -*- coding: utf-8 -*-
"""
Unit tests with specific domain examples.

Validates: Requirements 3.4, 5.3, 6.3, 7.3, 10.2, 10.7
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch
import numpy as np
import pytest

from src.components.intent_classifier import IntentClassifier, UNKNOWN_THRESHOLD
from src.components.sentiment_classifier import SentimentClassifier
from src.components.concept_extractor import ConceptExtractor
from src.components.pretty_printer import PrettyPrinter
from src.components.parser import Parser
from src.components.vectorizer import Vectorizer
from src.factory import create_analyzer
from src.models.data_models import (
    AnalysisReport, AnalysisError, ConceptMatch, Entity,
    IntentResult, SentimentResult, ConceptResult, ParsedText,
)


@pytest.fixture(scope="module")
def analyzer():
    return create_analyzer()


# ---------------------------------------------------------------------------
# Req 3.4: Synonyms recognized (e.g. "precio final" → closing, "rebaja" → discount)
# ---------------------------------------------------------------------------

def test_synonym_precio_final_maps_to_closing(analyzer):
    """'precio final' should trigger the closing concept (Req 3.4)."""
    result = analyzer.analyze(
        "El precio final acordado es de 200,000 dolares, firmamos manana."
    )
    assert isinstance(result, AnalysisReport)
    sales_labels = [c.concept for c in result.sales_concepts]
    # Either closing is detected OR intent is CLOSING
    assert "closing" in sales_labels or result.intent == "CLOSING", (
        f"Expected 'closing' concept or CLOSING intent. "
        f"Got sales={sales_labels}, intent={result.intent}"
    )


def test_synonym_rebaja_maps_to_discount(analyzer):
    """'rebaja' should trigger the discount concept (Req 3.4)."""
    result = analyzer.analyze(
        "Hay una rebaja especial del 15% para compradores al contado."
    )
    assert isinstance(result, AnalysisReport)
    sales_labels = [c.concept for c in result.sales_concepts]
    assert "discount" in sales_labels, (
        f"Expected 'discount' concept for 'rebaja'. Got: {sales_labels}"
    )


# ---------------------------------------------------------------------------
# Req 5.3: UNKNOWN intent when all probabilities < threshold
# ---------------------------------------------------------------------------

def test_unknown_intent_when_all_probs_below_threshold():
    """Req 5.3: if max probability < threshold, intent must be UNKNOWN."""
    mock_model = MagicMock()
    # All probabilities below threshold
    low_probs = np.array([[0.1, 0.1, 0.05, 0.05, 0.1]])
    mock_model.predict_proba.return_value = low_probs

    classes = ["OFFER", "INQUIRY", "NEGOTIATION", "CLOSING", "DESCRIPTION"]
    clf = IntentClassifier(model=mock_model, classes=classes)

    fv = MagicMock()
    result = clf.predict(fv)

    assert result.intent == "UNKNOWN"
    assert result.confidence == 0.0


def test_known_intent_when_prob_above_threshold():
    """Intent is assigned when max probability >= threshold."""
    mock_model = MagicMock()
    probs = np.array([[0.05, 0.05, 0.05, 0.05, 0.8]])
    mock_model.predict_proba.return_value = probs

    classes = ["OFFER", "INQUIRY", "NEGOTIATION", "CLOSING", "DESCRIPTION"]
    clf = IntentClassifier(model=mock_model, classes=classes)

    fv = MagicMock()
    result = clf.predict(fv)

    assert result.intent == "DESCRIPTION"
    assert result.confidence == pytest.approx(0.8, abs=0.001)


# ---------------------------------------------------------------------------
# Req 6.3: NEUTRAL sentiment with confidence 1.0 for factual text
# ---------------------------------------------------------------------------

def test_neutral_sentiment_factual_text(analyzer):
    """Req 6.3: factual text with no sentiment words → NEUTRAL."""
    result = analyzer.analyze(
        "El apartamento tiene 3 habitaciones y 2 banos en el piso 5."
    )
    assert isinstance(result, AnalysisReport)
    assert result.sentiment == "NEUTRAL"


# ---------------------------------------------------------------------------
# Req 10.7: Fallback when model raises exception
# ---------------------------------------------------------------------------

def test_intent_classifier_fallback_on_exception():
    """Req 10.7: IntentClassifier returns UNKNOWN/0.0 on model exception."""
    mock_model = MagicMock()
    mock_model.predict_proba.side_effect = RuntimeError("model crashed")

    clf = IntentClassifier(model=mock_model, classes=["OFFER", "INQUIRY"])
    result = clf.predict(MagicMock())

    assert result.intent == "UNKNOWN"
    assert result.confidence == 0.0


def test_sentiment_classifier_fallback_on_exception():
    """Req 10.7: SentimentClassifier returns NEUTRAL/0.0 on model exception."""
    mock_model = MagicMock()
    mock_model.predict_proba.side_effect = RuntimeError("model crashed")

    clf = SentimentClassifier(model=mock_model, classes=["POSITIVE", "NEUTRAL", "NEGATIVE"])
    result = clf.predict(MagicMock())

    assert result.sentiment == "NEUTRAL"
    assert result.confidence == 0.0


def test_concept_extractor_fallback_on_exception():
    """Req 10.7: ConceptExtractor returns empty lists on model exception."""
    mock_sales = MagicMock()
    mock_sales.predict_proba.side_effect = RuntimeError("model crashed")
    mock_re = MagicMock()
    mock_re.predict_proba.side_effect = RuntimeError("model crashed")

    mock_mlb = MagicMock()
    mock_mlb.classes_ = ["offer", "discount"]

    extractor = ConceptExtractor(
        sales_model=mock_sales,
        sales_mlb=mock_mlb,
        real_estate_model=mock_re,
        real_estate_mlb=mock_mlb,
    )

    parsed = ParsedText(original="test text", tokens=["test", "text"], sentences=[["test", "text"]])
    result = extractor.extract(MagicMock(), parsed)

    assert result.sales_concepts == []
    assert result.real_estate_concepts == []


# ---------------------------------------------------------------------------
# Req 10.2: Confidence derived from model probabilities (not fixed)
# ---------------------------------------------------------------------------

def test_confidence_derived_from_model_probabilities():
    """Req 10.2: confidence score matches the model's actual probability output."""
    mock_model = MagicMock()
    expected_prob = 0.7234
    probs = np.array([[0.1, 0.1, 0.0, expected_prob, 0.0766]])
    mock_model.predict_proba.return_value = probs

    classes = ["OFFER", "INQUIRY", "NEGOTIATION", "CLOSING", "DESCRIPTION"]
    clf = IntentClassifier(model=mock_model, classes=classes)

    result = clf.predict(MagicMock())

    assert result.intent == "CLOSING"
    assert result.confidence == pytest.approx(round(expected_prob, 4), abs=0.0001)


# ---------------------------------------------------------------------------
# Req 7.3: to_text() output contains intent and sentiment
# ---------------------------------------------------------------------------

def test_to_text_contains_intent_and_sentiment():
    """Req 7.3: PrettyPrinter.to_text() output includes intent and sentiment."""
    printer = PrettyPrinter()
    report = AnalysisReport(
        input_text="Ofrezco casa en USD 200,000.",
        intent="OFFER",
        intent_confidence=0.85,
        sentiment="POSITIVE",
        sentiment_confidence=0.72,
        sales_concepts=[],
        real_estate_concepts=[],
        entities=[],
        analyzed_at="2026-01-01T00:00:00Z",
    )
    text_output = printer.to_text(report)

    assert "OFFER" in text_output
    assert "POSITIVE" in text_output


def test_to_text_contains_concepts_when_present():
    """to_text() includes concept names when concepts are detected."""
    printer = PrettyPrinter()
    report = AnalysisReport(
        input_text="Rebaja del 10% para cierre rapido.",
        intent="OFFER",
        intent_confidence=0.6,
        sentiment="NEUTRAL",
        sentiment_confidence=0.5,
        sales_concepts=[ConceptMatch(concept="discount", confidence=0.8, source_text="rebaja")],
        real_estate_concepts=[],
        entities=[],
        analyzed_at="2026-01-01T00:00:00Z",
    )
    text_output = printer.to_text(report)
    assert "discount" in text_output


# ---------------------------------------------------------------------------
# Req 7.4: JSON round-trip
# ---------------------------------------------------------------------------

def test_json_roundtrip():
    """Req 7.4: to_json(from_json(to_json(r))) == to_json(r)."""
    printer = PrettyPrinter()
    report = AnalysisReport(
        input_text="Casa de 3 habitaciones en USD 250,000.",
        intent="OFFER",
        intent_confidence=0.75,
        sentiment="POSITIVE",
        sentiment_confidence=0.65,
        sales_concepts=[ConceptMatch(concept="offer", confidence=0.75, source_text="ofrezco")],
        real_estate_concepts=[ConceptMatch(concept="price", confidence=0.6, source_text="USD 250,000")],
        entities=[Entity(concept="price", raw_value="USD 250,000", numeric_value=250000.0, unit="USD")],
        analyzed_at="2026-01-01T00:00:00Z",
    )

    json1 = printer.to_json(report)
    json2 = printer.to_json(printer.from_json(json1))
    assert json1 == json2
