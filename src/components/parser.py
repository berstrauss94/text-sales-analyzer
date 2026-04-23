"""
Parser component for the text sales and real estate analyzer.

Transforms raw input text into a structured ParsedText representation.
Guarantees round-trip: parse(print(parse(text))).tokens == parse(text).tokens
"""
from __future__ import annotations

import re

from src.models.data_models import ParsedText


# Sentence boundary characters
_SENTENCE_DELIMITERS = re.compile(r'(?<=[.!?])\s+')

# Token splitter: split on whitespace and non-alphanumeric chars
# but keep currency symbols and numbers together (e.g. "USD", "250,000")
_TOKEN_SPLITTER = re.compile(r'[\s,;:()\[\]{}"\']+')


class Parser:
    """Tokenizes and segments input text into a structured ParsedText."""

    def parse(self, text: str) -> ParsedText:
        """
        Parse the input text into tokens and sentences.

        Steps:
        1. Strip leading/trailing whitespace from the full text.
        2. Segment into sentences using punctuation boundaries (.!?).
        3. For each sentence, tokenize by splitting on whitespace and
           non-sentence punctuation.
        4. Normalize tokens: lowercase, strip whitespace.
        5. Filter out empty tokens.

        Returns a ParsedText with:
        - original: the unmodified input text
        - tokens: flat list of all normalized tokens
        - sentences: list of token lists, one per sentence
        """
        stripped = text.strip()

        # Split into raw sentence strings
        raw_sentences = _SENTENCE_DELIMITERS.split(stripped)

        sentences: list[list[str]] = []
        all_tokens: list[str] = []

        for raw_sentence in raw_sentences:
            raw_sentence = raw_sentence.strip()
            if not raw_sentence:
                continue

            # Tokenize: split on whitespace and punctuation (except . ! ?)
            raw_tokens = _TOKEN_SPLITTER.split(raw_sentence)

            # Normalize: lowercase, strip, filter empty
            normalized: list[str] = []
            for tok in raw_tokens:
                # Remove trailing sentence punctuation from token
                tok_clean = tok.strip().rstrip('.!?').strip()
                tok_lower = tok_clean.lower()
                if tok_lower:
                    normalized.append(tok_lower)

            if normalized:
                sentences.append(normalized)
                all_tokens.extend(normalized)

        return ParsedText(
            original=text,
            tokens=all_tokens,
            sentences=sentences,
        )

    def print(self, parsed: ParsedText) -> str:
        """
        Serialize a ParsedText back to a string.

        Joins sentences with '. ' and tokens within each sentence with ' '.
        Guarantees round-trip: parse(print(parse(text))).tokens == parse(text).tokens
        """
        sentence_strings = [' '.join(sentence) for sentence in parsed.sentences]
        return '. '.join(sentence_strings)
