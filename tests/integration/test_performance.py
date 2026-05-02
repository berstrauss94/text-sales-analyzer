# -*- coding: utf-8 -*-
"""
Performance tests for the analysis pipeline.

Validates: Requirement 9.4 — analyze() on text up to 5,000 chars
completes within 2 seconds on standard hardware.
"""
from __future__ import annotations

import time

import pytest

from src.factory import create_analyzer
from src.models.data_models import AnalysisReport


@pytest.fixture(scope="module")
def analyzer():
    return create_analyzer()


def test_performance_5000_chars(analyzer):
    """Req 9.4: analyze() on 5,000-char text completes in under 2 seconds."""
    # Build a realistic 5,000-char text
    base = (
        "Ofrezco apartamento de 3 habitaciones en USD 180,000 negociable. "
        "La propiedad tiene 95 m2, piscina, gimnasio y seguridad 24 horas. "
        "Ubicado en Zona Norte, excelente estado, listo para habitar. "
    )
    text = (base * 30)[:5000]
    assert len(text) <= 5000

    start = time.perf_counter()
    result = analyzer.analyze(text)
    elapsed = time.perf_counter() - start

    assert isinstance(result, AnalysisReport), f"Expected AnalysisReport, got {type(result)}"
    assert elapsed < 2.0, f"analyze() took {elapsed:.2f}s, expected < 2.0s"


def test_performance_1000_chars(analyzer):
    """analyze() on 1,000-char text completes well under 2 seconds."""
    text = (
        "Casa de 4 habitaciones con piscina y jardin en zona residencial. "
        "Precio: USD 250,000 negociable. Metraje: 200 m2. "
    ) * 8
    text = text[:1000]

    start = time.perf_counter()
    result = analyzer.analyze(text)
    elapsed = time.perf_counter() - start

    assert isinstance(result, AnalysisReport)
    assert elapsed < 2.0, f"analyze() took {elapsed:.2f}s"
