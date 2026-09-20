"""
src/components/revenue_engine.py
================================
Puente / adaptador de Revenue Intelligence para la UI de Kiro.

IMPORTANTE — que ES y que NO ES este modulo:

  Este NO es un pipeline paralelo ni una reimplementacion del analisis. Es un
  ADAPTADOR limpio y stateless que expone un contrato estable (AnalysisResult
  con to_dict()) pero que INTERNAMENTE delega en los componentes REALES de
  produccion, sin duplicar su logica:

    - Analisis comercial: src.components.commercial_analyzer.CommercialAnalyzer
      (ya hace normalizacion con enie preservada, cache TTL del diccionario y
      _classify_risk internamente). NO recalculamos nada aca.
    - Diccionario editable: src.users.dictionary_store_pg (persistencia en
      PostgreSQL). El FeedbackLoop escribe ahi, NUNCA en una lista en RAM (eso
      se perderia en cada redeploy de Railway y no se compartiria entre workers).
    - Autorizacion admin: se apoya en la fuente de verdad del proyecto
      (_is_admin de web_app.py, basado en session["username"] in _ADMIN_USERS).
      NO inventa un modelo de sesion is_admin/user_id que el proyecto no usa.

  Objetivo: dar un contrato de arquitectura claro (DTO + orquestador + feedback
  + RBAC) sin tocar el pipeline de guardado, la resolucion de fechas ni el
  conteo de datos. Todo lo sensible sigue viviendo en sus modulos reales.

Contrato de resiliencia: RevenueAnalyzer.analyze() NUNCA lanza excepciones al
llamador; ante error devuelve un AnalysisResult con status="error".
"""

import logging
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from functools import wraps

# RiskLevel real del proyecto (hereda de str+Enum: serializa a "LOW"/"MEDIUM"/
# "HIGH"). Reutilizamos ESTE, no uno propio, para no crear un enum incompatible.
from src.components.commercial_analyzer import (
    CommercialAnalyzer,
    CommercialAnalysis,
    RiskLevel,
)

logger = logging.getLogger("RevenueEngine")


# ==========================================
# 1. DTO DE SALIDA (contrato estable para la UI)
# ==========================================
# @dataclass tradicional a proposito (SIN slots=True): decision del proyecto,
# slots daba friccion con el resto del codigo. No cambiar sin motivo.
@dataclass
class AnalysisResult:
    """
    Vista estable y serializable del analisis, poblada desde el CommercialAnalysis
    real. Es el contrato que consume la UI; aisla al frontend de la forma interna
    (rica) de CommercialAnalysis.
    """
    status: str  # "success" o "error"
    raw_text: str
    cleaned_text: str = ""
    talk_listen_ratio: float = 0.0
    intents: List[Dict[str, float]] = field(default_factory=list)
    sentiment: Dict[str, float] = field(
        default_factory=lambda: {"pos": 0.0, "neu": 0.0, "neg": 0.0}
    )
    concepts: List[str] = field(default_factory=list)
    risk_level: RiskLevel = RiskLevel.LOW
    error_message: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        # risk_level puede ser el enum RiskLevel (str-enum) o ya un str; en ambos
        # casos queremos el valor plano "LOW"/"MEDIUM"/"HIGH".
        risk_val = getattr(self.risk_level, "value", self.risk_level)
        return {
            "status": self.status,
            "raw_text": self.raw_text,
            "cleaned_text": self.cleaned_text,
            "metrics": {
                "talk_listen_ratio": self.talk_listen_ratio,
                "risk_level": risk_val,
            },
            "intents": self.intents,
            "sentiment": self.sentiment,
            "concepts": self.concepts,
            "error_message": self.error_message,
        }


# ==========================================
# 2. ORQUESTADOR STATELESS (puente al analizador real)
# ==========================================
class RevenueAnalyzer:
    """
    Orquestador central. Delega el analisis pesado en el CommercialAnalyzer real
    y traduce su CommercialAnalysis al DTO AnalysisResult.

    Garantia de contrato: NUNCA lanza excepciones al llamador (stateless &
    resilient). Ante cualquier fallo devuelve AnalysisResult(status="error").
    """

    def __init__(self, analyzer: Optional[CommercialAnalyzer] = None):
        # Reutiliza el analizador real (con su normalizacion de enie, cache TTL de
        # diccionario y _classify_risk). Inyectable para tests.
        self._analyzer = analyzer or CommercialAnalyzer()

    def analyze(self, raw_input: str) -> AnalysisResult:
        try:
            if not raw_input or not isinstance(raw_input, str) or not raw_input.strip():
                raise ValueError("El texto provisto es invalido o esta vacio.")

            ca: CommercialAnalysis = self._analyzer.analyze(raw_input)
            return self._to_result(raw_input, ca)
        except Exception as err:  # noqa: BLE001 - contrato: nunca propagar
            logger.error(
                "[Pipeline Error] Error procesando analisis: %s", err, exc_info=True
            )
            return AnalysisResult(
                status="error",
                raw_text=raw_input if isinstance(raw_input, str) else "",
                error_message=f"Error en el pipeline de analisis: {err}",
            )

    @staticmethod
    def _to_result(raw_input: str, ca: CommercialAnalysis) -> AnalysisResult:
        """Traduce el CommercialAnalysis real (rico) al DTO estable de salida."""
        # nivel_riesgo viene como str ("LOW"/"MEDIUM"/"HIGH"); lo normalizamos al
        # enum RiskLevel para el DTO (to_dict lo vuelve a aplanar a str).
        try:
            risk = RiskLevel(ca.nivel_riesgo)
        except Exception:
            risk = RiskLevel.LOW

        # Intents: derivamos una intencion principal a partir de la etapa del
        # funnel real, con la probabilidad de cierre como confianza. No inventamos
        # un clasificador nuevo; solo exponemos lo que el analizador ya calculo.
        intents: List[Dict[str, float]] = [
            {"intent": str(ca.etapa_funnel), "confidence": float(ca.probabilidad_cierre)}
        ]

        return AnalysisResult(
            status="success",
            raw_text=raw_input,
            cleaned_text="",  # el analizador real no expone el texto limpio
            talk_listen_ratio=float(getattr(ca, "densidad_comercial", 0.0)),
            intents=intents,
            sentiment={"pos": 0.0, "neu": 0.0, "neg": 0.0},
            concepts=list(getattr(ca, "keywords", []) or []),
            risk_level=risk,
        )


# ==========================================
# 3. FEEDBACK LOOP (diccionario en PostgreSQL, NO en RAM)
# ==========================================
class FeedbackLoop:
    """
    Actualiza el diccionario global de conceptos SIN reiniciar la app y SIN estado
    en memoria: escribe en PostgreSQL via dictionary_store_pg. Asi los cambios
    sobreviven redeploys de Railway y se comparten entre todos los workers.
    """

    def add_keywords(self, new_words: List[str], category: str, added_by: str = "") -> List[str]:
        """
        Persiste cada palabra/frase en la categoria dada del diccionario editable.
        Devuelve las que se agregaron efectivamente (add_phrase devuelve True).
        """
        # Import diferido: evita acoplar la carga del modulo a la disponibilidad
        # de PG y mantiene el mismo patron que web_app.py.
        from src.users import dictionary_store_pg

        added: List[str] = []
        for w in new_words or []:
            w_clean = (w or "").strip().lower()
            if not w_clean:
                continue
            try:
                if dictionary_store_pg.add_phrase(w_clean, category, added_by=added_by):
                    added.append(w_clean)
            except Exception as e:  # noqa: BLE001
                logger.warning("No se pudo persistir '%s' en el diccionario: %s", w_clean, e)
        return added


# ==========================================
# 4. DECORADOR RBAC (se apoya en la fuente de verdad del proyecto)
# ==========================================
def admin_required(f):
    """
    Protege endpoints destructivos. NO define su propio modelo de sesion:
    reutiliza _is_admin() de web_app.py (session["username"] in _ADMIN_USERS),
    que es la unica fuente de verdad de quien es admin en este proyecto.
    """

    @wraps(f)
    def decorated_function(*args, **kwargs):
        from flask import jsonify
        # Import diferido para evitar import circular con web_app.
        try:
            from web_app import _is_admin
        except Exception:  # noqa: BLE001
            _is_admin = None

        if _is_admin is None or not _is_admin():
            return jsonify({"status": "error", "message": "Acceso no autorizado a este recurso."}), 403
        return f(*args, **kwargs)

    return decorated_function
