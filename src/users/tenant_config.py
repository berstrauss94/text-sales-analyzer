# -*- coding: utf-8 -*-
"""
tenant_config.py — Configuracion por empresa (tenant). Hoy guarda el "rubro"
del negocio, que adapta el CONTEXTO de las explicaciones de la IA.

QUE ES EL "MODO RUBRO"
----------------------
El sistema nacio para inmobiliarias, pero el nucleo (analisis de conversaciones
de venta + IA que explica) sirve para cualquier venta consultiva. El modo rubro
permite que cada empresa declare su rubro (inmobiliaria, autos, seguros, etc.).
Esto NO reentrena el modelo ML (sigue detectando intencion/sentimiento igual):
lo que cambia es el CONTEXTO que se le da a la IA al redactar las explicaciones,
para que hable en el lenguaje del negocio de esa empresa.

Es opt-in y seguro: si un tenant no tiene rubro configurado, se usa
'inmobiliaria' (comportamiento actual, sin cambios).

DISENO
------
- Tabla propia `tenant_config` (tenant_id PK). No toca ninguna otra tabla.
- Best-effort: si PG no esta, devuelve el rubro por defecto.
- Cache en memoria por proceso (el rubro cambia rara vez) para no consultar la
  base en cada analisis.
"""
from __future__ import annotations

import logging
import threading
import time

logger = logging.getLogger(__name__)

_table_ready = False
_DEFAULT_RUBRO = "inmobiliaria"

# Rubros conocidos con una etiqueta legible. Es abierto: se acepta cualquier
# texto corto como rubro; estos son solo los sugeridos/validados para la UI.
RUBROS_CONOCIDOS = {
    "inmobiliaria": "Inmobiliaria / bienes raices",
    "automotriz": "Venta de autos / concesionaria",
    "seguros": "Seguros",
    "tecnologia": "Tecnologia / software",
    "retail": "Retail / comercio",
    "servicios": "Servicios profesionales",
    "generico": "Ventas en general",
}

# Cache simple {tenant_id: (rubro, epoch_guardado)} con TTL corto.
_cache: dict[str, tuple[str, float]] = {}
_cache_lock = threading.Lock()
_CACHE_TTL = 120.0  # segundos


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
            CREATE TABLE IF NOT EXISTS tenant_config (
                tenant_id   TEXT        NOT NULL,
                rubro       TEXT        NOT NULL DEFAULT 'inmobiliaria',
                descripcion TEXT        NOT NULL DEFAULT '',
                updated_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
                PRIMARY KEY (tenant_id)
            )
            """
        )
    conn.commit()
    _table_ready = True


def get_rubro(tenant_id: str = "__legacy__") -> str:
    """
    Devuelve el rubro de la empresa. Default 'inmobiliaria' si no esta
    configurado o PG no disponible. Usa cache en memoria (TTL corto).
    """
    tid = tenant_id or "__legacy__"
    now = time.time()
    with _cache_lock:
        cached = _cache.get(tid)
        if cached and (now - cached[1]) < _CACHE_TTL:
            return cached[0]
    rubro = _DEFAULT_RUBRO
    if is_available():
        conn = _conn()
        if conn is not None:
            try:
                _ensure_table(conn)
                with conn.cursor() as cur:
                    cur.execute(
                        "SELECT rubro FROM tenant_config WHERE tenant_id = %s LIMIT 1",
                        (tid,),
                    )
                    row = cur.fetchone()
                _release(conn)
                if row and row[0]:
                    rubro = str(row[0])
            except Exception as exc:  # noqa: BLE001
                logger.error(f"tenant_config get_rubro error: {exc}")
                try:
                    conn.rollback()
                except Exception:
                    pass
                _release(conn, close=True)
    with _cache_lock:
        _cache[tid] = (rubro, now)
    return rubro


def get_config(tenant_id: str = "__legacy__") -> dict:
    """Devuelve {rubro, descripcion} del tenant. Defaults si no existe."""
    base = {"rubro": _DEFAULT_RUBRO, "descripcion": ""}
    if not is_available():
        return base
    conn = _conn()
    if conn is None:
        return base
    try:
        _ensure_table(conn)
        with conn.cursor() as cur:
            cur.execute(
                "SELECT rubro, descripcion FROM tenant_config WHERE tenant_id = %s LIMIT 1",
                (tenant_id or "__legacy__",),
            )
            row = cur.fetchone()
        _release(conn)
        if row:
            return {"rubro": row[0] or _DEFAULT_RUBRO, "descripcion": row[1] or ""}
        return base
    except Exception as exc:  # noqa: BLE001
        logger.error(f"tenant_config get_config error: {exc}")
        try:
            conn.rollback()
        except Exception:
            pass
        _release(conn, close=True)
        return base


def set_config(tenant_id: str, rubro: str, descripcion: str = "") -> bool:
    """Guarda (upsert) el rubro/descripcion de la empresa. Best-effort."""
    tid = tenant_id or "__legacy__"
    r = (str(rubro or "").strip().lower() or _DEFAULT_RUBRO)[:40]
    d = str(descripcion or "").strip()[:300]
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
                INSERT INTO tenant_config (tenant_id, rubro, descripcion, updated_at)
                VALUES (%s, %s, %s, now())
                ON CONFLICT (tenant_id) DO UPDATE SET
                    rubro = EXCLUDED.rubro,
                    descripcion = EXCLUDED.descripcion,
                    updated_at = now()
                """,
                (tid, r, d),
            )
        conn.commit()
        _release(conn)
        # Invalidar cache de este tenant.
        with _cache_lock:
            _cache.pop(tid, None)
        return True
    except Exception as exc:  # noqa: BLE001
        logger.error(f"tenant_config set_config error: {exc}")
        try:
            conn.rollback()
        except Exception:
            pass
        _release(conn, close=True)
        return False


def rubro_contexto(rubro: str) -> str:
    """
    Devuelve una frase de contexto para el prompt de la IA segun el rubro. Para
    'inmobiliaria' devuelve el texto historico (comportamiento actual intacto).
    """
    r = (rubro or _DEFAULT_RUBRO).strip().lower()
    mapa = {
        "inmobiliaria": "conversaciones de ventas inmobiliarias (bienes raices)",
        "automotriz": "conversaciones de venta de autos / concesionaria",
        "seguros": "conversaciones de venta de seguros",
        "tecnologia": "conversaciones de venta de tecnologia / software",
        "retail": "conversaciones de venta en retail / comercio",
        "servicios": "conversaciones de venta de servicios profesionales",
        "generico": "conversaciones de venta consultiva",
    }
    return mapa.get(r, f"conversaciones de venta ({r})")
