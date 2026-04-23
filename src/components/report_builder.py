"""
Report builder component for the text sales and real estate analyzer.

Assembles the final AnalysisReport from all pipeline results.
"""
from __future__ import annotations

from datetime import datetime, timezone

from src.models.data_models import (
    AnalysisReport,
    ConceptResult,
    IntentResult,
    ParsedText,
    SentimentResult,
)


class ReportBuilder:
    """
    Assembles an AnalysisReport from the outputs of all pipeline components.

    Guarantees that all fields in the report are populated (no None values).
    """

    def build(
        self,
        original_text: str,
        parsed_text: ParsedText,
        intent_result: IntentResult,
        sentiment_result: SentimentResult,
        concept_result: ConceptResult,
    ) -> AnalysisReport:
        """
        Build and return a complete AnalysisReport.

        Args:
            original_text: The raw input text as provided by the caller.
            parsed_text: The structured parsed representation.
            intent_result: Classification result from IntentClassifier.
            sentiment_result: Classification result from SentimentClassifier.
            concept_result: Extraction result from ConceptExtractor.

        Returns:
            A fully populated AnalysisReport with an ISO 8601 UTC timestamp.
        """
        analyzed_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

        return AnalysisReport(
            input_text=original_text,
            intent=intent_result.intent,
            intent_confidence=intent_result.confidence,
            sentiment=sentiment_result.sentiment,
            sentiment_confidence=sentiment_result.confidence,
            sales_concepts=concept_result.sales_concepts,
            real_estate_concepts=concept_result.real_estate_concepts,
            entities=concept_result.entities,
            analyzed_at=analyzed_at,
        )
