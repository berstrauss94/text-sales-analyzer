"""
Model Registry component for the text sales and real estate analyzer.

Manages ML model versions and allows hot-swap of models without
modifying the public analyze() interface or restarting the system.

Thread-safe: get_active() reads are atomic reference reads.
activate() updates references atomically.
"""
from __future__ import annotations

import threading
from datetime import datetime, timezone

from src.models.data_models import ModelMetadata


class ModelRegistry:
    """
    Registry for ML models used in the analysis pipeline.

    Supports:
    - Registering new model versions
    - Activating a specific version for inference
    - Hot-swapping models without system restart
    - Listing all registered models with metadata
    """

    def __init__(self) -> None:
        # All registered models: {model_id: {version: (model_object, metadata)}}
        self._registry: dict[str, dict[str, tuple[object, ModelMetadata]]] = {}
        # Active models per domain: {domain: (model_object, metadata)}
        self._active: dict[str, tuple[object, ModelMetadata]] = {}
        self._lock = threading.Lock()

    def register(self, model: object, metadata: ModelMetadata) -> None:
        """
        Register a model with its metadata.

        Does NOT activate the model automatically.
        Call activate() to make it available for inference.

        Args:
            model: The fitted ML model object.
            metadata: ModelMetadata describing the model.
        """
        with self._lock:
            if metadata.model_id not in self._registry:
                self._registry[metadata.model_id] = {}
            self._registry[metadata.model_id][metadata.model_version] = (
                model,
                metadata,
            )

    def activate(self, model_id: str, version: str) -> None:
        """
        Activate a registered model version for inference.

        All subsequent analyze() calls will use this version.
        The switch is atomic — no in-flight requests are interrupted.

        Args:
            model_id: The model identifier.
            version: The version string to activate.

        Raises:
            KeyError: If the model_id or version is not registered.
        """
        with self._lock:
            if model_id not in self._registry:
                raise KeyError(f"Model '{model_id}' is not registered.")
            if version not in self._registry[model_id]:
                raise KeyError(
                    f"Version '{version}' of model '{model_id}' is not registered."
                )

            model_obj, metadata = self._registry[model_id][version]

            # Mark old active model as inactive
            domain = metadata.domain
            if domain in self._active:
                _, old_meta = self._active[domain]
                old_meta.is_active = False

            # Activate new model
            metadata.is_active = True
            self._active[domain] = (model_obj, metadata)

    def get_active(self, domain: str) -> tuple[object, ModelMetadata]:
        """
        Return the active model and its metadata for the given domain.

        Thread-safe: reads the active reference atomically.

        Args:
            domain: One of "vectorizer", "intent", "sentiment",
                    "concept_sales", "concept_real_estate".

        Returns:
            Tuple of (model_object, ModelMetadata).

        Raises:
            KeyError: If no model is active for the given domain.
        """
        # Read without lock for performance (reference read is atomic in CPython)
        active = self._active.get(domain)
        if active is None:
            raise KeyError(
                f"No active model for domain '{domain}'. "
                "Register and activate a model first."
            )
        return active

    def list_models(self) -> list[ModelMetadata]:
        """
        Return metadata for all registered models.

        Returns:
            List of ModelMetadata objects, one per registered version.
        """
        with self._lock:
            result: list[ModelMetadata] = []
            for versions in self._registry.values():
                for _, metadata in versions.values():
                    result.append(metadata)
            return result
