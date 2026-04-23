# -*- coding: utf-8 -*-
"""
Pretty printer component for the text sales and real estate analyzer.

Serializes AnalysisReport to JSON or human-readable plain text.
Guarantees round-trip: from_json(to_json(report)) produces an equivalent object.
"""
from __future__ import annotations

import json
from dataclasses import asdict

from src.models.data_models import (
    AnalysisError,
    AnalysisReport,
    ConceptMatch,
    Entity,
)


class PrettyPrinter:
    """
    Serializes and deserializes AnalysisReport objects.

    Supports:
    - to_json(): deterministic JSON serialization
    - from_json(): exact inverse of to_json()
    - to_text(): human-readable plain text summary
    """

    def to_json(self, report: AnalysisReport) -> str:
        """
        Serialize an AnalysisReport to a valid JSON string.

        Uses dataclasses.asdict for deterministic field ordering.
        Guarantees round-trip: from_json(to_json(r)) == r (field-by-field).
        """
        data = asdict(report)
        return json.dumps(data, ensure_ascii=True, indent=2, sort_keys=True)

    def from_json(self, json_str: str) -> AnalysisReport:
        """
        Deserialize an AnalysisReport from a JSON string.

        Exact inverse of to_json().
        """
        data = json.loads(json_str)

        sales_concepts = [
            ConceptMatch(**c) for c in data.get("sales_concepts", [])
        ]
        real_estate_concepts = [
            ConceptMatch(**c) for c in data.get("real_estate_concepts", [])
        ]
        entities = [
            Entity(**e) for e in data.get("entities", [])
        ]

        return AnalysisReport(
            input_text=data["input_text"],
            intent=data["intent"],
            intent_confidence=data["intent_confidence"],
            sentiment=data["sentiment"],
            sentiment_confidence=data["sentiment_confidence"],
            sales_concepts=sales_concepts,
            real_estate_concepts=real_estate_concepts,
            entities=entities,
            analyzed_at=data["analyzed_at"],
        )

    def to_text(self, report: AnalysisReport) -> str:
        """
        Serialize an AnalysisReport to a human-readable plain text summary.

        Includes intent, sentiment, detected concepts, and extracted entities.
        """
        lines: list[str] = []
        sep = "-" * 60

        lines.append(sep)
        lines.append("ANALISIS DE TEXTO - VENTAS Y BIENES RAICES")
        lines.append(sep)

        # Input text (truncated if long)
        preview = report.input_text[:120]
        if len(report.input_text) > 120:
            preview += "..."
        lines.append("Texto    : " + preview)
        lines.append("Analizado: " + report.analyzed_at)
        lines.append("")

        # Intent
        lines.append(
            "Intencion   : " + report.intent +
            " (confianza: " + f"{report.intent_confidence:.0%}" + ")"
        )

        # Sentiment
        lines.append(
            "Sentimiento : " + report.sentiment +
            " (confianza: " + f"{report.sentiment_confidence:.0%}" + ")"
        )

        # Sales concepts
        lines.append("")
        if report.sales_concepts:
            lines.append("Conceptos de Ventas:")
            for c in report.sales_concepts:
                lines.append(
                    "  - " + c.concept.ljust(20) +
                    f"{c.confidence:.0%}".rjust(5) +
                    '  "' + c.source_text[:40] + '"'
                )
        else:
            lines.append("Conceptos de Ventas: (ninguno detectado)")

        # Real estate concepts
        lines.append("")
        if report.real_estate_concepts:
            lines.append("Conceptos de Bienes Raices:")
            for c in report.real_estate_concepts:
                lines.append(
                    "  - " + c.concept.ljust(20) +
                    f"{c.confidence:.0%}".rjust(5) +
                    '  "' + c.source_text[:40] + '"'
                )
        else:
            lines.append("Conceptos de Bienes Raices: (ninguno detectado)")

        # Entities
        lines.append("")
        if report.entities:
            lines.append("Entidades Extraidas:")
            for e in report.entities:
                val_str = ""
                if e.numeric_value is not None:
                    val_str = " = " + f"{e.numeric_value:,.0f}"
                    if e.unit:
                        val_str += " " + e.unit
                lines.append(
                    "  - " + e.concept.ljust(15) +
                    ' "' + e.raw_value + '"' + val_str
                )
        else:
            lines.append("Entidades Extraidas: (ninguna detectada)")

        lines.append(sep)
        return "\n".join(lines)

    def error_to_text(self, error: AnalysisError) -> str:
        """Format an AnalysisError as a readable string."""
        return "[ERROR " + error.error_code + "] " + error.error_message
