# -*- coding: utf-8 -*-
"""
ai_cache.py — Cache de las explicaciones generadas por la IA para el refinamiento
de filtros, persistida en PostgreSQL en una tabla SEPARADA (ai_refine_cache).

POR QUE
-------
Cada analisis llama a Gemini con bastante contexto (todos los filtros). Si el
MISMO texto se reanaliza (algo comun: los admin reabren textos guardados), se
pagaria y se esperaria de nuevo por una respuesta identica. Esta cache guarda el
resultado del refinamiento y lo reutiliza:
  - Ahorra costo de API (no se vuelve a llamar a Gemini).
  - Responde al instante (sin la latencia de la IA).
  - Da resiliencia: si Gemini esta lento/caido, un texto ya cacheado sigue
    mostrando buenas explicaciones en vez de caer al fallback generico.

DISENO
------
- Tabla propia `ai_refine_cache`. NUNCA toca analysis_history ni los informes.
- La clave es un hash de (texto + etiquetas/valores detectados + modelo +
  version de prompt). Si cambia cualquiera, es una entrada distinta.
- TTL configurable (por defecto 30 dias): entradas viejas se ignoran (y se
  pueden limpiar). Version de prompt (_PROMPT_VERSION): subirla invalida toda la
  cache vieja cuando mejoramos el prompt de la IA.
- Multi-tenant: aislado por tenant_id. Best-effort: cualquier fallo se traga y
  se comporta como "no hay cache" (se llama a la IA normal).
"""
from __future__ import annotations

import hashlib
import json
import logging

logger = logging.getLogger(__name__)

_table_ready = False

# Subir esta version invalida TODA la cache anterior (p. ej. al mejorar el prompt
# o cambiar la forma del JSON de la IA). Es la forma segura de "refrescar todo".
_PROMPT_VERSION = "v1"

# Vida util de una entrada, en dias. Pasado esto, se ignora.
_TTL_DIAS = 30


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
            CREATE TABLE IF NOT EXISTS ai_refine_cache (
                cache_key   TEXT        NOT NULL,
                tenant_id   TEXT        NOT NULL DEFAULT '__legacy__',
                payload     JSONB       NOT NULL,
                model       TEXT        NOT NULL DEFAULT '',
                created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
                PRIMARY KEY (cache_key)
            )
            """
        )
        cur.execute(
            "CREATE INDEX IF NOT EXISTS idx_airc_tenant_created "
            "ON ai_refine_cache (tenant_id, created_at DESC)"
        )
    conn.commit()
    _table_ready = True


def make_key(text: str, intent: str, sentiment: str, sales_keys, re_keys,
             com_vals: dict, model: str, tenant_id: str = "__legacy__") -> str:
    """
    Construye una clave estable a partir de todo lo que determina el resultado
    del refinamiento. Si cualquiera cambia, la clave cambia (cache miss).
    """
    material = {
        "t": (text or "").strip(),
        "i": intent or "",
        "s": sentiment or "",
        "sc": sorted(sales_keys or []),
        "rc": sorted(re_keys or []),
        "cv": {k: com_vals.get(k, "") for k in sorted((com_vals or {}).keys())},
        "m": model or "",
        "pv": _PROMPT_VERSION,
        "tenant": tenant_id or "__legacy__",
    }
    raw = json.dumps(material, ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def get(cache_key: str, tenant_id: str = "__legacy__") -> dict | None:
    """
    Devuelve el payload cacheado (dict con las secciones de IA) si existe y no
    expiro. None si no hay, expiro o PG no esta disponible.
    """
    if not cache_key or not is_available():
        return None
    conn = _conn()
    if conn is None:
        return None
    try:
        _ensure_table(conn)
        with conn.cursor() as cur:
            cur.execute(
                "SELECT payload FROM ai_refine_cache "
                "WHERE cache_key = %s AND tenant_id = %s "
                "AND created_at > now() - (%s || ' days')::interval "
                "LIMIT 1",
                (cache_key, tenant_id or "__legacy__", str(_TTL_DIAS)),
            )
            row = cur.fetchone()
        _release(conn)
        if not row:
            return None
        payload = row[0]
        if isinstance(payload, dict):
            return payload
        return json.loads(payload) if payload else None
    except Exception as exc:  # noqa: BLE001
        logger.error(f"ai_refine_cache get error: {exc}")
        try:
            conn.rollback()
        except Exception:
            pass
        _release(conn, close=True)
        return None


def put(cache_key: str, payload: dict, model: str = "",
        tenant_id: str = "__legacy__") -> bool:
    """
    Guarda (upsert) el payload de refinamiento. Best-effort. True si guardo.
    """
    if not cache_key or not isinstance(payload, dict) or not is_available():
        return False
    conn = _conn()
    if conn is None:
        return False
    try:
        _ensure_table(conn)
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO ai_refine_cache (cache_key, tenant_id, payload, model, created_at)
                VALUES (%s, %s, %s, %s, now())
                ON CONFLICT (cache_key) DO UPDATE SET
                    payload = EXCLUDED.payload,
                    model = EXCLUDED.model,
                    created_at = now()
                """,
                (cache_key, tenant_id or "__legacy__",
                 json.dumps(payload, ensure_ascii=False), model or ""),
            )
        conn.commit()
        _release(conn)
        return True
    except Exception as exc:  # noqa: BLE001
        logger.error(f"ai_refine_cache put error: {exc}")
        try:
            conn.rollback()
        except Exception:
            pass
        _release(conn, close=True)
        return False


def stats(tenant_id: str = "__legacy__") -> dict:
    """Cantidad de entradas cacheadas del tenant. {} si PG no esta."""
    if not is_available():
        return {}
    conn = _conn()
    if conn is None:
        return {}
    try:
        _ensure_table(conn)
        with conn.cursor() as cur:
            cur.execute(
                "SELECT COUNT(*) FROM ai_refine_cache WHERE tenant_id = %s",
                (tenant_id or "__legacy__",),
            )
            n = cur.fetchone()[0]
        _release(conn)
        return {"entries": int(n)}
    except Exception as exc:  # noqa: BLE001
        logger.error(f"ai_refine_cache stats error: {exc}")
        try:
            conn.rollback()
        except Exception:
            pass
        _release(conn, close=True)
        return {}
