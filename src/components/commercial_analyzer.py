"""
Commercial analyzer component.

Inspired by SALES_INTELLIGENCE_ENGINE v7.5.
Computes commercial indicators, closing probability,
lead classification and recommendations from a sales text.

All logic is deterministic and stateless — same text always
produces the same result.
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

@dataclass
class CommercialAnalysis:
    """Commercial intelligence report for a sales text."""

    # Raw indicator counts
    palabras_positivas: int = 0
    respuestas_afirmativas: int = 0
    indicios_cierre: int = 0
    escasez_comercial: int = 0
    pedidos_referidos: int = 0
    objeciones: int = 0
    indicios_prospeccion: int = 0

    # Derived metrics
    total_palabras: int = 0
    total_indicadores: int = 0
    densidad_comercial: float = 0.0
    probabilidad_cierre: float = 0.0

    # Classification
    tipo_lead: str = "FRIO"          # CALIENTE / TIBIO / FRIO
    nivel_interes: str = "MEDIO"     # ALTO / MEDIO / BAJO
    tendencia_cierre: str = "MODERADA"  # FUERTE / MODERADA / DEBIL
    recomendacion: str = ""


# ---------------------------------------------------------------------------
# Keyword dictionaries (Spanish + English)
# ---------------------------------------------------------------------------

_KEYWORDS: dict[str, list[str]] = {
    "palabras_positivas": [
        "bueno", "buena", "buenos", "buenas",
        "perfecto", "perfecta", "perfectos", "perfectas",
        "excelente", "excelentes",
        "genial", "fantastico", "fantastica",
        "great", "perfect", "excellent", "wonderful", "amazing",
    ],
    "respuestas_afirmativas": [
        "si", "claro", "ok", "dale", "listo", "correcto",
        "exacto", "afirmativo", "por supuesto", "con gusto",
        "yes", "sure", "absolutely", "of course", "agreed",
    ],
    "indicios_cierre": [
        "reservar", "reserva", "bloquear", "bloqueo", "avanzar",
        "firmar", "firma", "cerrar", "cierre", "proceder",
        "confirmar", "confirmamos", "acordamos", "trato",
        "reserve", "book", "close", "sign", "proceed", "confirm", "deal",
    ],
    "escasez_comercial": [
        "ultimos", "ultima", "ultimo", "disponible", "disponibles",
        "limitado", "limitada", "pocas", "pocos", "urgente",
        "last", "available", "limited", "urgent", "only",
    ],
    "pedidos_referidos": [
        "conoces", "conoce", "alguien", "referido", "referidos",
        "recomendar", "recomiendas", "contacto",
        "know", "someone", "referral", "recommend",
    ],
    "objeciones": [
        "precio", "caro", "cara", "costoso", "costosa",
        "cuota", "duda", "dudas", "pensar", "pensarlo",
        "no se", "no estoy", "esperar", "despues",
        "expensive", "price", "doubt", "think", "wait", "later",
    ],
    "indicios_prospeccion": [
        "invertir", "inversion", "consultar", "averiguar",
        "informacion", "interesado", "interesada", "evaluar",
        "invest", "consult", "information", "interested", "evaluate",
    ],
}


# ---------------------------------------------------------------------------
# Text normalization
# ---------------------------------------------------------------------------

def _normalize(text: str) -> str:
    """Lowercase and remove accents for robust matching."""
    text = text.lower()
    # Remove accents using unicode normalization
    nfkd = unicodedata.normalize("NFKD", text)
    return "".join(c for c in nfkd if not unicodedata.combining(c))


def _count_keyword(text: str, keyword: str) -> int:
    """Count exact word/phrase occurrences in normalized text."""
    # Escape special regex chars and match as whole word/phrase
    pattern = r'(?<![a-z])' + re.escape(keyword) + r'(?![a-z])'
    return len(re.findall(pattern, text))


def _count_total_words(text: str) -> int:
    """Count total words in text."""
    return len(re.findall(r'\b\w+\b', text))


# ---------------------------------------------------------------------------
# Main analyzer
# ---------------------------------------------------------------------------

class CommercialAnalyzer:
    """
    Computes commercial intelligence metrics from a sales text.

    Stateless: each call to analyze() is independent.
    """

    def analyze(self, text: str) -> CommercialAnalysis:
        """
        Analyze a text and return a CommercialAnalysis.

        Args:
            text: Any sales or real estate conversation text.

        Returns:
            CommercialAnalysis with all indicators and recommendations.
        """
        normalized = _normalize(text)
        ca = CommercialAnalysis()

        # Count each indicator group
        for group, keywords in _KEYWORDS.items():
            count = sum(_count_keyword(normalized, kw) for kw in keywords)
            setattr(ca, group, count)

        # Total words and indicators
        ca.total_palabras = _count_total_words(normalized)
        ca.total_indicadores = (
            ca.palabras_positivas
            + ca.respuestas_afirmativas
            + ca.indicios_cierre
            + ca.escasez_comercial
            + ca.pedidos_referidos
            + ca.objeciones
            + ca.indicios_prospeccion
        )

        # Densidad comercial
        if ca.total_palabras > 0:
            ca.densidad_comercial = round(
                ca.total_indicadores / ca.total_palabras, 4
            )

        # Probabilidad de cierre (weighted formula from original engine)
        if ca.total_palabras > 0:
            raw = (
                (ca.indicios_cierre * 5)
                + (ca.respuestas_afirmativas * 2)
                - (ca.objeciones * 3)
            ) / ca.total_palabras * 100
            ca.probabilidad_cierre = round(max(0.0, min(100.0, raw)), 2)

        # Lead classification
        if ca.probabilidad_cierre > 70:
            ca.tipo_lead = "CALIENTE"
        elif ca.probabilidad_cierre > 40:
            ca.tipo_lead = "TIBIO"
        else:
            ca.tipo_lead = "FRIO"

        # Interest level
        if ca.densidad_comercial > 0.04:
            ca.nivel_interes = "ALTO"
        elif ca.densidad_comercial > 0.02:
            ca.nivel_interes = "MEDIO"
        else:
            ca.nivel_interes = "BAJO"

        # Closing tendency
        if ca.probabilidad_cierre > 70:
            ca.tendencia_cierre = "FUERTE"
        elif ca.probabilidad_cierre > 30:
            ca.tendencia_cierre = "MODERADA"
        else:
            ca.tendencia_cierre = "DEBIL"

        # Recommendation
        ca.recomendacion = self._build_recommendation(ca)

        return ca

    def _build_recommendation(self, ca: CommercialAnalysis) -> str:
        """Generate a contextual recommendation based on the indicators."""
        parts: list[str] = []

        if ca.tipo_lead == "CALIENTE":
            parts.append("Lead caliente: proceder al cierre inmediatamente.")
        elif ca.tipo_lead == "TIBIO":
            parts.append("Lead tibio: reforzar urgencia y beneficios.")
        else:
            parts.append("Lead frio: nutrir con informacion y seguimiento.")

        if ca.objeciones > 2:
            parts.append("Hay objeciones importantes: trabajar precio y condiciones.")
        elif ca.objeciones > 0:
            parts.append("Objeciones menores detectadas: resolver antes de cerrar.")

        if ca.indicios_cierre > 0:
            parts.append("Senales de cierre presentes: aprovechar el momento.")

        if ca.escasez_comercial > 0:
            parts.append("Usar escasez como palanca de decision.")

        if ca.pedidos_referidos > 0:
            parts.append("Solicitar referidos al finalizar la conversacion.")

        if ca.indicios_prospeccion > 0:
            parts.append("Cliente en etapa de evaluacion: proveer informacion clave.")

        return " ".join(parts) if parts else "Continuar el seguimiento regular."
