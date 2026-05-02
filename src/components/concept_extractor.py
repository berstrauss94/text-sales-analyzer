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
    re.compile(r'([\d,\.]+\d\s*(?:dolares|dollars|usd))', re.IGNORECASE),
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
    re.compile(r'(\d+\s*(?:banos?|bathrooms?|baths?))', re.IGNORECASE),
    re.compile(r'(\d+-?bath)', re.IGNORECASE),
]

# Geographic location terms - only match when preceded by a location keyword
# Avoids false positives like "este" (this) being detected as "east"
_LOCATION_TERMS = [
    # "zona norte", "zona residencial", etc.
    re.compile(r'\b(zona\s+[a-zA-Z]{3,})', re.IGNORECASE),
    # "sector las mercedes", etc.
    re.compile(r'\b(sector\s+[a-zA-Z]{3,})', re.IGNORECASE),
    # "urbanizacion xyz"
    re.compile(r'\b(urbanizacion\s+[a-zA-Z]{3,})', re.IGNORECASE),
    # English location keywords
    re.compile(r'\b(downtown|city\s+center|uptown|midtown)\b', re.IGNORECASE),
    # Only match compass directions when followed by another word (e.g. "zona norte" already caught above)
    # or when part of a proper location phrase like "Zona Norte", "Sector Este"
    re.compile(r'\b(Zona\s+(?:Norte|Sur|Este|Oeste|Centro))\b', re.UNICODE),
    re.compile(r'\b(Sector\s+(?:Norte|Sur|Este|Oeste|Centro))\b', re.UNICODE),
    # City names and proper nouns after "en", "in", "at", "near" - only if capitalized
    re.compile(r'\b(?:en|in|at|near)\s+([A-Z][a-z]{2,}(?:\s+[A-Z][a-z]{2,})*)', re.UNICODE),
]

# Words to exclude from location detection (common Spanish words that look like directions)
_LOCATION_STOPWORDS = {
    'este', 'esta', 'estos', 'estas',  # "this/these" in Spanish
    'norte', 'sur', 'oeste', 'centro',  # standalone compass words without context
    'bien', 'mal', 'mas', 'menos',
}


def _extract_numeric(raw: str) -> float | None:
    """Extract the first numeric value from a raw string."""
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
    if 'usd' in raw_lower or 'dollar' in raw_lower or 'dolar' in raw_lower or '$' in raw:
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

    # Location extraction with stopword filtering
    for pattern in _LOCATION_TERMS:
        for match in pattern.finditer(original_text):
            span = match.span()
            if span in seen_spans:
                continue
            raw = match.group(0).strip()
            # Skip if the raw value is a common stopword
            if raw.lower() in _LOCATION_STOPWORDS:
                continue
            # Skip very short matches (less than 4 chars) to avoid false positives
            if len(raw) < 4:
                continue
            seen_spans.add(span)
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
        """Run the multi-label classifier and return concept matches."""
        try:
            proba_matrix = model.predict_proba(feature_vector)

            concepts: list[ConceptMatch] = []
            threshold = 0.15

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
        """Find a representative text fragment for a concept."""
        keyword_map: dict[str, list[str]] = {
            'offer': ['ofrezco', 'oferta', 'offer', 'offering', 'vendo', 'selling'],
            'discount': ['descuento', 'rebaja', 'discount', 'reduction'],
            'commission': ['comision', 'commission', 'fee', 'honorario'],
            'closing': ['cierre', 'closing', 'firmamos', 'precio final', 'final price'],
            'prospect': ['prospecto', 'prospect', 'buyer', 'comprador', 'cliente'],
            'objection': ['objeta', 'objection', 'concern', 'duda'],
            'follow_up': ['seguimiento', 'follow up', 'follow-up', 'contactar'],
            'negotiation': ['negociacion', 'negotiation', 'negociar', 'negotiate'],
            'property_type': ['apartamento', 'casa', 'house', 'condo', 'terreno', 'local'],
            'price': ['precio', 'price', 'usd', 'dolares', 'dollars'],
            'area_sqm': ['m2', 'metros', 'sqm', 'square', 'metraje'],
            'bedrooms': ['habitaciones', 'cuartos', 'bedrooms', 'dormitorios'],
            'bathrooms': ['banos', 'bathrooms', 'baths'],
            'location': ['zona', 'ubicado', 'located', 'sector', 'ciudad'],
            'amenities': ['piscina', 'gimnasio', 'pool', 'gym', 'amenidades', 'amenities'],
            'zoning': ['zonificacion', 'zoning', 'zona comercial', 'residencial'],
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
