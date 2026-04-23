"""
Validator component for the text sales and real estate analyzer.

Validates input text before it enters the processing pipeline.
"""
from src.models.data_models import ValidationResult


class Validator:
    MIN_LENGTH = 3
    MAX_LENGTH = 50_000

    def validate(self, text: str) -> ValidationResult:
        """
        Validate the input text against the pipeline's acceptance rules.

        Rules are evaluated in order:
        1. len(text) < 3        → INPUT_TOO_SHORT
        2. len(text) > 50_000   → INPUT_TOO_LONG
        3. text.strip() == ""   → INPUT_EMPTY
        4. Otherwise            → success
        """
        if len(text) < self.MIN_LENGTH:
            return ValidationResult.failure(
                "INPUT_TOO_SHORT",
                "Input text is too short to analyze",
            )

        if len(text) > self.MAX_LENGTH:
            return ValidationResult.failure(
                "INPUT_TOO_LONG",
                "Input text exceeds maximum allowed length",
            )

        if text.strip() == "":
            return ValidationResult.failure(
                "INPUT_EMPTY",
                "Input text contains no analyzable content",
            )

        return ValidationResult.success()
