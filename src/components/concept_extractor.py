"""
Concept extractor component for the text sales and real estate analyzer.

Extracts sales and real estate concepts from text using:
1. ML multi-label classifiers for concept detection
2. Regex post-processing for numeric entity extraction
"""
from __future__ import annotations

import re

from src.models.data_models import (
    ConceptMatch,
    ConceptResult,
    Entity,
    ParsedText,
)

# ---------------------------------------------------------------------------
# Regex patterns for entity extraction
# ---------------------------------------------------------------------------

# Price patterns: USD 250,000 / $180,000 / 200000 dolares / 150k
_PRICE_PATTERNS = [
    re.compile(r'(USD\s*[\d,\.]+\d)', re.IGNORECASE),
    re.compile(r'(\$\s*[\d,\.]+\d)', re.IGNORECASE),
    re.compile(r'([\d,\.]+\d\s*(?:dólares|dolares|dollars|usd))', re.IGNORECASE),
    re.compile(r'(\d+k)\b', re.IGNORECASE),
]

# Area patterns: 85 m2 / 200 metros cuadrados / 150 sqm / 1200 square feet
_AREA_PATTERNS = [
    re.compile(r'(\d[\d,\.]*\s*m2)\b', re.IGNORECASE),
    re.compile(r'(\d[\d,\.]*\s*metros?\s*cuadrados?)', re.IGNORECASE),
    re.compile(r'(\d[\d,\.]*\s*sqm)\b', re.IGNORECASE),
    re.compile(r'(\d[\d,\.]*\s*square\s*(?:meters?|feet|foot|ft))', re.IGNORECASE),
]

# Bedroom patterns: 3 habitaciones / 4 bedrooms / 2 cuartos / 3 dormitorios
_BEDROOM_PATTERNS = [
    re.compile(r'(\d+\s*(?:habitaciones?|cuartos?|dormitorios?|rooms?|bedrooms?))', re.IGNORECASE),
    re.compile(r'(\d+-?bedroom)', re.IGNORECASE),
]

# Bathroom patterns: 2 banos / 3 bathrooms
_BATHROOM_PATTERNS = [
    re.compile(r'(\d+\s*(?:baños?|banos?|bathrooms?|baths?))', re.IGNORECASE),
    re.compile(r'(\d+-?bath)', re.IGNORECASE),
]

# Geographic location terms (Spanish and English)
_LOCATION_TERMS = [
    re.compile(r'\b(zona\s+\w+)', re.IGNORECASE),
    re.compile(r'\b(sector\s+\w+)', re.IGNORECASE),
    re.compile(r'\b(urbanización\s+\w+)', re.IGNORECASE),
    re.compile(r'\b(downtown|city\s+center|uptown|midtown)\b', re.IGNORECASE),
    re.compile(r'\b(norte|sur|este|oeste|centro)\b', re.IGNORECASE),
    re.compile(r'\b(?:en|in|at|near)\s+([A-Z][a-záéíóúñ]+(?:\s+[A-Z][a-záéíóúñ]+)*)', re.UNICODE),
]


def _extract_numeric(raw: str) -> float | None:
    """Extract the first numeric value from a raw string."""
    # Find the first standalone number (digits with optional commas/dots)
    match = re.search(r'[\d]+(?:[,\.][\d]+)*', raw)
    if not match:
        return None
    try:
        return float(match.group(0).replace(',', ''))
    except ValueError:
        return None


def _extract_unit(raw: str) -> str | None:
    """Extract the unit from a raw value string."""
    raw_lower = raw.lower()
    if 'usd' in raw_lower or 'dollar' in raw_lower or 'dólar' in raw_lower or '$' in raw:
        return 'USD'
    if 'm2' in raw_lower or 'metro' in raw_lower or 'sqm' in raw_lower:
        return 'm2'
    if 'feet' in raw_lower or 'foot' in raw_lower or 'ft' in raw_lower:
        return 'sqft'
    if 'k' in raw_lower and re.match(r'^\d+k$', raw.strip(), re.IGNORECASE):
        return 'USD'
    return None


def _find_entities(original_text: str) -> list[Entity]:
    """Extract structured entities from the original text using regex."""
    entities: list[Entity] = []
    seen_spans: set[tuple[int, int]] = set()

    def add_entity(concept: str, patterns: list[re.Pattern]) -> None:
        for pattern in patterns:
            for match in pattern.finditer(original_text):
                span = match.span()
                if span in seen_spans:
                    continue
                seen_spans.add(span)
                raw = match.group(0).strip()
                entities.append(Entity(
                    concept=concept,
                    raw_value=raw,
                    numeric_value=_extract_numeric(raw),
                    unit=_extract_unit(raw),
                ))

    add_entity('price', _PRICE_PATTERNS)
    add_entity('area_sqm', _AREA_PATTERNS)
    add_entity('bedrooms', _BEDROOM_PATTERNS)
    add_entity('bathrooms', _BATHROOM_PATTERNS)

    # Location extraction
    for pattern in _LOCATION_TERMS:
        for match in pattern.finditer(original_text):
            span = match.span()
            if span in seen_spans:
                continue
            seen_spans.add(span)
            raw = match.group(0).strip()
            entities.append(Entity(
                concept='location',
                raw_value=raw,
                numeric_value=None,
                unit=None,
            ))

    return entities


class ConceptExtractor:
    """
    Extracts sales and real estate concepts from text.

    Uses ML multi-label classifiers for concept detection and
    regex post-processing for structured entity extraction.
    Falls back to empty results if the model fails.
    """

    def __init__(
        self,
        sales_model,
        sales_mlb,
        real_estate_model,
        real_estate_mlb,
    ) -> None:
        self._sales_model = sales_model
        self._sales_mlb = sales_mlb
        self._re_model = real_estate_model
        self._re_mlb = real_estate_mlb

    def extract(
        self, feature_vector, parsed_text: ParsedText
    ) -> ConceptResult:
        """
        Extract concepts and entities from the feature vector and parsed text.

        Returns ConceptResult with:
        - sales_concepts: list of detected sales concepts with confidence
        - real_estate_concepts: list of detected real estate concepts with confidence
        - entities: list of structured entities (prices, areas, locations, etc.)
        """
        sales_concepts = self._extract_concepts(
            feature_vector,
            self._sales_model,
            self._sales_mlb,
            parsed_text.original,
        )
        real_estate_concepts = self._extract_concepts(
            feature_vector,
            self._re_model,
            self._re_mlb,
            parsed_text.original,
        )
        entities = _find_entities(parsed_text.original)

        return ConceptResult(
            sales_concepts=sales_concepts,
            real_estate_concepts=real_estate_concepts,
            entities=entities,
        )

    def _extract_concepts(
        self,
        feature_vector,
        model,
        mlb,
        original_text: str,
    ) -> list[ConceptMatch]:
        """Run the multi-label classifier and return concept matches.

        OneVsRestClassifier.predict_proba() returns an array of shape
        (n_samples, n_classes) where each value is the probability of
        the positive class for that label.
        """
        try:
            # Shape: (1, n_classes) — one sample, n_classes probabilities
            proba_matrix = model.predict_proba(feature_vector)

            concepts: list[ConceptMatch] = []
            threshold = 0.2  # minimum confidence to report a concept

            for i, class_label in enumerate(mlb.classes_):
                prob = float(proba_matrix[0, i])
                if prob >= threshold:
                    source = self._find_source(class_label, original_text)
                    concepts.append(ConceptMatch(
                        concept=class_label,
                        confidence=round(prob, 4),
                        source_text=source,
                    ))

            return sorted(concepts, key=lambda c: c.confidence, reverse=True)

        except Exception:
            return []

    def _find_source(self, concept: str, text: str) -> str:
        """
        Find a representative text fragment for a concept.
        Returns the first matching keyword or the first 50 chars of text.
        """
        # Keyword map for common concepts
        keyword_map: dict[str, list[str]] = {
            'offer': ['ofrezco', 'oferta', 'offer', 'offering', 'vendo', 'selling'],
            'discount': ['descuento', 'rebaja', 'discount', 'reduction', 'reducción'],
            'commission': ['comisión', 'commission', 'fee', 'honorario'],
            'closing': ['cierre', 'closing', 'firmamos', 'precio final', 'final price'],
            'prospect': ['prospecto', 'prospect', 'buyer', 'comprador', 'cliente'],
            'objection': ['objeta', 'objection', 'concern', 'preocupación', 'duda'],
            'follow_up': ['seguimiento', 'follow up', 'follow-up', 'contactar'],
            'negotiation': ['negociación', 'negotiation', 'negociar', 'negotiate'],
            'property_type': ['apartamento', 'casa', 'house', 'condo', 'terreno', 'local'],
            'price': ['precio', 'price', 'usd', 'dólares', 'dollars', '$'],
            'area_sqm': ['m2', 'metros', 'sqm', 'square', 'metraje'],
            'bedrooms': ['habitaciones', 'cuartos', 'bedrooms', 'dormitorios'],
            'bathrooms': ['baños', 'bathrooms', 'baths'],
            'location': ['zona', 'ubicado', 'located', 'sector', 'ciudad'],
            'amenities': ['piscina', 'gimnasio', 'pool', 'gym', 'amenidades', 'amenities'],
            'zoning': ['zonificación', 'zoning', 'zona comercial', 'residencial'],
            'condition': ['estado', 'condition', 'remodelado', 'renovated', 'nuevo'],
        }

        keywords = keyword_map.get(concept, [])
        text_lower = text.lower()
        for kw in keywords:
            idx = text_lower.find(kw.lower())
            if idx != -1:
                start = max(0, idx)
                end = min(len(text), idx + len(kw) + 20)
                return text[start:end].strip()

        return text[:50].strip()
