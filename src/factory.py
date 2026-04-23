"""
Factory for creating a fully initialized Analyzer instance.

Loads all serialized ML models from the models/ directory,
registers them in the ModelRegistry, and returns a ready-to-use Analyzer.

Usage:
    from src.factory import create_analyzer
    analyzer = create_analyzer()
    result = analyzer.analyze("Ofrezco apartamento en USD 180,000.")
"""
from __future__ import annotations

import os
from datetime import datetime, timezone

import joblib

from src.analyzer import Analyzer
from src.components.concept_extractor import ConceptExtractor
from src.components.intent_classifier import IntentClassifier
from src.components.model_registry import ModelRegistry
from src.components.sentiment_classifier import SentimentClassifier
from src.components.vectorizer import Vectorizer
from src.models.data_models import ModelMetadata

# Path to the models directory (relative to project root)
_MODELS_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "models")


def _model_path(filename: str) -> str:
    return os.path.join(_MODELS_DIR, filename)


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def create_analyzer(models_dir: str | None = None) -> Analyzer:
    """
    Create and return a fully initialized Analyzer.

    Loads all models from the models/ directory (or models_dir if provided).
    Registers and activates all models in the ModelRegistry.

    Args:
        models_dir: Optional path to the models directory.
                    Defaults to <project_root>/models/

    Returns:
        A ready-to-use Analyzer instance.

    Raises:
        FileNotFoundError: If any required model file is missing.
                           Run `python -m src.training.train_models` first.
    """
    base_dir = models_dir or _MODELS_DIR

    def load(filename: str):
        path = os.path.join(base_dir, filename)
        if not os.path.exists(path):
            raise FileNotFoundError(
                f"Model file not found: {path}\n"
                "Run 'python -m src.training.train_models' to train the models first."
            )
        return joblib.load(path)

    # Load serialized artifacts
    tfidf = load("vectorizer.joblib")
    intent_clf = load("intent_classifier.joblib")
    intent_classes = load("intent_classes.joblib")
    sentiment_clf = load("sentiment_classifier.joblib")
    sentiment_classes = load("sentiment_classes.joblib")
    sales_clf = load("sales_concept_classifier.joblib")
    sales_mlb = load("sales_concept_mlb.joblib")
    re_clf = load("real_estate_concept_classifier.joblib")
    re_mlb = load("real_estate_concept_mlb.joblib")

    # Wrap in component classes
    vectorizer = Vectorizer()
    vectorizer._tfidf = tfidf
    vectorizer._fitted = True

    intent_classifier = IntentClassifier(model=intent_clf, classes=intent_classes)
    sentiment_classifier = SentimentClassifier(model=sentiment_clf, classes=sentiment_classes)
    concept_extractor = ConceptExtractor(
        sales_model=sales_clf,
        sales_mlb=sales_mlb,
        real_estate_model=re_clf,
        real_estate_mlb=re_mlb,
    )

    # Build registry and register all models
    registry = ModelRegistry()
    now = _now_iso()

    registry.register(
        vectorizer,
        ModelMetadata(
            model_id="vectorizer-v1",
            model_version="1.0.0",
            domain="vectorizer",
            registered_at=now,
        ),
    )
    registry.activate("vectorizer-v1", "1.0.0")

    registry.register(
        intent_classifier,
        ModelMetadata(
            model_id="intent-v1",
            model_version="1.0.0",
            domain="intent",
            registered_at=now,
        ),
    )
    registry.activate("intent-v1", "1.0.0")

    registry.register(
        sentiment_classifier,
        ModelMetadata(
            model_id="sentiment-v1",
            model_version="1.0.0",
            domain="sentiment",
            registered_at=now,
        ),
    )
    registry.activate("sentiment-v1", "1.0.0")

    registry.register(
        concept_extractor,
        ModelMetadata(
            model_id="concept-v1",
            model_version="1.0.0",
            domain="concept",
            registered_at=now,
        ),
    )
    registry.activate("concept-v1", "1.0.0")

    return Analyzer(registry=registry)
