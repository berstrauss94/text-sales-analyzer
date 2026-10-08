# -*- coding: utf-8 -*-
"""
system_lock_pg.py — Interruptor de bloqueo del sistema persistido en PostgreSQL.

QUE ES
------
Un unico "candado" global de la plataforma que controla el superadmin
(Berna.Strauss). Cuando esta activado, ningun otro usuario (comun o admin)
puede ingresar: ven el aviso naranja "Sistema bloqueado por falta de pago".
Sirve como corte por falta de pago al administrador de la plataforma.

POR QUE PostgreSQL
------------------
En produccion (Railway) el disco es efimero: un archivo JSON se borra en cada
redeploy. Para que el bloqueo SOBREVIVA a los redeploys, el estado se guarda en
una tabla propia de PostgreSQL, igual que business_config.py.

DISENO
------
- Tabla propia system_lock con una sola fila (lock_key = 'global').
- Best-effort: si PG no esta disponible (dev local), devuelve "no bloqueado".
  El wrapper system_lock.py se encarga del fallback a JSON local en ese caso.
"""
from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

_table_ready = False

# Clave fija de la unica fila: el bloqueo es global a toda la plataforma.
_LOCK_KEY = "global"


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
            CREATE TABLE IF NOT EXISTS system_lock (
                lock_key    TEXT        NOT NULL,
                locked      BOOLEAN     NOT NULL DEFAULT FALSE,
                updated_by  TEXT,
                updated_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
                PRIMARY KEY (lock_key)
            )
            """
        )
    conn.commit()
    _table_ready = True


def get_state() -> dict:
    """Estado del bloqueo global. Si PG no esta, devuelve no-bloqueado."""
    base = {"locked": False, "updated_at": None, "updated_by": None}
    if not is_available():
        return base
    conn = _conn()
    if conn is None:
        return base
    try:
        _ensure_table(conn)
        with conn.cursor() as cur:
            cur.execute(
                "SELECT locked, updated_at, updated_by FROM system_lock "
                "WHERE lock_key = %s LIMIT 1",
                (_LOCK_KEY,),
            )
            row = cur.fetchone()
        _release(conn)
        if not row:
            return base
        return {
            "locked": bool(row[0]),
            "updated_at": row[1].isoformat() if row[1] else None,
            "updated_by": row[2],
        }
    except Exception as exc:  # noqa: BLE001
        logger.error(f"system_lock get error: {exc}")
        try:
            conn.rollback()
        except Exception:
            pass
        _release(conn, close=True)
        return base


def is_locked() -> bool:
    """True si el sistema esta bloqueado por falta de pago."""
    return bool(get_state().get("locked", False))


def set_locked(locked: bool, updated_by: str = "") -> bool:
    """Guarda (upsert) el estado del bloqueo global. Best-effort."""
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
                INSERT INTO system_lock (lock_key, locked, updated_by, updated_at)
                VALUES (%s, %s, %s, now())
                ON CONFLICT (lock_key) DO UPDATE SET
                    locked     = EXCLUDED.locked,
                    updated_by = EXCLUDED.updated_by,
                    updated_at = now()
                """,
                (_LOCK_KEY, bool(locked), str(updated_by or "")[:120]),
            )
        conn.commit()
        _release(conn)
        return True
    except Exception as exc:  # noqa: BLE001
        logger.error(f"system_lock set error: {exc}")
        try:
            conn.rollback()
        except Exception:
            pass
        _release(conn, close=True)
        return False
