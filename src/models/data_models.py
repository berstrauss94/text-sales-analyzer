"""
Data models for the text sales and real estate analyzer.

All dataclasses used across the pipeline are defined here.
"""
from __future__ import annotations

from dataclasses import dataclass, field


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

@dataclass
class ValidationResult:
    """Result of input text validation."""

    ok: bool
    error_code: str | None = None
    error_message: str | None = None

    @staticmethod
    def success() -> ValidationResult:
        """Return a successful validation result."""
        return ValidationResult(ok=True)

    @staticmethod
    def failure(code: str, message: str) -> ValidationResult:
        """Return a failed validation result with an error code and message."""
        return ValidationResult(ok=False, error_code=code, error_message=message)


# ---------------------------------------------------------------------------
# Parsing
# ---------------------------------------------------------------------------

@dataclass
class ParsedText:
    """Structured representation of a parsed input text."""

    original: str
    tokens: list[str]
    sentences: list[list[str]]


# ---------------------------------------------------------------------------
# Classification results
# ---------------------------------------------------------------------------

@dataclass
class IntentResult:
    """Result of intent classification."""

    intent: str       # "OFFER" | "INQUIRY" | "NEGOTIATION" | "CLOSING" | "DESCRIPTION" | "UNKNOWN"
    confidence: float  # [0.0, 1.0]


@dataclass
class SentimentResult:
    """Result of sentiment classification."""

    sentiment: str    # "POSITIVE" | "NEUTRAL" | "NEGATIVE"
    confidence: float  # [0.0, 1.0]


# ---------------------------------------------------------------------------
# Concept extraction
# ---------------------------------------------------------------------------

@dataclass
class ConceptMatch:
    """A single concept detected in the text."""

    concept: str       # e.g., "offer", "discount", "property_type"
    confidence: float  # [0.0, 1.0]
    source_text: str   # Fragment of the original text that triggered the detection


@dataclass
class Entity:
    """A structured entity extracted from the text."""

    concept: str                  # e.g., "price", "area_sqm", "location"
    raw_value: str                # Textual value as found in the text (e.g., "USD 250,000")
    numeric_value: float | None   # Numeric value if applicable (e.g., 250000.0)
    unit: str | None              # Unit if applicable (e.g., "USD", "m2")


@dataclass
class ConceptResult:
    """Aggregated result of concept extraction."""

    sales_concepts: list[ConceptMatch]
    real_estate_concepts: list[ConceptMatch]
    entities: list[Entity]


# ---------------------------------------------------------------------------
# Analysis report
# ---------------------------------------------------------------------------

@dataclass
class AnalysisReport:
    """Full analysis report produced by the pipeline."""

    input_text: str
    intent: str                               # Value from IntentResult
    intent_confidence: float
    sentiment: str                            # Value from SentimentResult
    sentiment_confidence: float
    sales_concepts: list[ConceptMatch]
    real_estate_concepts: list[ConceptMatch]
    entities: list[Entity]
    analyzed_at: str                          # ISO 8601 UTC timestamp


# ---------------------------------------------------------------------------
# Error
# ---------------------------------------------------------------------------

@dataclass
class AnalysisError:
    """Structured error returned when the pipeline cannot produce a report."""

    error_code: str     # e.g., "INPUT_TOO_SHORT", "INPUT_TOO_LONG", "INPUT_EMPTY", "ANALYSIS_ERROR"
    error_message: str


# ---------------------------------------------------------------------------
# Model metadata
# ---------------------------------------------------------------------------

@dataclass
class ModelMetadata:
    """Metadata associated with a registered ML model."""

    model_id: str
    model_version: str
    domain: str          # "intent" | "sentiment" | "concept_sales" | "concept_real_estate" | "vectorizer"
    registered_at: str   # ISO 8601 timestamp
    is_active: bool = False
