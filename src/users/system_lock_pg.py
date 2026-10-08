# -*- coding: utf-8 -*-
"""
system_lock_pg.py — Interruptor de bloqueo del sistema persistido en PostgreSQL.

QUE ES
------
Un unico "candado" global de la plataforma que controla el superadmin
(Berna.Strauss). Cuando esta activado, bloquea el ingreso: los usuarios ven el
aviso "Sistema bloqueado por falta de pago". Sirve como corte por falta de pago.

MODOS DE BLOQUEO
----------------
- "general":   bloquea a TODOS los usuarios (salvo el superadmin).
- "selective": bloquea SOLO a los usuarios de la lista blocked_users.

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

import json
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
        # Migracion aditiva: columnas para el modo y la lista de usuarios.
        # IF NOT EXISTS hace que sea seguro ejecutarlo siempre (idempotente).
        cur.execute(
            "ALTER TABLE system_lock ADD COLUMN IF NOT EXISTS "
            "mode TEXT NOT NULL DEFAULT 'general'"
        )
        cur.execute(
            "ALTER TABLE system_lock ADD COLUMN IF NOT EXISTS "
            "blocked_users TEXT NOT NULL DEFAULT '[]'"
        )
    conn.commit()
    _table_ready = True


def _parse_users(raw) -> list:
    """Normaliza blocked_users a una lista de strings."""
    if isinstance(raw, list):
        return [str(u) for u in raw if str(u).strip()]
    if isinstance(raw, str) and raw.strip():
        try:
            data = json.loads(raw)
            if isinstance(data, list):
                return [str(u) for u in data if str(u).strip()]
        except Exception:
            pass
    return []


def get_state() -> dict:
    """Estado del bloqueo. Si PG no esta, devuelve no-bloqueado (general)."""
    base = {"locked": False, "mode": "general", "blocked_users": [],
            "updated_at": None, "updated_by": None}
    if not is_available():
        return base
    conn = _conn()
    if conn is None:
        return base
    try:
        _ensure_table(conn)
        with conn.cursor() as cur:
            cur.execute(
                "SELECT locked, mode, blocked_users, updated_at, updated_by "
                "FROM system_lock WHERE lock_key = %s LIMIT 1",
                (_LOCK_KEY,),
            )
            row = cur.fetchone()
        _release(conn)
        if not row:
            return base
        return {
            "locked": bool(row[0]),
            "mode": row[1] or "general",
            "blocked_users": _parse_users(row[2]),
            "updated_at": row[3].isoformat() if row[3] else None,
            "updated_by": row[4],
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
    """True si el bloqueo esta activo (en cualquier modo)."""
    return bool(get_state().get("locked", False))


def set_state(locked: bool, mode: str, blocked_users: list, updated_by: str = "") -> bool:
    """Guarda (upsert) el estado completo del bloqueo. Best-effort."""
    if not is_available():
        return False
    conn = _conn()
    if conn is None:
        return False
    mode = "selective" if str(mode) == "selective" else "general"
    users_json = json.dumps(_parse_users(blocked_users), ensure_ascii=False)
    try:
        _ensure_table(conn)
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO system_lock
                    (lock_key, locked, mode, blocked_users, updated_by, updated_at)
                VALUES (%s, %s, %s, %s, %s, now())
                ON CONFLICT (lock_key) DO UPDATE SET
                    locked        = EXCLUDED.locked,
                    mode          = EXCLUDED.mode,
                    blocked_users = EXCLUDED.blocked_users,
                    updated_by    = EXCLUDED.updated_by,
                    updated_at    = now()
                """,
                (_LOCK_KEY, bool(locked), mode, users_json,
                 str(updated_by or "")[:120]),
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
