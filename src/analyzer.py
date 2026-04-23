"""
Analyzer — main orchestrator for the text sales and real estate analyzer.

Public interface:
    analyze(text: str) -> AnalysisReport | AnalysisError

Each call is completely stateless and independent.
Never raises exceptions to the caller.
"""
from __future__ import annotations

from src.components.concept_extractor import ConceptExtractor
from src.components.intent_classifier import IntentClassifier
from src.components.model_registry import ModelRegistry
from src.components.parser import Parser
from src.components.pretty_printer import PrettyPrinter
from src.components.report_builder import ReportBuilder
from src.components.sentiment_classifier import SentimentClassifier
from src.components.validator import Validator
from src.components.vectorizer import Vectorizer
from src.models.data_models import AnalysisError, AnalysisReport


class Analyzer:
    """
    Orchestrates the full text analysis pipeline.

    Pipeline:
        1. Validate input text
        2. Parse text into tokens and sentences
        3. Retrieve active models from ModelRegistry
        4. Vectorize parsed text
        5. Run ML inference (intent, sentiment, concepts)
        6. Build and return AnalysisReport

    Properties:
    - Stateless: each analyze() call is independent
    - Safe: never raises exceptions to the caller
    - Deterministic: same text + same models → same result
    """

    def __init__(self, registry: ModelRegistry) -> None:
        self._registry = registry
        self._validator = Validator()
        self._parser = Parser()
        self._report_builder = ReportBuilder()
        self._pretty_printer = PrettyPrinter()

    def analyze(self, text: str) -> AnalysisReport | AnalysisError:
        """
        Analyze a text and return a complete AnalysisReport.

        Args:
            text: Any string in Spanish, English, or mixed.

        Returns:
            AnalysisReport on success, AnalysisError on any failure.
            Never raises an exception.
        """
        try:
            # Step 1: Validate
            validation = self._validator.validate(text)
            if not validation.ok:
                return AnalysisError(
                    error_code=validation.error_code or "VALIDATION_ERROR",
                    error_message=validation.error_message or "Validation failed.",
                )

            # Step 2: Parse
            parsed_text = self._parser.parse(text)

            # Step 3: Get active models from registry
            vectorizer_obj, _ = self._registry.get_active("vectorizer")
            intent_obj, _ = self._registry.get_active("intent")
            sentiment_obj, _ = self._registry.get_active("sentiment")
            concept_obj, _ = self._registry.get_active("concept")

            # Step 4: Vectorize
            feature_vector = vectorizer_obj.vectorize(parsed_text)

            # Step 5: ML inference
            intent_result = intent_obj.predict(feature_vector)
            sentiment_result = sentiment_obj.predict(feature_vector)
            concept_result = concept_obj.extract(feature_vector, parsed_text)

            # Step 6: Build report
            report = self._report_builder.build(
                original_text=text,
                parsed_text=parsed_text,
                intent_result=intent_result,
                sentiment_result=sentiment_result,
                concept_result=concept_result,
            )
            return report

        except Exception as exc:
            return AnalysisError(
                error_code="ANALYSIS_ERROR",
                error_message=str(exc) or "An unexpected error occurred during analysis.",
            )
