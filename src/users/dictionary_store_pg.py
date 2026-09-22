# -*- coding: utf-8 -*-
"""
PostgreSQL-backed dictionary overrides (user-contributed phrases).

WHY THIS EXISTS
---------------
The analysis engine ships a fixed base dictionary of phrases per indicator
(commercial_analyzer._INDICADOR_CATEGORIAS). Users add their own words/phrases
via the "Resaltar y definir" tool. Those additions must:
  - persist globally (affect everyone's analysis), and
  - be manageable (deleted, or moved to another category) via a modal,
without ever touching the base dictionary shipped in code.

This module stores ONLY those user-contributed phrases in a durable table
(dictionary_overrides). The engine reads them and ADDS them to the base
categories at analysis time (as an extra "agregadas" subcategory), so the base
phrases are never modified or lost.

Reuses the history_manager connection pool. All writes are best-effort and
wrapped in try/except so a failure never breaks the caller.
"""
from __future__ import annotations

import logging
import time as _time

logger = logging.getLogger(__name__)

# The 7 valid indicator/category keys a phrase can belong to.
VALID_CATEGORIES = {
    "palabras_positivas", "respuestas_afirmativas", "indicios_cierre",
    "escasez_comercial", "pedidos_referidos", "objeciones",
    "indicios_prospeccion",
}

# ── Performance ────────────────────────────────────────────────────────────
# The dictionary is read on EVERY text analysis. Hitting PostgreSQL each time
# (a SELECT of ~hundreds of phrases) made analysis slow. We cache the grouped
# phrases in memory with a short TTL and invalidate on any write, so analysis
# reads from RAM in the common case. Per-process cache (safe across gunicorn
# workers — each has its own; the TTL bounds staleness anyway).
# Tenant por defecto (multi-tenant Fase 1). Mientras la sesion no provea un
# tenant (llega en la Fase 3), todo cae en este tenant, dejando el comportamiento
# actual IDENTICO para la empresa existente. El aislamiento por tenant ya queda
# implementado en el esquema y las consultas.
DEFAULT_TENANT = "__legacy__"

_CACHE_TTL_SECONDS = 60.0
# Cache POR TENANT: { tenant_id: {category: [phrase, ...]} } y su timestamp.
# Antes era un unico cache global; en multi-tenant cada empresa tiene el suyo,
# para que el diccionario de una no se mezcle con el de otra.
_cache_by_tenant: dict = {}
_cache_ts_by_tenant: dict = {}
# _ensure_table runs a DDL round-trip; only needed once per process.
_table_ready = False


def _invalidate_cache(tenant_id: str | None = None) -> None:
    """
    Drop the in-memory cache so the next read reflects fresh writes. Si se pasa
    tenant_id, invalida solo el de ese tenant; si no, invalida todos.
    """
    global _cache_by_tenant, _cache_ts_by_tenant
    if tenant_id is None:
        _cache_by_tenant = {}
        _cache_ts_by_tenant = {}
    else:
        _cache_by_tenant.pop(tenant_id, None)
        _cache_ts_by_tenant.pop(tenant_id, None)


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
    """Create the dictionary_overrides table + index if they don't exist.

    Runs the DDL only ONCE per process (guarded by _table_ready) to avoid a
    round-trip to PostgreSQL on every call.
    """
    global _table_ready
    if _table_ready:
        return
    with conn.cursor() as cur:
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS dictionary_overrides (
                id        BIGSERIAL   PRIMARY KEY,
                tenant_id TEXT        NOT NULL DEFAULT '__legacy__',
                phrase    TEXT        NOT NULL,
                category  TEXT        NOT NULL,
                added_by  TEXT        NOT NULL DEFAULT '',
                ts        TIMESTAMPTZ NOT NULL DEFAULT now()
            )
            """
        )
        # Migracion segura para tablas ya existentes: agregar tenant_id si falta.
        # Todas las filas actuales quedan en '__legacy__' sin perder nada.
        cur.execute(
            "ALTER TABLE dictionary_overrides "
            "ADD COLUMN IF NOT EXISTS tenant_id TEXT NOT NULL DEFAULT '__legacy__'"
        )
        # Indice unico AHORA POR TENANT: la misma frase puede existir en dos
        # empresas distintas sin colisionar. Se crea el nuevo y se descarta el
        # viejo global si existiera.
        cur.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS idx_dictov_tenant_phrase_cat "
            "ON dictionary_overrides (tenant_id, lower(phrase), category)"
        )
        cur.execute("DROP INDEX IF EXISTS idx_dictov_phrase_cat")
    conn.commit()
    _table_ready = True


def add_phrase(phrase: str, category: str, added_by: str = "",
               tenant_id: str = DEFAULT_TENANT) -> bool:
    """
    Add a user phrase to a category, WITHIN a tenant. Idempotent: un duplicado
    (misma frase+categoria+tenant) se ignora. Returns True on success.
    """
    phrase = (phrase or "").strip()
    tenant_id = tenant_id or DEFAULT_TENANT
    if not phrase or category not in VALID_CATEGORIES or not is_available():
        return False
    conn = _conn()
    if conn is None:
        return False
    try:
        _ensure_table(conn)
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO dictionary_overrides (tenant_id, phrase, category, added_by) "
                "VALUES (%s, %s, %s, %s) "
                "ON CONFLICT (tenant_id, lower(phrase), category) DO NOTHING",
                (tenant_id, phrase, category, added_by or ""),
            )
        conn.commit()
        _invalidate_cache(tenant_id)
        _release(conn)
        return True
    except Exception as exc:
        logger.error(f"dictionary_overrides add error: {exc}")
        try:
            conn.rollback()
        except Exception:
            pass
        _release(conn, close=True)
        return False


def list_phrases(tenant_id: str = DEFAULT_TENANT) -> list[dict]:
    """
    Return the override phrases OF A TENANT as a list of dicts:
      [{ "id": int, "phrase": str, "category": str, "added_by": str, "ts": iso }]
    Empty list if PG is unavailable.
    """
    tenant_id = tenant_id or DEFAULT_TENANT
    if not is_available():
        return []
    conn = _conn()
    if conn is None:
        return []
    try:
        _ensure_table(conn)
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, phrase, category, added_by, ts "
                "FROM dictionary_overrides WHERE tenant_id = %s "
                "ORDER BY category ASC, ts DESC",
                (tenant_id,),
            )
            rows = cur.fetchall()
        _release(conn)
        out = []
        for r in rows:
            out.append({
                "id": r[0], "phrase": r[1], "category": r[2],
                "added_by": r[3] or "",
                "ts": r[4].isoformat() if hasattr(r[4], "isoformat") else str(r[4]),
            })
        return out
    except Exception as exc:
        logger.error(f"dictionary_overrides list error: {exc}")
        try:
            conn.rollback()
        except Exception:
            pass
        _release(conn, close=True)
        return []


def phrases_by_category(tenant_id: str = DEFAULT_TENANT) -> dict:
    """
    Return { category: [phrase, ...], ... } for the analysis engine, DEL TENANT
    indicado.

    CACHED en memoria POR TENANT con TTL corto: se lee en cada analisis de texto.
    El cache se invalida en cualquier escritura del tenant y expira tras
    _CACHE_TTL_SECONDS.
    """
    tenant_id = tenant_id or DEFAULT_TENANT
    now = _time.time()
    cached = _cache_by_tenant.get(tenant_id)
    ts = _cache_ts_by_tenant.get(tenant_id, 0.0)
    if cached is not None and (now - ts) < _CACHE_TTL_SECONDS:
        return cached
    grouped: dict = {}
    for row in list_phrases(tenant_id):
        grouped.setdefault(row["category"], []).append(row["phrase"])
    _cache_by_tenant[tenant_id] = grouped
    _cache_ts_by_tenant[tenant_id] = now
    return grouped


def count_phrases(tenant_id: str = DEFAULT_TENANT) -> int:
    """Return how many override rows exist FOR A TENANT (0 if unavailable)."""
    tenant_id = tenant_id or DEFAULT_TENANT
    if not is_available():
        return 0
    conn = _conn()
    if conn is None:
        return 0
    try:
        _ensure_table(conn)
        with conn.cursor() as cur:
            cur.execute(
                "SELECT COUNT(*) FROM dictionary_overrides WHERE tenant_id = %s",
                (tenant_id,),
            )
            n = cur.fetchone()[0]
        _release(conn)
        return int(n or 0)
    except Exception as exc:
        logger.error(f"dictionary_overrides count error: {exc}")
        try:
            conn.rollback()
        except Exception:
            pass
        _release(conn, close=True)
        return 0


def seed_from_base(base_by_category: dict, tenant_id: str = DEFAULT_TENANT) -> int:
    """
    One-time seed POR TENANT: si el tenant no tiene frases aun, lo puebla con
    todas las frases base, para que el editor muestre el diccionario completo y
    el motor lea todo de una unica fuente editable.

    base_by_category: { category: [phrase, ...] }. Categorias fuera de
    VALID_CATEGORIES se ignoran. Devuelve cuantas frases se insertaron (0 si el
    tenant ya tenia filas, o PG no esta disponible).
    """
    tenant_id = tenant_id or DEFAULT_TENANT
    if not is_available():
        return 0
    # Only seed when empty (for this tenant), so we never duplicate/overwrite.
    if count_phrases(tenant_id) > 0:
        return 0
    conn = _conn()
    if conn is None:
        return 0
    inserted = 0
    try:
        _ensure_table(conn)
        with conn.cursor() as cur:
            for category, phrases in (base_by_category or {}).items():
                if category not in VALID_CATEGORIES:
                    continue
                for phrase in phrases:
                    p = (phrase or "").strip()
                    if not p:
                        continue
                    cur.execute(
                        "INSERT INTO dictionary_overrides (tenant_id, phrase, category, added_by) "
                        "VALUES (%s, %s, %s, %s) "
                        "ON CONFLICT (tenant_id, lower(phrase), category) DO NOTHING",
                        (tenant_id, p, category, "sistema"),
                    )
                    if cur.rowcount > 0:
                        inserted += 1
        conn.commit()
        _invalidate_cache(tenant_id)
        _release(conn)
        logger.info(f"dictionary_overrides seeded with {inserted} base phrases (tenant={tenant_id})")
        return inserted
    except Exception as exc:
        logger.error(f"dictionary_overrides seed error: {exc}")
        try:
            conn.rollback()
        except Exception:
            pass
        _release(conn, close=True)
        return 0


def delete_phrase(override_id: int, tenant_id: str = DEFAULT_TENANT) -> bool:
    """
    Delete an override phrase by its id, SOLO si pertenece al tenant dado. Asi
    una empresa no puede borrar una frase de otra pasando un id ajeno.
    Returns True if a row was removed.
    """
    tenant_id = tenant_id or DEFAULT_TENANT
    if not is_available():
        return False
    conn = _conn()
    if conn is None:
        return False
    try:
        _ensure_table(conn)
        with conn.cursor() as cur:
            cur.execute(
                "DELETE FROM dictionary_overrides WHERE id = %s AND tenant_id = %s",
                (int(override_id), tenant_id),
            )
            removed = cur.rowcount > 0
        conn.commit()
        _invalidate_cache(tenant_id)
        _release(conn)
        return removed
    except Exception as exc:
        logger.error(f"dictionary_overrides delete error: {exc}")
        try:
            conn.rollback()
        except Exception:
            pass
        _release(conn, close=True)
        return False


def move_phrase(override_id: int, new_category: str,
                tenant_id: str = DEFAULT_TENANT) -> bool:
    """
    Move an override phrase to another category, SOLO si pertenece al tenant
    dado. Returns True on success.
    """
    tenant_id = tenant_id or DEFAULT_TENANT
    if new_category not in VALID_CATEGORIES or not is_available():
        return False
    conn = _conn()
    if conn is None:
        return False
    try:
        _ensure_table(conn)
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE dictionary_overrides SET category = %s "
                "WHERE id = %s AND tenant_id = %s",
                (new_category, int(override_id), tenant_id),
            )
            moved = cur.rowcount > 0
        conn.commit()
        _invalidate_cache(tenant_id)
        _release(conn)
        return moved
    except Exception as exc:
        logger.error(f"dictionary_overrides move error: {exc}")
        try:
            conn.rollback()
        except Exception:
            pass
        _release(conn, close=True)
        return False
