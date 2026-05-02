# -*- coding: utf-8 -*-
"""
Concurrency tests for the analysis pipeline.

Validates: Requirement 11.4 — concurrent analyze() calls with different
texts produce independent results without cross-contamination.
"""
from __future__ import annotations

import concurrent.futures

import pytest

from src.factory import create_analyzer
from src.models.data_models import AnalysisReport

TEXTS = [
    "Ofrezco apartamento de 3 habitaciones en USD 180,000.",
    "What is the asking price for this property?",
    "Podriamos negociar si bajas el precio un 10%.",
    "Firmamos el contrato el proximo lunes, precio final acordado.",
    "Hermosa casa con piscina y jardin en zona residencial.",
    "I have a qualified buyer interested in this listing.",
    "El cliente objeta el precio, dice que es muy alto.",
    "Vendo terreno de 500 m2 en zona comercial.",
    "The property has 4 bedrooms and 3 bathrooms.",
    "Excelente inversion, la zona esta en pleno crecimiento.",
]


@pytest.fixture(scope="module")
def analyzer():
    return create_analyzer()


def test_concurrent_10_calls_independent(analyzer):
    """Req 11.4: 10 concurrent calls produce independent results."""
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        futures = {
            executor.submit(analyzer.analyze, text): text
            for text in TEXTS
        }
        results = {}
        for future in concurrent.futures.as_completed(futures):
            text = futures[future]
            result = future.result()
            results[text] = result

    # All calls completed
    assert len(results) == len(TEXTS)

    # All results are valid types
    for text, result in results.items():
        assert isinstance(result, AnalysisReport), (
            f"Expected AnalysisReport for '{text[:40]}', got {type(result)}"
        )

    # No cross-contamination: input_text matches the text that was analyzed
    for text, result in results.items():
        assert result.input_text == text, (
            f"Cross-contamination detected: input_text '{result.input_text[:40]}' "
            f"does not match submitted text '{text[:40]}'"
        )


def test_concurrent_same_text_deterministic(analyzer):
    """Req 11.2 + 11.4: concurrent calls with same text produce identical results."""
    text = "Ofrezco casa de 3 habitaciones en USD 200,000 negociable."

    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        futures = [executor.submit(analyzer.analyze, text) for _ in range(5)]
        results = [f.result() for f in concurrent.futures.as_completed(futures)]

    reports = [r for r in results if isinstance(r, AnalysisReport)]
    assert len(reports) == 5

    # All should have same intent and sentiment
    intents = {r.intent for r in reports}
    sentiments = {r.sentiment for r in reports}
    assert len(intents) == 1, f"Non-deterministic intents in concurrent calls: {intents}"
    assert len(sentiments) == 1, f"Non-deterministic sentiments in concurrent calls: {sentiments}"
