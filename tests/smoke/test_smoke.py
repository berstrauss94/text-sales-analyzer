# -*- coding: utf-8 -*-
"""
Smoke tests for the analysis pipeline.

Validates: Requirements 9.1, 10.3, 12.5
"""
from __future__ import annotations

import inspect
from unittest.mock import MagicMock, patch, call

import pytest

from src.factory import create_analyzer
from src.analyzer import Analyzer
from src.models.data_models import AnalysisReport, AnalysisError


@pytest.fixture(scope="module")
def analyzer():
    return create_analyzer()


# ---------------------------------------------------------------------------
# Req 9.1: analyze() exists with correct signature
# ---------------------------------------------------------------------------

def test_analyze_function_exists(analyzer):
    """Req 9.1: Analyzer exposes an analyze() method."""
    assert hasattr(analyzer, "analyze"), "Analyzer must have an analyze() method"
    assert callable(analyzer.analyze)


def test_analyze_signature():
    """Req 9.1: analyze() accepts a str parameter and returns Report or Error."""
    sig = inspect.signature(Analyzer.analyze)
    params = list(sig.parameters.keys())
    assert "text" in params, f"analyze() must have a 'text' parameter. Got: {params}"


# ---------------------------------------------------------------------------
# Req 10.3: vectorizer.vectorize() is called before model.predict()
# ---------------------------------------------------------------------------

def test_vectorizer_called_before_predict(analyzer):
    """Req 10.3: pipeline calls vectorize() before any model predict()."""
    call_order = []

    registry = analyzer._registry
    vectorizer_obj, _ = registry.get_active("vectorizer")
    intent_obj, _ = registry.get_active("intent")

    original_vectorize = vectorizer_obj.vectorize
    original_predict = intent_obj.predict

    def spy_vectorize(parsed_text):
        call_order.append("vectorize")
        return original_vectorize(parsed_text)

    def spy_predict(fv):
        call_order.append("predict")
        return original_predict(fv)

    vectorizer_obj.vectorize = spy_vectorize
    intent_obj.predict = spy_predict

    try:
        analyzer.analyze("Ofrezco apartamento en USD 200,000.")
        assert "vectorize" in call_order, "vectorize() was never called"
        assert "predict" in call_order, "predict() was never called"
        vectorize_idx = call_order.index("vectorize")
        predict_idx = call_order.index("predict")
        assert vectorize_idx < predict_idx, (
            f"vectorize() must be called before predict(). "
            f"Order was: {call_order}"
        )
    finally:
        vectorizer_obj.vectorize = original_vectorize
        intent_obj.predict = original_predict


# ---------------------------------------------------------------------------
# Req 12.5: any valid text is analyzable on first submission (no pre-registration)
# ---------------------------------------------------------------------------

def test_new_text_analyzable_without_prior_setup(analyzer):
    """Req 12.5: a brand-new text can be analyzed without any prior setup."""
    unique_text = (
        "Este es un texto completamente nuevo que nunca fue visto antes. "
        "Propiedad en venta por USD 175,000 en zona exclusiva."
    )
    result = analyzer.analyze(unique_text)
    assert isinstance(result, (AnalysisReport, AnalysisError))
    # If valid text, must return a report
    assert isinstance(result, AnalysisReport), (
        f"Expected AnalysisReport for valid text, got AnalysisError: {result}"
    )


def test_create_analyzer_returns_analyzer_instance():
    """create_analyzer() returns a ready-to-use Analyzer."""
    anlzr = create_analyzer()
    assert isinstance(anlzr, Analyzer)


def test_analyze_returns_report_or_error_never_raises(analyzer):
    """analyze() never raises — always returns Report or Error."""
    test_inputs = [
        "Valid text for analysis.",
        "",
        "ab",
        "   ",
        "a" * 50_001,
        "Texto válido con acentos y ñ.",
        "123 456 789",
    ]
    for text in test_inputs:
        try:
            result = analyzer.analyze(text)
            assert isinstance(result, (AnalysisReport, AnalysisError)), (
                f"analyze('{text[:20]}') returned unexpected type: {type(result)}"
            )
        except Exception as exc:
            pytest.fail(f"analyze('{text[:20]}') raised an exception: {exc}")
