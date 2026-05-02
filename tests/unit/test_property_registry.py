# -*- coding: utf-8 -*-
"""
Property-based tests for the ModelRegistry component.

Validates: Requirement 10.6
"""
from __future__ import annotations

from hypothesis import given, settings
from hypothesis import strategies as st
from unittest.mock import MagicMock

from src.components.model_registry import ModelRegistry
from src.models.data_models import ModelMetadata


DOMAINS = ["intent", "sentiment", "concept", "vectorizer"]

metadata_strategy = st.builds(
    ModelMetadata,
    model_id=st.text(min_size=1, max_size=20, alphabet=st.characters(whitelist_categories=("Lu", "Ll", "Nd"), whitelist_characters="-_")),
    model_version=st.just("1.0.0"),
    domain=st.sampled_from(DOMAINS),
    registered_at=st.just("2026-01-01T00:00:00Z"),
)


# ---------------------------------------------------------------------------
# Property 13: all registered models have required metadata fields
# ---------------------------------------------------------------------------

@given(metas=st.lists(metadata_strategy, min_size=1, max_size=10))
@settings(max_examples=100)
def test_property_registry_metadata_fields_complete(metas):
    """Req 10.6: list_models() returns entries with all required non-null fields."""
    registry = ModelRegistry()
    for meta in metas:
        mock_model = MagicMock()
        registry.register(mock_model, meta)

    listed = registry.list_models()

    # The registry deduplicates by (model_id, version), so the number of
    # listed entries equals the number of unique (model_id, version) pairs.
    unique_keys = {(m.model_id, m.model_version) for m in metas}
    assert len(listed) == len(unique_keys)

    for meta in listed:
        assert meta.model_id, "model_id must not be empty"
        assert meta.model_version, "model_version must not be empty"
        assert meta.domain, "domain must not be empty"
        assert meta.registered_at, "registered_at must not be empty"


@given(metas=st.lists(metadata_strategy, min_size=1, max_size=5))
@settings(max_examples=50)
def test_property_registry_register_then_activate(metas):
    """Registered models can be activated and retrieved."""
    registry = ModelRegistry()
    for meta in metas:
        mock_model = MagicMock()
        registry.register(mock_model, meta)
        registry.activate(meta.model_id, meta.model_version)

        retrieved_model, retrieved_meta = registry.get_active(meta.domain)
        assert retrieved_meta.model_id == meta.model_id
        assert retrieved_meta.model_version == meta.model_version
