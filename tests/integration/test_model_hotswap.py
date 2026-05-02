# -*- coding: utf-8 -*-
"""
Hot-swap tests for the ModelRegistry.

Validates: Requirements 10.4, 10.5 — a new model version can be registered
and activated without modifying the public analyze() interface or restarting.
"""
from __future__ import annotations

import pytest

from src.factory import create_analyzer
from src.components.model_registry import ModelRegistry
from src.models.data_models import AnalysisReport, ModelMetadata
from src.components.intent_classifier import IntentClassifier


@pytest.fixture(scope="module")
def analyzer():
    return create_analyzer()


def test_hotswap_registers_new_model_version(analyzer):
    """Req 10.4: a new model version can be registered in the registry."""
    registry = analyzer._registry
    models_before = len(registry.list_models())

    # Create a trivial v2 intent classifier (same model, new version)
    active_model, active_meta = registry.get_active("intent")
    new_meta = ModelMetadata(
        model_id="intent-v2",
        model_version="2.0.0",
        domain="intent",
        registered_at="2026-01-01T00:00:00Z",
    )
    registry.register(active_model, new_meta)

    models_after = len(registry.list_models())
    assert models_after == models_before + 1


def test_hotswap_activates_new_version(analyzer):
    """Req 10.5: activating a new version makes analyze() use it immediately."""
    registry = analyzer._registry

    # Register v2 if not already done
    active_model, _ = registry.get_active("intent")
    new_meta = ModelMetadata(
        model_id="intent-v2-swap",
        model_version="2.0.0",
        domain="intent",
        registered_at="2026-01-01T00:00:00Z",
    )
    registry.register(active_model, new_meta)
    registry.activate("intent-v2-swap", "2.0.0")

    # analyze() should still work after hot-swap
    result = analyzer.analyze("Ofrezco apartamento en USD 200,000.")
    assert isinstance(result, AnalysisReport)

    # Restore original
    registry.activate("intent-v1", "1.0.0")


def test_hotswap_no_restart_required(analyzer):
    """Req 10.5: no restart needed — analyze() works before and after swap."""
    text = "Casa de 3 habitaciones en venta, precio negociable."

    result_before = analyzer.analyze(text)
    assert isinstance(result_before, AnalysisReport)

    # Swap and swap back
    registry = analyzer._registry
    active_model, _ = registry.get_active("intent")
    meta = ModelMetadata(
        model_id="intent-tmp",
        model_version="99.0.0",
        domain="intent",
        registered_at="2026-01-01T00:00:00Z",
    )
    registry.register(active_model, meta)
    registry.activate("intent-tmp", "99.0.0")

    result_after = analyzer.analyze(text)
    assert isinstance(result_after, AnalysisReport)

    # Restore
    registry.activate("intent-v1", "1.0.0")


def test_registry_metadata_fields(analyzer):
    """Req 10.6: all registered models have required metadata fields."""
    registry = analyzer._registry
    for meta in registry.list_models():
        assert meta.model_id, "model_id must not be empty"
        assert meta.model_version, "model_version must not be empty"
        assert meta.domain, "domain must not be empty"
        assert meta.registered_at, "registered_at must not be empty"
