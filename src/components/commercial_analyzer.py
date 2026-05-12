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

    # Detailed word counts per group: {group: {word: count}}
    detalle: dict = field(default_factory=dict)

    # Derived metrics
    total_palabras: int = 0
    total_indicadores: int = 0
    densidad_comercial: float = 0.0
    probabilidad_cierre: float = 0.0

    # Classification
    tipo_lead: str = "FRIO"
    nivel_interes: str = "MEDIO"
    tendencia_cierre: str = "MODERADA"
    recomendacion: str = ""

    # --- Extended analysis fields ---
    etapa_funnel: str = "AWARENESS"          # AWARENESS | CONSIDERATION | DECISION | CLOSED
    urgencia: str = "BAJA"                   # BAJA | MEDIA | ALTA | CRITICA
    nivel_compromiso: str = "BAJO"           # BAJO | MEDIO | ALTO
    senales_compra: list = field(default_factory=list)
    objeciones_especificas: list = field(default_factory=list)
    tipo_operacion: str = "INDEFINIDO"       # VENTA | ALQUILER | INVERSION | PERMUTA | INDEFINIDO
    financiamiento: str = "NO_DETECTADO"     # CONTADO | CREDITO | FINANCIAMIENTO_DIRECTO | NO_DETECTADO
    tecnicas_persuasion: list = field(default_factory=list)
    preguntas_abiertas: list = field(default_factory=list)
    keywords: list = field(default_factory=list)
    resumen: str = ""
    accion_siguiente: str = ""


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

# --- Extended keyword dictionaries ---

_BUYING_SIGNALS: list[str] = [
    "cuando podemos", "cuando firmamos", "me interesa mucho",
    "quiero avanzar", "estoy listo", "vamos a hacerlo",
    "me convence", "lo quiero", "cerremos", "hagamoslo",
    "cuando empezamos", "donde firmo", "cuanto antes",
    "lo tomo", "me quedo con", "acepto", "de acuerdo",
    "when can we", "i want it", "let's do it", "i'm ready",
    "let's move forward", "i'll take it", "deal",
    "felicidades", "bienvenidos", "primer caso",
    "buena inversion", "excelente inversion",
]

_URGENCY_KEYWORDS: list[str] = [
    "urgente", "urgencia", "rapido", "inmediato", "inmediatamente",
    "hoy", "ahora", "ya", "cuanto antes", "lo antes posible",
    "esta semana", "manana", "pronto", "no puede esperar",
    "urgent", "immediately", "asap", "right now", "today",
    "this week", "tomorrow", "soon", "can't wait",
]

_COMMITMENT_KEYWORDS: list[str] = [
    "confirmo", "acepto", "de acuerdo", "listo", "vamos",
    "procedo", "adelante", "hecho", "perfecto", "ok",
    "confirm", "agree", "ready", "let's go", "done",
    "seguro", "sin duda", "definitivamente", "por supuesto",
]

_EVASION_KEYWORDS: list[str] = [
    "despues", "luego", "mas adelante", "no se", "tengo que pensar",
    "lo voy a pensar", "no estoy seguro", "tal vez", "quizas",
    "veremos", "puede ser", "dejame ver", "no puedo ahora",
    "later", "maybe", "not sure", "let me think", "we'll see",
    "perhaps", "i don't know", "need to think",
]

_OPERATION_VENTA: list[str] = [
    "venta", "vender", "vendo", "comprar", "compra", "adquirir",
    "sale", "sell", "buy", "purchase", "acquire",
]

_OPERATION_ALQUILER: list[str] = [
    "alquiler", "alquilar", "renta", "rentar", "arrendamiento",
    "arriendo", "inquilino", "rent", "lease", "tenant",
]

_OPERATION_INVERSION: list[str] = [
    "inversion", "invertir", "rentabilidad", "retorno", "roi",
    "rendimiento", "capitalizar", "invest", "investment", "return",
    "yield", "profit", "portfolio",
]

_FINANCING_CONTADO: list[str] = [
    "contado", "cash", "efectivo", "pago completo", "pago total",
    "sin financiamiento", "pago unico",
]

_FINANCING_CREDITO: list[str] = [
    "credito", "hipoteca", "hipotecario", "banco", "prestamo",
    "financiamiento bancario", "mortgage", "loan", "bank",
    "pre-aprobado", "preaprobado", "aprobacion bancaria",
]

_FINANCING_DIRECTO: list[str] = [
    "financiamiento directo", "pago en cuotas", "cuotas",
    "facilidades de pago", "plan de pago", "owner financing",
    "seller financing", "installments", "payment plan",
]

_PERSUASION_ESCASEZ: list[str] = [
    "ultimo", "ultima", "ultimos", "pocas unidades", "se acaba",
    "no va a durar", "oportunidad unica", "solo queda",
    "limited", "last one", "won't last", "only one left",
]

_PERSUASION_AUTORIDAD: list[str] = [
    "experto", "experiencia", "anos en el mercado", "profesional",
    "certificado", "reconocido", "lider", "mejor agente",
    "expert", "experience", "years in market", "professional",
    "certified", "top agent", "award",
]

_PERSUASION_SOCIAL: list[str] = [
    "todos quieren", "muy demandado", "se vendieron rapido",
    "otros clientes", "el vecino compro", "muy popular",
    "everyone wants", "high demand", "sold quickly",
    "other clients", "very popular",
]

_PERSUASION_RECIPROCIDAD: list[str] = [
    "te regalo", "sin costo", "gratis", "cortesia", "bonus",
    "incluyo", "te doy", "de regalo", "free", "complimentary",
    "no charge", "on the house", "i'll include",
]

# Stopwords for keyword extraction
_STOPWORDS = {
    "el", "la", "los", "las", "un", "una", "unos", "unas", "de", "del",
    "en", "con", "por", "para", "que", "es", "son", "se", "al", "lo",
    "su", "sus", "mas", "muy", "ya", "no", "si", "como", "pero", "o",
    "y", "a", "mi", "me", "te", "le", "nos", "les", "esto", "esta",
    "ese", "esa", "esos", "esas", "este", "estos", "estas", "hay",
    "ser", "estar", "tener", "hacer", "poder", "ir", "ver", "dar",
    "the", "a", "an", "is", "are", "was", "were", "be", "been", "being",
    "have", "has", "had", "do", "does", "did", "will", "would", "could",
    "should", "may", "might", "shall", "can", "need", "dare", "ought",
    "to", "of", "in", "for", "on", "with", "at", "by", "from", "as",
    "into", "through", "during", "before", "after", "above", "below",
    "between", "out", "off", "over", "under", "again", "further", "then",
    "once", "here", "there", "when", "where", "why", "how", "all", "each",
    "every", "both", "few", "more", "most", "other", "some", "such", "no",
    "not", "only", "own", "same", "so", "than", "too", "very", "just",
    "don", "now", "and", "but", "or", "if", "while", "about", "up",
    "also", "bien", "eso", "porque", "entonces", "cuando", "donde",
    "tambien", "asi", "aqui", "ahi", "todo", "toda", "todos", "todas",
    "otro", "otra", "otros", "otras", "mismo", "misma", "cada", "mucho",
    "mucha", "muchos", "muchas", "poco", "poca", "nada", "algo", "yo",
    "tu", "el", "ella", "nosotros", "ellos", "ellas", "usted", "ustedes",
    "voy", "vas", "va", "vamos", "van", "tengo", "tiene", "tienen",
    "hago", "hace", "hacen", "puedo", "puede", "pueden", "quiero",
    "quiere", "quieren", "digo", "dice", "dicen", "soy", "eres",
    "somos", "estoy", "estas", "estamos", "estan", "veces", "vez",
    "cosas", "cosa", "manera", "forma", "parte", "tiempo", "dia",
}


# ---------------------------------------------------------------------------
# Text normalization
# ---------------------------------------------------------------------------

def _normalize(text: str) -> str:
    """Lowercase and remove accents for robust matching."""
    text = text.lower()
    nfkd = unicodedata.normalize("NFKD", text)
    return "".join(c for c in nfkd if not unicodedata.combining(c))


def _count_keyword(text: str, keyword: str) -> int:
    """Count exact word/phrase occurrences in normalized text."""
    pattern = r'(?<![a-z])' + re.escape(keyword) + r'(?![a-z])'
    return len(re.findall(pattern, text))


def _count_total_words(text: str) -> int:
    """Count total words in text."""
    return len(re.findall(r'\b\w+\b', text))


def _find_phrases(text: str, phrases: list[str]) -> list[str]:
    """Find which phrases from a list appear in the text."""
    found = []
    for phrase in phrases:
        if _count_keyword(text, phrase) > 0:
            found.append(phrase)
    return found


def _extract_questions(text: str) -> list[str]:
    """Extract questions from the original text."""
    questions = re.findall(r'[^.!?\n]*\?', text)
    implicit = re.findall(
        r'(?:^|[.!?\n]\s*)((?:cuando|donde|como|cuanto|cuantos|cuantas|por que|que|cual|cuales|quien|quienes)\s[^.!?\n]{5,}[.!?\n])',
        text, re.IGNORECASE
    )
    all_questions = [q.strip() for q in questions + implicit if len(q.strip()) > 5]
    return all_questions[:10]


def _extract_keywords(text: str, top_n: int = 10) -> list[str]:
    """Extract top keywords from text, excluding stopwords."""
    normalized = _normalize(text)
    words = re.findall(r'\b[a-z]{3,}\b', normalized)
    freq: dict[str, int] = {}
    for w in words:
        if w not in _STOPWORDS and len(w) > 3:
            freq[w] = freq.get(w, 0) + 1
    sorted_words = sorted(freq.items(), key=lambda x: x[1], reverse=True)
    return [w for w, _ in sorted_words[:top_n]]


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
            CommercialAnalysis with all indicators, word details and recommendations.
        """
        normalized = _normalize(text)
        ca = CommercialAnalysis()
        ca.detalle = {}

        # Count each indicator group and collect word-level detail
        for group, keywords in _KEYWORDS.items():
            word_counts: dict[str, int] = {}
            total = 0
            for kw in keywords:
                count = _count_keyword(normalized, kw)
                if count > 0:
                    word_counts[kw] = count
                    total += count
            setattr(ca, group, total)
            ca.detalle[group] = word_counts

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

        # Probabilidad de cierre (weighted formula)
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

        # --- Extended analysis ---
        ca.senales_compra = _find_phrases(normalized, _BUYING_SIGNALS)
        ca.objeciones_especificas = self._extract_objections(normalized, text)
        ca.etapa_funnel = self._classify_funnel(ca)
        ca.urgencia = self._classify_urgency(normalized)
        ca.nivel_compromiso = self._classify_commitment(normalized)
        ca.tipo_operacion = self._classify_operation(normalized)
        ca.financiamiento = self._classify_financing(normalized)
        ca.tecnicas_persuasion = self._detect_persuasion(normalized)
        ca.preguntas_abiertas = _extract_questions(text)
        ca.keywords = _extract_keywords(text)

        # Recommendation (uses extended data)
        ca.recomendacion = self._build_recommendation(ca)
        ca.resumen = self._build_summary(ca)
        ca.accion_siguiente = self._build_next_action(ca)

        return ca

    def _extract_objections(self, normalized: str, original: str) -> list[str]:
        """Extract specific objection phrases from the text."""
        objection_patterns = [
            (r'(?:precio|caro|costoso|expensive)[^.!?\n]{0,50}', "Objecion de precio"),
            (r'(?:lejos|distancia|ubicacion|location)[^.!?\n]{0,50}', "Objecion de ubicacion"),
            (r'(?:mal estado|reparacion|arreglo|deterioro|condition)[^.!?\n]{0,50}', "Objecion de estado"),
            (r'(?:documentos|papeles|titulo|escritura|legal)[^.!?\n]{0,50}', "Objecion legal/documental"),
            (r'(?:no me convence|no estoy seguro|tengo que pensar|not sure)[^.!?\n]{0,50}', "Indecision"),
            (r'(?:duda|dudas|doubt)[^.!?\n]{0,40}', "Dudas generales"),
        ]
        found = []
        for pattern, label in objection_patterns:
            matches = re.findall(pattern, normalized)
            if matches:
                found.append(label)
        return found

    def _classify_funnel(self, ca: CommercialAnalysis) -> str:
        """Classify the funnel stage based on indicators."""
        if ca.indicios_cierre >= 2 or ca.probabilidad_cierre > 60:
            return "DECISION"
        if ca.indicios_cierre >= 1 and ca.respuestas_afirmativas >= 1:
            return "DECISION"
        if ca.indicios_prospeccion > 0 or ca.objeciones > 0:
            return "CONSIDERATION"
        if ca.respuestas_afirmativas >= 2 or ca.palabras_positivas >= 2:
            return "CONSIDERATION"
        if ca.probabilidad_cierre > 70:
            return "CLOSED"
        return "AWARENESS"

    def _classify_urgency(self, normalized: str) -> str:
        """Classify urgency level from text."""
        urgency_count = len(_find_phrases(normalized, _URGENCY_KEYWORDS))
        if urgency_count >= 3:
            return "CRITICA"
        if urgency_count >= 2:
            return "ALTA"
        if urgency_count >= 1:
            return "MEDIA"
        return "BAJA"

    def _classify_commitment(self, normalized: str) -> str:
        """Classify commitment level based on commitment vs evasion signals."""
        commitment = len(_find_phrases(normalized, _COMMITMENT_KEYWORDS))
        evasion = len(_find_phrases(normalized, _EVASION_KEYWORDS))
        score = commitment - evasion
        if score >= 2:
            return "ALTO"
        if score >= 0 and commitment > 0:
            return "MEDIO"
        return "BAJO"

    def _classify_operation(self, normalized: str) -> str:
        """Classify the type of real estate operation."""
        venta = len(_find_phrases(normalized, _OPERATION_VENTA))
        alquiler = len(_find_phrases(normalized, _OPERATION_ALQUILER))
        inversion = len(_find_phrases(normalized, _OPERATION_INVERSION))

        scores = {"VENTA": venta, "ALQUILER": alquiler, "INVERSION": inversion}
        best = max(scores, key=scores.get)
        if scores[best] == 0:
            return "INDEFINIDO"
        return best

    def _classify_financing(self, normalized: str) -> str:
        """Detect financing type mentioned in text."""
        contado = len(_find_phrases(normalized, _FINANCING_CONTADO))
        credito = len(_find_phrases(normalized, _FINANCING_CREDITO))
        directo = len(_find_phrases(normalized, _FINANCING_DIRECTO))

        scores = {
            "CONTADO": contado,
            "CREDITO": credito,
            "FINANCIAMIENTO_DIRECTO": directo,
        }
        best = max(scores, key=scores.get)
        if scores[best] == 0:
            return "NO_DETECTADO"
        return best

    def _detect_persuasion(self, normalized: str) -> list[str]:
        """Detect persuasion techniques used in the text."""
        techniques = []
        if _find_phrases(normalized, _PERSUASION_ESCASEZ):
            techniques.append("Escasez")
        if _find_phrases(normalized, _PERSUASION_AUTORIDAD):
            techniques.append("Autoridad")
        if _find_phrases(normalized, _PERSUASION_SOCIAL):
            techniques.append("Prueba social")
        if _find_phrases(normalized, _PERSUASION_RECIPROCIDAD):
            techniques.append("Reciprocidad")
        return techniques

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

    def _build_summary(self, ca: CommercialAnalysis) -> str:
        """Generate a brief summary of the conversation analysis."""
        parts = []

        funnel_labels = {
            "AWARENESS": "El cliente esta en etapa inicial de conocimiento.",
            "CONSIDERATION": "El cliente esta evaluando opciones activamente.",
            "DECISION": "El cliente esta cerca de tomar una decision.",
            "CLOSED": "La operacion esta cerrada o muy avanzada.",
        }
        parts.append(funnel_labels.get(ca.etapa_funnel, ""))

        if ca.tipo_operacion != "INDEFINIDO":
            op_labels = {
                "VENTA": "compra-venta",
                "ALQUILER": "alquiler",
                "INVERSION": "inversion",
            }
            parts.append(f"Tipo de operacion: {op_labels.get(ca.tipo_operacion, 'indefinida')}.")
        else:
            parts.append("Tipo de operacion no identificado claramente.")

        if ca.senales_compra:
            parts.append(f"Se detectaron {len(ca.senales_compra)} senal(es) de compra.")
        if ca.objeciones_especificas:
            parts.append(f"Objeciones: {', '.join(ca.objeciones_especificas).lower()}.")

        return " ".join(parts)

    def _build_next_action(self, ca: CommercialAnalysis) -> str:
        """Determine the recommended next action for the salesperson."""
        if ca.etapa_funnel == "CLOSED":
            return "Felicitar al cliente, solicitar referidos y programar seguimiento post-venta."

        if ca.etapa_funnel == "DECISION":
            if ca.objeciones > 0:
                return "Resolver objeciones pendientes y presentar propuesta de cierre con urgencia."
            return "Presentar propuesta final y agendar firma. No dejar enfriar."

        if ca.etapa_funnel == "CONSIDERATION":
            if ca.objeciones_especificas:
                return f"Abordar: {', '.join(ca.objeciones_especificas).lower()}. Enviar comparables y beneficios."
            return "Enviar informacion detallada, comparables de mercado y agendar segunda visita."

        # AWARENESS
        if ca.indicios_prospeccion > 0:
            return "Calificar al prospecto: presupuesto, plazo y necesidades. Agendar llamada de descubrimiento."
        return "Hacer seguimiento, enviar material informativo y agendar primera reunion."
