"""
src/components/revenue_engine.py
================================
Puente / adaptador de Revenue Intelligence para la UI de Kiro.

IMPORTANTE - que ES y que NO ES este modulo:

  Este NO es un pipeline paralelo ni una reimplementacion del analisis. Es un
  ADAPTADOR limpio y stateless que expone contratos estables (DTOs con to_dict())
  pero que INTERNAMENTE delega en los componentes REALES de produccion, sin
  duplicar su logica:

    - Analisis comercial: src.components.commercial_analyzer.CommercialAnalyzer
      (ya hace normalizacion con enie preservada, cache TTL del diccionario y
      _classify_risk internamente). NO recalculamos nada aca.
    - Diccionario editable: src.users.dictionary_store_pg (persistencia en
      PostgreSQL). El FeedbackLoop escribe ahi, NUNCA en una lista en RAM (eso
      se perderia en cada redeploy de Railway y no se compartiria entre workers).
    - Autorizacion admin: se apoya en la fuente de verdad del proyecto
      (_is_admin de web_app.py, basado en session["username"] in _ADMIN_USERS).

  Objetivo: dar un contrato de arquitectura tipo Conversation & Revenue
  Intelligence (estilo Gong/Chorus) SIN tocar el pipeline de guardado, la
  resolucion de fechas ni el conteo de datos. Todo lo sensible sigue viviendo
  en sus modulos reales. Este modulo esta AISLADO e INERTE: no se conecta a
  ningun endpoint de web_app.py (Opcion A).

HONESTIDAD SOBRE EL ALCANCE (leer antes de usar):
  El vocabulario de Revenue Intelligence (Gong/Chorus) incluye conceptos que
  requieren capacidades que este sistema HOY no tiene: audio con diarizacion de
  hablantes, talk-time real, grabacion de llamadas, sincronizacion con CRM,
  forecasting y coaching en tiempo real. NO los inventamos.

  Cada campo de los DTOs esta clasificado como:
    * DATO REAL      -> derivado directamente de lo que CommercialAnalysis ya
                        calcula sobre el texto.
    * PROXY          -> aproximacion honesta a partir de texto (ej: "talk ratio"
                        derivado de densidad comercial, NO de talk-time de audio).
    * CONTRATO FUTURO-> campo definido para dar forma al contrato, pero HOY vacio
                        o None porque su fuente real (audio/CRM/ML) no esta
                        conectada. Marcado con Field.SOURCE_PENDING.

Contrato de resiliencia: RevenueAnalyzer.analyze() NUNCA lanza excepciones al
llamador; ante error devuelve AnalysisResult(status="error").
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
# 0. MARCADORES DE PROCEDENCIA DEL DATO
# ==========================================
# Etiquetas para que quede EXPLICITO, en el propio payload, que dato es real,
# cual es un proxy de texto y cual es contrato preparado para el futuro.
class DataSource:
    REAL = "real"                      # derivado del analisis actual del texto
    PROXY = "proxy"                    # aproximacion honesta desde texto
    SOURCE_PENDING = "source_pending"  # contrato futuro: fuente real no conectada


# ==========================================
# 1. DTO DE SALIDA BASICO (contrato estable para la UI actual)
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
# 2. DTOs DE REVENUE INTELLIGENCE (contrato tipo Gong/Chorus)
# ==========================================
@dataclass
class DealHealth:
    """
    Salud del deal / probabilidad de cierre. Equivalente al "deal health score"
    de Gong/Chorus, pero derivado del texto (no de senales de CRM).
    """
    risk_level: str = RiskLevel.LOW.value  # REAL: nivel_riesgo del analizador
    close_probability: float = 0.0         # REAL: probabilidad_cierre
    deal_stage: str = "AWARENESS"          # REAL: etapa_funnel
    lead_temperature: str = "FRIO"         # REAL: tipo_lead
    interest_level: str = "MEDIO"          # REAL: nivel_interes
    commitment_level: str = "BAJO"         # REAL: nivel_compromiso
    close_trend: str = "MODERADA"          # REAL: tendencia_cierre
    urgency: str = "BAJA"                   # REAL: urgencia
    needs_manager_review: bool = False      # REAL: requiere_revision_coordinador
    review_reason: str = ""                 # REAL: motivo_revision
    source: str = DataSource.REAL

    def to_dict(self) -> Dict[str, Any]:
        return {
            "risk_level": self.risk_level,
            "close_probability": self.close_probability,
            "deal_stage": self.deal_stage,
            "lead_temperature": self.lead_temperature,
            "interest_level": self.interest_level,
            "commitment_level": self.commitment_level,
            "close_trend": self.close_trend,
            "urgency": self.urgency,
            "needs_manager_review": self.needs_manager_review,
            "review_reason": self.review_reason,
            "source": self.source,
        }


@dataclass
class Stakeholders:
    """
    Mapa de decisores (multi-threading en el vocabulario de Gong). Derivado de
    los co-decisores detectados en el texto.
    """
    decision_makers: List[str] = field(default_factory=list)  # REAL: co_decisores
    is_multi_stakeholder: bool = False                         # REAL: es_multi_decisor
    # CONTRATO FUTURO: roles/seniority por persona requeririan diarizacion de
    # hablantes (audio) o datos de CRM. Hoy no disponibles.
    roles: List[Dict[str, str]] = field(default_factory=list)
    source: str = DataSource.REAL

    def to_dict(self) -> Dict[str, Any]:
        return {
            "decision_makers": self.decision_makers,
            "is_multi_stakeholder": self.is_multi_stakeholder,
            "roles": self.roles,
            "roles_source": DataSource.SOURCE_PENDING,
            "source": self.source,
        }


@dataclass
class DealValue:
    """Valor / presupuesto del deal. Derivado del rango presupuestario detectado."""
    budget_range: str = "NO_DETECTADO"   # REAL: rango_presupuestario
    financing: str = "NO_DETECTADO"      # REAL: financiamiento
    operation_type: str = "INDEFINIDO"   # REAL: tipo_operacion
    budget_detail: Dict[str, Any] = field(default_factory=dict)  # REAL: presupuesto_detalle
    # CONTRATO FUTURO: monto de deal ponderado y moneda normalizada requeririan
    # CRM. Hoy solo tenemos el detalle textual de montos mencionados.
    weighted_amount: Optional[float] = None
    source: str = DataSource.REAL

    def to_dict(self) -> Dict[str, Any]:
        return {
            "budget_range": self.budget_range,
            "financing": self.financing,
            "operation_type": self.operation_type,
            "budget_detail": self.budget_detail,
            "weighted_amount": self.weighted_amount,
            "weighted_amount_source": DataSource.SOURCE_PENDING,
            "source": self.source,
        }


@dataclass
class ConversationMoments:
    """
    Momentos clave y temas de la conversacion. En Gong/Chorus estos vienen con
    timestamps de audio; aca son textuales (sin marca de tiempo).
    """
    buying_signals: List[str] = field(default_factory=list)       # REAL: senales_compra
    objections: List[str] = field(default_factory=list)            # REAL: objeciones_especificas
    open_questions: List[str] = field(default_factory=list)        # REAL: preguntas_abiertas
    persuasion_techniques: List[str] = field(default_factory=list) # REAL: tecnicas_persuasion
    topics: List[str] = field(default_factory=list)                # REAL: keywords
    alerts: List[Dict[str, Any]] = field(default_factory=list)     # REAL: alertas_vendedor
    # CONTRATO FUTURO: timestamps de cada momento requieren audio.
    source: str = DataSource.REAL

    def to_dict(self) -> Dict[str, Any]:
        return {
            "buying_signals": self.buying_signals,
            "objections": self.objections,
            "open_questions": self.open_questions,
            "persuasion_techniques": self.persuasion_techniques,
            "topics": self.topics,
            "alerts": self.alerts,
            "timestamps_source": DataSource.SOURCE_PENDING,
            "source": self.source,
        }


@dataclass
class ConversationMetrics:
    """
    Metricas de conversacion. OJO con el "talk ratio": en Gong es el % de tiempo
    que habla el vendedor vs el cliente, medido sobre AUDIO. Aca NO tenemos audio,
    asi que exponemos un PROXY textual (densidad comercial) y dejamos el talk-time
    real como contrato futuro.
    """
    commercial_density: float = 0.0     # REAL: densidad_comercial
    total_words: int = 0                # REAL: total_palabras
    total_indicators: int = 0           # REAL: total_indicadores
    talk_ratio_proxy: float = 0.0       # PROXY: densidad como proxy de "talk ratio"
    # CONTRATO FUTURO: talk-time real, monologos, patience, interactividad
    # requieren audio con diarizacion de hablantes.
    talk_time_ratio: Optional[float] = None
    longest_monologue_sec: Optional[float] = None
    source: str = DataSource.PROXY

    def to_dict(self) -> Dict[str, Any]:
        return {
            "commercial_density": self.commercial_density,
            "total_words": self.total_words,
            "total_indicators": self.total_indicators,
            "talk_ratio_proxy": self.talk_ratio_proxy,
            "talk_time_ratio": self.talk_time_ratio,
            "longest_monologue_sec": self.longest_monologue_sec,
            "talk_time_source": DataSource.SOURCE_PENDING,
            "source": self.source,
        }


@dataclass
class NextSteps:
    """Proximos pasos / recomendacion comercial. Derivado del analizador."""
    recommended_action: str = ""   # REAL: accion_siguiente
    recommendation: str = ""       # REAL: recomendacion
    summary: str = ""              # REAL: resumen
    source: str = DataSource.REAL

    def to_dict(self) -> Dict[str, Any]:
        return {
            "recommended_action": self.recommended_action,
            "recommendation": self.recommendation,
            "summary": self.summary,
            "source": self.source,
        }


@dataclass
class RevenueInsights:
    """
    Contrato COMPLETO de Conversation & Revenue Intelligence para un texto.
    Agrupa todos los sub-DTOs. Se puebla desde un unico CommercialAnalysis real.
    """
    status: str = "success"                 # "success" | "error"
    raw_text: str = ""
    deal_health: DealHealth = field(default_factory=DealHealth)
    stakeholders: Stakeholders = field(default_factory=Stakeholders)
    deal_value: DealValue = field(default_factory=DealValue)
    moments: ConversationMoments = field(default_factory=ConversationMoments)
    metrics: ConversationMetrics = field(default_factory=ConversationMetrics)
    next_steps: NextSteps = field(default_factory=NextSteps)
    # CONTRATO FUTURO: sentiment fino vive en el pipeline ML de web_app.py, no en
    # CommercialAnalyzer; y la transcripcion/diarizacion requiere audio.
    sentiment: Optional[Dict[str, float]] = None
    error_message: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "status": self.status,
            "raw_text": self.raw_text,
            "deal_health": self.deal_health.to_dict(),
            "stakeholders": self.stakeholders.to_dict(),
            "deal_value": self.deal_value.to_dict(),
            "moments": self.moments.to_dict(),
            "metrics": self.metrics.to_dict(),
            "next_steps": self.next_steps.to_dict(),
            "sentiment": self.sentiment,
            "sentiment_source": DataSource.SOURCE_PENDING,
            "transcription_source": DataSource.SOURCE_PENDING,
            "crm_forecast_source": DataSource.SOURCE_PENDING,
            "error_message": self.error_message,
        }


# ==========================================
# 3. ORQUESTADOR STATELESS (puente al analizador real)
# ==========================================
class RevenueAnalyzer:
    """
    Orquestador central. Delega el analisis pesado en el CommercialAnalyzer real
    y traduce su CommercialAnalysis a los DTOs de este modulo.

    Garantia de contrato: NUNCA lanza excepciones al llamador (stateless &
    resilient). Ante cualquier fallo devuelve el DTO con status="error".
    """

    def __init__(self, analyzer: Optional[CommercialAnalyzer] = None):
        # Reutiliza el analizador real (con su normalizacion de enie, cache TTL de
        # diccionario y _classify_risk). Inyectable para tests.
        self._analyzer = analyzer or CommercialAnalyzer()

    # -- API basica (compatibilidad con el contrato AnalysisResult original) ---
    def analyze(self, raw_input: str) -> AnalysisResult:
        try:
            self._require_text(raw_input)
            ca = self._analyzer.analyze(raw_input)
            return self._to_result(raw_input, ca)
        except Exception as err:  # noqa: BLE001 - contrato: nunca propagar
            logger.error("[Pipeline Error] analyze: %s", err, exc_info=True)
            return AnalysisResult(
                status="error",
                raw_text=raw_input if isinstance(raw_input, str) else "",
                error_message=f"Error en el pipeline de analisis: {err}",
            )

    # -- API extendida (Revenue Intelligence completo) -------------------------
    def analyze_revenue(self, raw_input: str) -> RevenueInsights:
        """
        Devuelve el contrato completo de Revenue Intelligence. Mismo contrato de
        resiliencia: ante fallo devuelve RevenueInsights(status="error").
        """
        try:
            self._require_text(raw_input)
            ca = self._analyzer.analyze(raw_input)
            return self._to_insights(raw_input, ca)
        except Exception as err:  # noqa: BLE001
            logger.error("[Pipeline Error] analyze_revenue: %s", err, exc_info=True)
            return RevenueInsights(
                status="error",
                raw_text=raw_input if isinstance(raw_input, str) else "",
                error_message=f"Error en el pipeline de analisis: {err}",
            )

    # -- Helpers ---------------------------------------------------------------
    @staticmethod
    def _require_text(raw_input: str) -> None:
        if not raw_input or not isinstance(raw_input, str) or not raw_input.strip():
            raise ValueError("El texto provisto es invalido o esta vacio.")

    @staticmethod
    def _safe_risk(ca: CommercialAnalysis) -> RiskLevel:
        try:
            return RiskLevel(ca.nivel_riesgo)
        except Exception:
            return RiskLevel.LOW

    @classmethod
    def _to_result(cls, raw_input: str, ca: CommercialAnalysis) -> AnalysisResult:
        """Traduce al DTO basico (contrato original, sin cambios)."""
        intents: List[Dict[str, float]] = [
            {"intent": str(ca.etapa_funnel), "confidence": float(ca.probabilidad_cierre)}
        ]
        return AnalysisResult(
            status="success",
            raw_text=raw_input,
            cleaned_text="",
            talk_listen_ratio=float(getattr(ca, "densidad_comercial", 0.0)),
            intents=intents,
            sentiment={"pos": 0.0, "neu": 0.0, "neg": 0.0},
            concepts=list(getattr(ca, "keywords", []) or []),
            risk_level=cls._safe_risk(ca),
        )

    @classmethod
    def _to_insights(cls, raw_input: str, ca: CommercialAnalysis) -> RevenueInsights:
        """Traduce el CommercialAnalysis real al contrato completo de Revenue Intelligence."""
        risk = cls._safe_risk(ca)
        return RevenueInsights(
            status="success",
            raw_text=raw_input,
            deal_health=DealHealth(
                risk_level=risk.value,
                close_probability=float(getattr(ca, "probabilidad_cierre", 0.0)),
                deal_stage=str(getattr(ca, "etapa_funnel", "AWARENESS")),
                lead_temperature=str(getattr(ca, "tipo_lead", "FRIO")),
                interest_level=str(getattr(ca, "nivel_interes", "MEDIO")),
                commitment_level=str(getattr(ca, "nivel_compromiso", "BAJO")),
                close_trend=str(getattr(ca, "tendencia_cierre", "MODERADA")),
                urgency=str(getattr(ca, "urgencia", "BAJA")),
                needs_manager_review=bool(getattr(ca, "requiere_revision_coordinador", False)),
                review_reason=str(getattr(ca, "motivo_revision", "")),
            ),
            stakeholders=Stakeholders(
                decision_makers=list(getattr(ca, "co_decisores", []) or []),
                is_multi_stakeholder=bool(getattr(ca, "es_multi_decisor", False)),
            ),
            deal_value=DealValue(
                budget_range=str(getattr(ca, "rango_presupuestario", "NO_DETECTADO")),
                financing=str(getattr(ca, "financiamiento", "NO_DETECTADO")),
                operation_type=str(getattr(ca, "tipo_operacion", "INDEFINIDO")),
                budget_detail=dict(getattr(ca, "presupuesto_detalle", {}) or {}),
            ),
            moments=ConversationMoments(
                buying_signals=list(getattr(ca, "senales_compra", []) or []),
                objections=list(getattr(ca, "objeciones_especificas", []) or []),
                open_questions=list(getattr(ca, "preguntas_abiertas", []) or []),
                persuasion_techniques=list(getattr(ca, "tecnicas_persuasion", []) or []),
                topics=list(getattr(ca, "keywords", []) or []),
                alerts=list(getattr(ca, "alertas_vendedor", []) or []),
            ),
            metrics=ConversationMetrics(
                commercial_density=float(getattr(ca, "densidad_comercial", 0.0)),
                total_words=int(getattr(ca, "total_palabras", 0)),
                total_indicators=int(getattr(ca, "total_indicadores", 0)),
                talk_ratio_proxy=float(getattr(ca, "densidad_comercial", 0.0)),
            ),
            next_steps=NextSteps(
                recommended_action=str(getattr(ca, "accion_siguiente", "")),
                recommendation=str(getattr(ca, "recomendacion", "")),
                summary=str(getattr(ca, "resumen", "")),
            ),
            # sentiment queda None: su fuente real (pipeline ML) no esta conectada aca.
            sentiment=None,
        )


# ==========================================
# 4. FEEDBACK LOOP (diccionario en PostgreSQL, NO en RAM)
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
# 5. DECORADOR RBAC (se apoya en la fuente de verdad del proyecto)
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
        try:
            from web_app import _is_admin
        except Exception:  # noqa: BLE001
            _is_admin = None

        if _is_admin is None or not _is_admin():
            return jsonify({"status": "error", "message": "Acceso no autorizado a este recurso."}), 403
        return f(*args, **kwargs)

    return decorated_function
