"""
Concept extractor component for the text sales and real estate analyzer.

Extracts sales and real estate concepts from text using:
1. ML multi-label classifiers for concept detection
2. Regex post-processing for numeric entity extraction
3. Extended entity extraction for conversational sales data
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

# Bedroom patterns
_BEDROOM_PATTERNS = [
    re.compile(r'(\d+\s*(?:habitaciones?|cuartos?|dormitorios?|rooms?|bedrooms?))', re.IGNORECASE),
    re.compile(r'(\d+-?bedroom)', re.IGNORECASE),
]

# Bathroom patterns
_BATHROOM_PATTERNS = [
    re.compile(r'(\d+\s*(?:banos?|bathrooms?|baths?))', re.IGNORECASE),
    re.compile(r'(\d+-?bath)', re.IGNORECASE),
]

# Geographic location terms
_LOCATION_TERMS = [
    re.compile(r'\b(zona\s+[a-zA-Z\u00e1\u00e9\u00ed\u00f3\u00fa\u00f1]{3,})', re.IGNORECASE),
    re.compile(r'\b(sector\s+[a-zA-Z\u00e1\u00e9\u00ed\u00f3\u00fa\u00f1]{3,})', re.IGNORECASE),
    re.compile(r'\b(urbanizacion\s+[a-zA-Z\u00e1\u00e9\u00ed\u00f3\u00fa\u00f1]{3,})', re.IGNORECASE),
    re.compile(r'\b(barrio\s+[a-zA-Z\u00e1\u00e9\u00ed\u00f3\u00fa\u00f1]{3,})', re.IGNORECASE),
    re.compile(r'\b(colonia\s+[a-zA-Z\u00e1\u00e9\u00ed\u00f3\u00fa\u00f1]{3,})', re.IGNORECASE),
    re.compile(r'\b(downtown|city\s+center|uptown|midtown)\b', re.IGNORECASE),
    re.compile(r'\b(Zona\s+(?:Norte|Sur|Este|Oeste|Centro))\b', re.UNICODE),
    re.compile(r'\b(Sector\s+(?:Norte|Sur|Este|Oeste|Centro))\b', re.UNICODE),
    re.compile(r'\b(?:en|in|at|near)\s+([A-Z][a-z\u00e1\u00e9\u00ed\u00f3\u00fa\u00f1]{2,}(?:\s+[A-Z][a-z\u00e1\u00e9\u00ed\u00f3\u00fa\u00f1]{2,})*)', re.UNICODE),
]

_LOCATION_STOPWORDS = {
    'este', 'esta', 'estos', 'estas',
    'norte', 'sur', 'oeste', 'centro',
    'bien', 'mal', 'mas', 'menos',
    'entonces', 'donde', 'cuando',
}

# --- Extended entity patterns ---

# Date/time patterns
_DATE_PATTERNS = [
    re.compile(r'\b((?:el\s+)?(?:lunes|martes|mi[eé]rcoles|jueves|viernes|s[aá]bado|domingo))\b', re.IGNORECASE),
    re.compile(r'\b((?:esta|la\s+pr[oó]xima|la\s+siguiente|este|el\s+pr[oó]ximo)\s+(?:semana|mes|a[nñ]o|fin\s+de\s+semana))\b', re.IGNORECASE),
    re.compile(r'\b(en\s+\d+\s+(?:d[ií]as?|semanas?|meses?))\b', re.IGNORECASE),
    re.compile(r'\b(\d{1,2}\s+(?:de|del)\s+(?:enero|febrero|marzo|abril|mayo|junio|julio|agosto|septiembre|octubre|noviembre|diciembre|mes))\b', re.IGNORECASE),
    re.compile(r'\b((?:next|this)\s+(?:week|month|monday|tuesday|wednesday|thursday|friday|saturday|sunday))\b', re.IGNORECASE),
    re.compile(r'\b(hoy|ma[nñ]ana|ayer|pasado\s+ma[nñ]ana)\b', re.IGNORECASE),
    re.compile(r'\b(today|tomorrow|yesterday)\b', re.IGNORECASE),
]

# Time/schedule patterns
_SCHEDULE_PATTERNS = [
    re.compile(r'\b((?:a\s+la|por\s+la|en\s+la)\s+(?:ma[nñ]ana|tarde|noche))\b', re.IGNORECASE),
    re.compile(r'\b(de\s+\d{1,2}\s+a\s+\d{1,2}(?:\s*(?:hs?|horas?))?)\b', re.IGNORECASE),
    re.compile(r'\b(a\s+las?\s+\d{1,2}(?::\d{2})?(?:\s*(?:hs?|horas?|am|pm))?)\b', re.IGNORECASE),
    re.compile(r'\b(franjas?\s+horarias?)\b', re.IGNORECASE),
    re.compile(r'\b((?:en\s+)?turnos?(?:\s+(?:rotativos?|fijos?))?)\b', re.IGNORECASE),
    re.compile(r'\b((?:in\s+the\s+)?(?:morning|afternoon|evening))\b', re.IGNORECASE),
    re.compile(r'\b(at\s+\d{1,2}(?::\d{2})?\s*(?:am|pm)?)\b', re.IGNORECASE),
]

# Percentage patterns
_PERCENTAGE_PATTERNS = [
    re.compile(r'(\d+(?:[.,]\d+)?\s*%)', re.IGNORECASE),
    re.compile(r'(\d+(?:[.,]\d+)?\s+por\s+ciento)', re.IGNORECASE),
    re.compile(r'(\d+(?:[.,]\d+)?\s+percent)', re.IGNORECASE),
]

# Contact info patterns
_CONTACT_PATTERNS = [
    re.compile(r'(\+?\d{1,3}[\s\-]?\(?\d{2,4}\)?[\s\-]?\d{3,4}[\s\-]?\d{3,4})', re.IGNORECASE),
    re.compile(r'([a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,})', re.IGNORECASE),
]

# Action/commitment patterns
_ACTION_PATTERNS = [
    re.compile(r'\b((?:voy|vamos|va)\s+a\s+(?:llamar|enviar|mandar|escribir|visitar|ver|revisar|consultar|confirmar|agendar|coordinar)\w*)\b', re.IGNORECASE),
    re.compile(r'\b((?:te|le|les)\s+(?:env[ií]o|mando|llamo|escribo|confirmo|agendo|paso)\w*(?:\s+\w+){0,3})\b', re.IGNORECASE),
    re.compile(r'\b((?:quedamos|acordamos|coordinamos)\s+(?:en\s+)?\w+(?:\s+\w+){0,4})\b', re.IGNORECASE),
    re.compile(r'\b(no\s+dud[ae]n?\s+en\s+\w+(?:\s+\w+){0,3})\b', re.IGNORECASE),
    re.compile(r'\b(cualquier\s+(?:consulta|duda|pregunta)[^.!?\n]{0,30})\b', re.IGNORECASE),
]

# Role/person detection
_ROLE_PATTERNS = [
    re.compile(r'\b((?:mi|el|la|nuestro|nuestra)\s+(?:cliente|comprador|compradora|vendedor|vendedora|agente|asesor|asesora|corredor|corredora|propietario|propietaria|inquilino|inquilina|due[nñ]o|due[nñ]a))\b', re.IGNORECASE),
    re.compile(r'\b((?:mis?|nuestros?|nuestras?)\s+(?:compa[nñ]eras?|compa[nñ]eros?|equipo|colegas?|socios?|socio))\b', re.IGNORECASE),
    re.compile(r'\b((?:my|the|our)\s+(?:client|buyer|seller|agent|broker|owner|tenant|team|partner))\b', re.IGNORECASE),
]

# Condition/requirement patterns
_CONDITION_PATTERNS = [
    re.compile(r'\b(siempre\s+(?:que|y\s+cuando|pido)\s+[^.!?\n]{3,40})\b', re.IGNORECASE),
    re.compile(r'\b((?:necesito|requiero|pido|exijo)\s+(?:que\s+)?[^.!?\n]{3,40})\b', re.IGNORECASE),
]


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
    if '%' in raw_lower or 'ciento' in raw_lower or 'percent' in raw_lower:
        return '%'
    return None


def _find_entities(original_text: str) -> list[Entity]:
    """Extract structured entities from the original text using regex."""
    entities: list[Entity] = []
    seen_spans: set[tuple[int, int]] = set()

    def _overlaps(span: tuple[int, int]) -> bool:
        """Check if a span overlaps with any already seen span."""
        for s in seen_spans:
            if span[0] < s[1] and span[1] > s[0]:
                return True
        return False

    def add_entity(concept: str, patterns: list[re.Pattern], extract_num: bool = True, min_len: int = 3) -> None:
        for pattern in patterns:
            for match in pattern.finditer(original_text):
                span = match.span()
                if span in seen_spans or _overlaps(span):
                    continue
                seen_spans.add(span)
                raw = match.group(0).strip()
                if len(raw) < min_len:
                    continue
                entities.append(Entity(
                    concept=concept,
                    raw_value=raw,
                    numeric_value=_extract_numeric(raw) if extract_num else None,
                    unit=_extract_unit(raw) if extract_num else None,
                ))

    # Core real estate entities
    add_entity('price', _PRICE_PATTERNS)
    add_entity('area_sqm', _AREA_PATTERNS)
    add_entity('bedrooms', _BEDROOM_PATTERNS)
    add_entity('bathrooms', _BATHROOM_PATTERNS)

    # Extended entities
    add_entity('percentage', _PERCENTAGE_PATTERNS, min_len=2)
    add_entity('date', _DATE_PATTERNS, extract_num=False)
    add_entity('schedule', _SCHEDULE_PATTERNS, extract_num=False)
    add_entity('contact', _CONTACT_PATTERNS, extract_num=False)
    add_entity('action', _ACTION_PATTERNS, extract_num=False)
    add_entity('role', _ROLE_PATTERNS, extract_num=False)
    add_entity('condition', _CONDITION_PATTERNS, extract_num=False)

    # Location extraction with stopword filtering
    for pattern in _LOCATION_TERMS:
        for match in pattern.finditer(original_text):
            span = match.span()
            if span in seen_spans or _overlaps(span):
                continue
            raw = match.group(0).strip()
            if raw.lower() in _LOCATION_STOPWORDS:
                continue
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
            'offer': ['ofrezco', 'oferta', 'offer', 'offering', 'vendo', 'selling', 'pongo en venta'],
            'discount': ['descuento', 'rebaja', 'discount', 'reduction', 'promocion'],
            'commission': ['comision', 'commission', 'fee', 'honorario'],
            'closing': ['cierre', 'closing', 'firmamos', 'precio final', 'final price', 'reserva', 'escritura', 'boleto'],
            'prospect': ['prospecto', 'prospect', 'buyer', 'comprador', 'cliente', 'interesado'],
            'objection': ['objeta', 'objection', 'concern', 'duda', 'caro', 'costoso', 'lejos'],
            'follow_up': ['seguimiento', 'follow up', 'follow-up', 'contactar', 'llamar'],
            'negotiation': ['negociacion', 'negotiation', 'negociar', 'negotiate', 'contraoferta', 'precio'],
            'property_type': ['apartamento', 'casa', 'house', 'condo', 'terreno', 'local', 'lote', 'departamento', 'duplex', 'ph'],
            'price': ['precio', 'price', 'usd', 'dolares', 'dollars', 'cuota', 'pesos', 'contado', 'financ'],
            'area_sqm': ['m2', 'metros', 'sqm', 'square', 'metraje', 'superficie', 'hectarea'],
            'bedrooms': ['habitaciones', 'cuartos', 'bedrooms', 'dormitorios', 'ambientes'],
            'bathrooms': ['banos', 'bathrooms', 'baths'],
            'location': ['zona', 'ubicado', 'located', 'sector', 'ciudad', 'barrio', 'avenida', 'calle'],
            'amenities': ['piscina', 'gimnasio', 'pool', 'gym', 'amenidades', 'amenities', 'pileta', 'seguridad'],
            'zoning': ['zonificacion', 'zoning', 'zona comercial', 'residencial', 'habilitado'],
            'condition': ['estado', 'condition', 'remodelado', 'renovated', 'nuevo', 'estrenar', 'construir'],
        }

        keywords = keyword_map.get(concept, [])
        text_lower = text.lower()
        for kw in keywords:
            idx = text_lower.find(kw.lower())
            if idx != -1:
                # Show context around the keyword (40 chars before, 60 after)
                start = max(0, idx - 40)
                end = min(len(text), idx + len(kw) + 60)
                fragment = text[start:end].strip()
                # Clean up: don't start/end mid-word
                if start > 0:
                    space_idx = fragment.find(' ')
                    if space_idx > 0 and space_idx < 15:
                        fragment = fragment[space_idx+1:]
                return fragment

        # Fallback: return empty string instead of beginning of text
        return ""
