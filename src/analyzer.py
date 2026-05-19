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

            # Step 5b: If intent is UNKNOWN and text is long, try segmented classification
            if intent_result.intent == "UNKNOWN" and len(parsed_text.tokens) > 100:
                intent_result = self._segmented_intent(
                    text, parsed_text, vectorizer_obj, intent_obj
                )
            if sentiment_result.sentiment == "NEUTRAL" and len(parsed_text.tokens) > 100:
                sentiment_result = self._segmented_sentiment(
                    text, parsed_text, vectorizer_obj, sentiment_obj
                )

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

    def _segmented_intent(self, text, parsed_text, vectorizer_obj, intent_obj):
        """
        For long texts: split into segments, classify each, vote on the result.
        This handles the TF-IDF dilution problem with long documents.
        """
        from src.models.data_models import IntentResult, ParsedText as PT
        from collections import Counter

        # Split tokens into segments of ~80 tokens (similar to training example length)
        tokens = parsed_text.tokens
        segment_size = 80
        segments = [tokens[i:i+segment_size] for i in range(0, len(tokens), segment_size)]

        votes = Counter()
        confidences = []

        for seg_tokens in segments[:20]:  # Max 20 segments to avoid slowness
            if len(seg_tokens) < 10:
                continue
            seg_parsed = PT(original=" ".join(seg_tokens), tokens=seg_tokens, sentences=[seg_tokens])
            try:
                seg_vector = vectorizer_obj.vectorize(seg_parsed)
                seg_result = intent_obj.predict(seg_vector)
                if seg_result.intent != "UNKNOWN":
                    votes[seg_result.intent] += 1
                    confidences.append(seg_result.confidence)
            except Exception:
                continue

        if votes:
            best_intent = votes.most_common(1)[0][0]
            avg_conf = sum(confidences) / len(confidences) if confidences else 0.0
            # Scale confidence by vote proportion
            total_votes = sum(votes.values())
            vote_ratio = votes[best_intent] / total_votes
            final_conf = round(avg_conf * vote_ratio, 4)
            return IntentResult(intent=best_intent, confidence=max(final_conf, 0.15))

        return IntentResult(intent="UNKNOWN", confidence=0.0)

    def _segmented_sentiment(self, text, parsed_text, vectorizer_obj, sentiment_obj):
        """
        For long texts: split into segments, classify each, vote on sentiment.
        """
        from src.models.data_models import SentimentResult, ParsedText as PT
        from collections import Counter

        tokens = parsed_text.tokens
        segment_size = 80
        segments = [tokens[i:i+segment_size] for i in range(0, len(tokens), segment_size)]

        votes = Counter()
        confidences = []

        for seg_tokens in segments[:20]:
            if len(seg_tokens) < 10:
                continue
            seg_parsed = PT(original=" ".join(seg_tokens), tokens=seg_tokens, sentences=[seg_tokens])
            try:
                seg_vector = vectorizer_obj.vectorize(seg_parsed)
                seg_result = sentiment_obj.predict(seg_vector)
                votes[seg_result.sentiment] += 1
                confidences.append(seg_result.confidence)
            except Exception:
                continue

        if votes:
            best_sentiment = votes.most_common(1)[0][0]
            avg_conf = sum(confidences) / len(confidences) if confidences else 0.0
            total_votes = sum(votes.values())
            vote_ratio = votes[best_sentiment] / total_votes
            final_conf = round(avg_conf * vote_ratio, 4)
            return SentimentResult(sentiment=best_sentiment, confidence=max(final_conf, 0.15))

        from src.models.data_models import SentimentResult
        return SentimentResult(sentiment="NEUTRAL", confidence=0.0)
