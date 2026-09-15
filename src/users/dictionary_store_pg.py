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
_CACHE_TTL_SECONDS = 60.0
_cache_by_category: dict | None = None
_cache_ts: float = 0.0
# _ensure_table runs a DDL round-trip; only needed once per process.
_table_ready = False


def _invalidate_cache() -> None:
    """Drop the in-memory cache so the next read reflects fresh writes."""
    global _cache_by_category, _cache_ts
    _cache_by_category = None
    _cache_ts = 0.0


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
                id       BIGSERIAL   PRIMARY KEY,
                phrase   TEXT        NOT NULL,
                category TEXT        NOT NULL,
                added_by TEXT        NOT NULL DEFAULT '',
                ts       TIMESTAMPTZ NOT NULL DEFAULT now()
            )
            """
        )
        # Prevent exact duplicates (same phrase in the same category).
        cur.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS idx_dictov_phrase_cat "
            "ON dictionary_overrides (lower(phrase), category)"
        )
    conn.commit()
    _table_ready = True


def add_phrase(phrase: str, category: str, added_by: str = "") -> bool:
    """
    Add a user phrase to a category. Idempotent: a duplicate (same phrase+category)
    is silently ignored. Returns True on success. Best-effort.
    """
    phrase = (phrase or "").strip()
    if not phrase or category not in VALID_CATEGORIES or not is_available():
        return False
    conn = _conn()
    if conn is None:
        return False
    try:
        _ensure_table(conn)
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO dictionary_overrides (phrase, category, added_by) "
                "VALUES (%s, %s, %s) "
                "ON CONFLICT (lower(phrase), category) DO NOTHING",
                (phrase, category, added_by or ""),
            )
        conn.commit()
        _invalidate_cache()
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


def list_phrases() -> list[dict]:
    """
    Return all override phrases as a list of dicts:
      [{ "id": int, "phrase": str, "category": str, "added_by": str, "ts": iso }]
    Empty list if PG is unavailable.
    """
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
                "FROM dictionary_overrides ORDER BY category ASC, ts DESC"
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


def phrases_by_category() -> dict:
    """
    Return { category: [phrase, ...], ... } for the analysis engine.

    CACHED in memory with a short TTL: this is read on every text analysis, so
    hitting PostgreSQL each time was a real slowdown. The cache is invalidated
    on any write (add/delete/move/seed) and expires after _CACHE_TTL_SECONDS.
    """
    global _cache_by_category, _cache_ts
    now = _time.time()
    if _cache_by_category is not None and (now - _cache_ts) < _CACHE_TTL_SECONDS:
        return _cache_by_category
    grouped: dict = {}
    for row in list_phrases():
        grouped.setdefault(row["category"], []).append(row["phrase"])
    _cache_by_category = grouped
    _cache_ts = now
    return grouped


def count_phrases() -> int:
    """Return how many override rows exist (0 if unavailable)."""
    if not is_available():
        return 0
    conn = _conn()
    if conn is None:
        return 0
    try:
        _ensure_table(conn)
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM dictionary_overrides")
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


def seed_from_base(base_by_category: dict) -> int:
    """
    One-time seed: if the overrides table is EMPTY, populate it with every base
    phrase so the editor shows the full dictionary and the engine reads
    everything from a single, editable source ("segunda capa" / effective dict).

    base_by_category: { category: [phrase, ...] }. Categories not in
    VALID_CATEGORIES are ignored. Returns the number of phrases inserted (0 if
    the table already had rows, or PG is unavailable).
    """
    if not is_available():
        return 0
    # Only seed when empty, so we never duplicate or overwrite user edits.
    if count_phrases() > 0:
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
                        "INSERT INTO dictionary_overrides (phrase, category, added_by) "
                        "VALUES (%s, %s, %s) "
                        "ON CONFLICT (lower(phrase), category) DO NOTHING",
                        (p, category, "sistema"),
                    )
                    if cur.rowcount > 0:
                        inserted += 1
        conn.commit()
        _invalidate_cache()
        _release(conn)
        logger.info(f"dictionary_overrides seeded with {inserted} base phrases")
        return inserted
    except Exception as exc:
        logger.error(f"dictionary_overrides seed error: {exc}")
        try:
            conn.rollback()
        except Exception:
            pass
        _release(conn, close=True)
        return 0


def delete_phrase(override_id: int) -> bool:
    """Delete an override phrase by its id. Returns True if a row was removed."""
    if not is_available():
        return False
    conn = _conn()
    if conn is None:
        return False
    try:
        _ensure_table(conn)
        with conn.cursor() as cur:
            cur.execute("DELETE FROM dictionary_overrides WHERE id = %s", (int(override_id),))
            removed = cur.rowcount > 0
        conn.commit()
        _invalidate_cache()
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


def move_phrase(override_id: int, new_category: str) -> bool:
    """Move an override phrase to another category. Returns True on success."""
    if new_category not in VALID_CATEGORIES or not is_available():
        return False
    conn = _conn()
    if conn is None:
        return False
    try:
        _ensure_table(conn)
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE dictionary_overrides SET category = %s WHERE id = %s",
                (new_category, int(override_id)),
            )
            moved = cur.rowcount > 0
        conn.commit()
        _invalidate_cache()
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
