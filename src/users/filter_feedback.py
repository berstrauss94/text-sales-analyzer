# -*- coding: utf-8 -*-
"""
filter_feedback.py — Votos de los vendedores sobre la calidad de cada apartado
de los filtros de analisis (intencion, sentimiento, etc.), persistidos en
PostgreSQL en una tabla SEPARADA (no toca analysis_history ni los informes).

QUE ES
------
En cada apartado de un filtro (Que significa / Para el vendedor / Tips / Siguiente
paso) el vendedor puede marcar una perilla ✓ (acertado) o ✗ (no acertado). Cada
voto se guarda aca. Sirve para:
  1. Medir que apartados aciertan y cuales no (panel admin).
  2. A futuro: inyectar los votos negativos recientes como ejemplos "a evitar"
     en el prompt de la IA (few-shot). Esta capa solo GUARDA y CONSULTA; la
     inyeccion se resuelve en web_app cuando se decida activarla.

DISENO
------
- Tabla propia `filter_feedback`. NUNCA se toca analysis_history: cero riesgo
  para los datos historicos ni la distribucion por mes.
- Multi-tenant: aislado por tenant_id. Reutiliza el pool de history_manager.
- Best-effort: cualquier fallo se traga y devuelve un valor neutro; jamas rompe
  el analisis ni el guardado del texto.
"""
from __future__ import annotations

import logging
import uuid

logger = logging.getLogger(__name__)

_table_ready = False

# Filtros validos (deben coincidir con el frontend). Ahora cubren TODOS los
# filtros del panel, no solo intencion/sentimiento.
VALID_FILTERS = {"intent", "sentiment", "sales", "re", "commercial"}
VALID_VOTES = {"up", "down"}

# Los apartados (section_key) varian por filtro: intencion/sentimiento usan
# meaning/seller/tips/next/risk; conceptos usan la clave del concepto
# (price, location, ...); comercial usa funnel/urgencia/etc. Como el conjunto es
# abierto, NO se valida contra una lista fija: se acepta cualquier section_key
# corto y no vacio (se sanitiza el largo al guardar).
_MAX_SECTION_LEN = 40


def _conn():
    try:
        from src.users.history_manager import _get_pg_conn
        return _get_pg_conn()
    except Exception:
        return None


def _release(conn, close: bool = False) -> None:
    try:
        from src.users.history_manager import _return_pg_conn
        _return_pg_conn(conn, close=close)
    except Exception:
        pass


def is_available() -> bool:
    try:
        from src.users.history_manager import _is_pg_available
        return bool(_is_pg_available())
    except Exception:
        return False


def _ensure_table(conn) -> None:
    global _table_ready
    if _table_ready:
        return
    with conn.cursor() as cur:
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS filter_feedback (
                id           TEXT        NOT NULL,
                tenant_id    TEXT        NOT NULL DEFAULT '__legacy__',
                username     TEXT        NOT NULL DEFAULT '',
                filter_key   TEXT        NOT NULL,
                section_key  TEXT        NOT NULL,
                label        TEXT        NOT NULL DEFAULT '',
                vote         TEXT        NOT NULL,
                text_excerpt TEXT        NOT NULL DEFAULT '',
                section_text TEXT        NOT NULL DEFAULT '',
                created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
                PRIMARY KEY (id)
            )
            """
        )
        cur.execute(
            "CREATE INDEX IF NOT EXISTS idx_ff_tenant_filter "
            "ON filter_feedback (tenant_id, filter_key, section_key, vote)"
        )
        cur.execute(
            "CREATE INDEX IF NOT EXISTS idx_ff_created "
            "ON filter_feedback (tenant_id, created_at DESC)"
        )
    conn.commit()
    _table_ready = True


def record_vote(username: str, filter_key: str, section_key: str, vote: str,
                label: str = "", text_excerpt: str = "", section_text: str = "",
                tenant_id: str = "__legacy__") -> bool:
    """
    Guarda un voto (up/down) de un apartado de un filtro. Best-effort.
    Devuelve True si guardo. Valida filtro/apartado/voto contra las listas
    permitidas; si no son validos, no guarda y devuelve False (sin romper).
    """
    fk = str(filter_key or "").strip().lower()
    sk = str(section_key or "").strip().lower()[:_MAX_SECTION_LEN]
    v = str(vote or "").strip().lower()
    if fk not in VALID_FILTERS or not sk or v not in VALID_VOTES:
        return False
    if not is_available():
        return False
    conn = _conn()
    if conn is None:
        return False
    try:
        _ensure_table(conn)
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO filter_feedback
                    (id, tenant_id, username, filter_key, section_key, label,
                     vote, text_excerpt, section_text, created_at)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s, now())
                """,
                (uuid.uuid4().hex, tenant_id or "__legacy__",
                 str(username or "")[:120], fk, sk,
                 str(label or "")[:60], v,
                 str(text_excerpt or "")[:500], str(section_text or "")[:2000]),
            )
        conn.commit()
        _release(conn)
        return True
    except Exception as exc:
        logger.error(f"filter_feedback record error: {exc}")
        try:
            conn.rollback()
        except Exception:
            pass
        _release(conn, close=True)
        return False


def recent_negative_any(filter_key: str, tenant_id: str = "__legacy__",
                        limit: int = 3) -> list[dict]:
    """
    Como recent_negative pero SIN fijar el apartado: trae los votos negativos
    recientes de un filtro cualquiera sea su section_key. Util para conceptos y
    comercial, cuyas secciones son claves dinamicas. Incluye section_key en cada
    resultado. Lista vacia si PG no esta o no hay votos.
    """
    fk = str(filter_key or "").strip().lower()
    if fk not in VALID_FILTERS or not is_available():
        return []
    conn = _conn()
    if conn is None:
        return []
    try:
        _ensure_table(conn)
        with conn.cursor() as cur:
            cur.execute(
                "SELECT section_key, text_excerpt, section_text, created_at "
                "FROM filter_feedback "
                "WHERE tenant_id = %s AND filter_key = %s "
                "AND vote = 'down' AND section_text <> '' "
                "ORDER BY created_at DESC LIMIT %s",
                (tenant_id or "__legacy__", fk, int(limit)),
            )
            rows = cur.fetchall()
        _release(conn)
        return [
            {"section_key": r[0] or "", "text_excerpt": r[1] or "",
             "section_text": r[2] or "",
             "created_at": r[3].isoformat() if hasattr(r[3], "isoformat") else str(r[3])}
            for r in rows
        ]
    except Exception as exc:  # noqa: BLE001
        logger.error(f"filter_feedback recent_negative_any error: {exc}")
        try:
            conn.rollback()
        except Exception:
            pass
        _release(conn, close=True)
        return []


def stats(tenant_id: str = "__legacy__") -> dict:
    """
    Resumen de votos por (filtro, apartado): cuantos up y cuantos down.
    Estructura: {"intent": {"meaning": {"up": 3, "down": 1}, ...}, ...}.
    {} si PG no esta disponible.
    """
    if not is_available():
        return {}
    conn = _conn()
    if conn is None:
        return {}
    try:
        _ensure_table(conn)
        with conn.cursor() as cur:
            cur.execute(
                "SELECT filter_key, section_key, vote, COUNT(*) "
                "FROM filter_feedback WHERE tenant_id = %s "
                "GROUP BY filter_key, section_key, vote",
                (tenant_id or "__legacy__",),
            )
            rows = cur.fetchall()
        _release(conn)
        out: dict = {}
        for fk, sk, v, cnt in rows:
            out.setdefault(fk, {}).setdefault(sk, {"up": 0, "down": 0})
            if v in ("up", "down"):
                out[fk][sk][v] = cnt
        return out
    except Exception as exc:
        logger.error(f"filter_feedback stats error: {exc}")
        try:
            conn.rollback()
        except Exception:
            pass
        _release(conn, close=True)
        return {}


def totals(tenant_id: str = "__legacy__") -> dict:
    """
    Totales globales de votos del tenant: {"up": N, "down": M, "total": N+M}.
    {"up":0,"down":0,"total":0} si PG no esta o no hay votos.
    """
    base = {"up": 0, "down": 0, "total": 0}
    if not is_available():
        return base
    conn = _conn()
    if conn is None:
        return base
    try:
        _ensure_table(conn)
        with conn.cursor() as cur:
            cur.execute(
                "SELECT vote, COUNT(*) FROM filter_feedback "
                "WHERE tenant_id = %s GROUP BY vote",
                (tenant_id or "__legacy__",),
            )
            rows = cur.fetchall()
        _release(conn)
        for v, cnt in rows:
            if v in ("up", "down"):
                base[v] = int(cnt)
        base["total"] = base["up"] + base["down"]
        return base
    except Exception as exc:  # noqa: BLE001
        logger.error(f"filter_feedback totals error: {exc}")
        try:
            conn.rollback()
        except Exception:
            pass
        _release(conn, close=True)
        return base


def recent_negative(filter_key: str, section_key: str, tenant_id: str = "__legacy__",
                    limit: int = 3) -> list[dict]:
    """
    Devuelve los votos NEGATIVOS (down) mas recientes de un (filtro, apartado),
    con el texto del apartado marcado. Preparado para el few-shot futuro:
    inyectar estos ejemplos "a evitar" en el prompt de la IA. Lista vacia si PG
    no esta disponible o no hay votos.
    """
    fk = str(filter_key or "").strip().lower()
    sk = str(section_key or "").strip().lower()[:_MAX_SECTION_LEN]
    if fk not in VALID_FILTERS or not sk or not is_available():
        return []
    conn = _conn()
    if conn is None:
        return []
    try:
        _ensure_table(conn)
        with conn.cursor() as cur:
            cur.execute(
                "SELECT text_excerpt, section_text, created_at "
                "FROM filter_feedback "
                "WHERE tenant_id = %s AND filter_key = %s AND section_key = %s "
                "AND vote = 'down' AND section_text <> '' "
                "ORDER BY created_at DESC LIMIT %s",
                (tenant_id or "__legacy__", fk, sk, int(limit)),
            )
            rows = cur.fetchall()
        _release(conn)
        return [
            {"text_excerpt": r[0] or "", "section_text": r[1] or "",
             "created_at": r[2].isoformat() if hasattr(r[2], "isoformat") else str(r[2])}
            for r in rows
        ]
    except Exception as exc:
        logger.error(f"filter_feedback recent_negative error: {exc}")
        try:
            conn.rollback()
        except Exception:
            pass
        _release(conn, close=True)
        return []
