# -*- coding: utf-8 -*-
"""
PostgreSQL-backed persistence for user accounts (credentials + ficha).

WHY THIS EXISTS
---------------
Historically each user was stored ONLY as a plain-text file in usuarios/*.txt.
On Railway the filesystem is EPHEMERAL: it is wiped on every redeploy. So any
user registered after the last deploy would lose their credential file and:
  - disappear from the users list, and
  - be unable to log in,
even though their saved texts survived in the persistent PostgreSQL table.

This module persists the account itself (username, password hash, and the raw
ficha text) in PostgreSQL so accounts survive redeploys. The usuarios/*.txt
files remain as a local cache / dev fallback.

It reuses the connection pool from history_manager so there is a single, tested
PostgreSQL access path.
"""
from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

# _ensure_table runs a DDL round-trip; only needed once per process.
_table_ready = False


def _conn():
    """Borrow a pooled connection (or None if PG is unavailable)."""
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
    """Create the app_users table if it does not exist (once per process)."""
    global _table_ready
    if _table_ready:
        return
    with conn.cursor() as cur:
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS app_users (
                username      TEXT PRIMARY KEY,
                password_hash TEXT NOT NULL DEFAULT '',
                ficha         TEXT NOT NULL DEFAULT '',
                created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
            )
            """
        )
        # Multi-tenant Fase 3: tabla de empresas (tenants).
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS tenants (
                id         TEXT PRIMARY KEY,
                nombre     TEXT NOT NULL DEFAULT '',
                activo     BOOLEAN NOT NULL DEFAULT true,
                plan       TEXT NOT NULL DEFAULT 'basico',
                created_at TIMESTAMPTZ NOT NULL DEFAULT now()
            )
            """
        )
        # Asegurar que exista el tenant por defecto donde viven los datos actuales.
        cur.execute(
            "INSERT INTO tenants (id, nombre) VALUES ('__legacy__', 'Empresa (legacy)') "
            "ON CONFLICT (id) DO NOTHING"
        )
        # app_users gana tenant_id y rol (migracion segura para filas existentes).
        # rol: 'vendedor' | 'admin' | 'superadmin'. Todas las cuentas actuales
        # quedan en el tenant '__legacy__' y rol 'vendedor' por defecto; los
        # admins reales se ajustan en el bootstrap (ver sync_admin_roles).
        cur.execute(
            "ALTER TABLE app_users "
            "ADD COLUMN IF NOT EXISTS tenant_id TEXT NOT NULL DEFAULT '__legacy__'"
        )
        cur.execute(
            "ALTER TABLE app_users "
            "ADD COLUMN IF NOT EXISTS rol TEXT NOT NULL DEFAULT 'vendedor'"
        )
    conn.commit()
    _table_ready = True


def upsert_user(username: str, password_hash: str, ficha: str) -> bool:
    """Insert or update a user account in PostgreSQL. Returns True on success."""
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
                INSERT INTO app_users (username, password_hash, ficha)
                VALUES (%s, %s, %s)
                ON CONFLICT (username) DO UPDATE
                    SET password_hash = EXCLUDED.password_hash,
                        ficha         = EXCLUDED.ficha
                """,
                (username, password_hash, ficha),
            )
        conn.commit()
        _release(conn)
        return True
    except Exception as exc:
        logger.error(f"app_users upsert error: {exc}")
        try:
            conn.rollback()
        except Exception:
            pass
        _release(conn, close=True)
        return False


def get_user(username: str) -> dict | None:
    """Return {'password_hash', 'ficha', 'tenant_id', 'rol'} or None if not found."""
    if not is_available():
        return None
    conn = _conn()
    if conn is None:
        return None
    try:
        _ensure_table(conn)
        with conn.cursor() as cur:
            cur.execute(
                "SELECT password_hash, ficha, tenant_id, rol "
                "FROM app_users WHERE username = %s LIMIT 1",
                (username,),
            )
            row = cur.fetchone()
        _release(conn)
        if not row:
            return None
        return {
            "password_hash": row[0] or "",
            "ficha": row[1] or "",
            "tenant_id": row[2] or "__legacy__",
            "rol": row[3] or "vendedor",
        }
    except Exception as exc:
        logger.error(f"app_users get error: {exc}")
        try:
            conn.rollback()
        except Exception:
            pass
        _release(conn, close=True)
        return None


def list_usernames() -> list[str]:
    """Return all usernames stored in app_users (empty list if unavailable)."""
    if not is_available():
        return []
    conn = _conn()
    if conn is None:
        return []
    try:
        _ensure_table(conn)
        with conn.cursor() as cur:
            cur.execute("SELECT username FROM app_users")
            names = [r[0] for r in cur.fetchall() if r[0]]
        _release(conn)
        return names
    except Exception as exc:
        logger.error(f"app_users list error: {exc}")
        try:
            conn.rollback()
        except Exception:
            pass
        _release(conn, close=True)
        return []


# ---------------------------------------------------------------------------
# Multi-tenant: roles y gestion de empresas (Fase 3 / Fase 5)
# ---------------------------------------------------------------------------
def set_user_role_tenant(username: str, rol: str | None = None,
                         tenant_id: str | None = None) -> bool:
    """
    Ajusta el rol y/o el tenant de una cuenta. Best-effort. Solo actualiza los
    campos provistos (no pisa el otro).
    """
    if not username or not is_available():
        return False
    if rol is None and tenant_id is None:
        return False
    conn = _conn()
    if conn is None:
        return False
    try:
        _ensure_table(conn)
        sets, params = [], []
        if rol is not None:
            sets.append("rol = %s")
            params.append(rol)
        if tenant_id is not None:
            sets.append("tenant_id = %s")
            params.append(tenant_id)
        params.append(username)
        with conn.cursor() as cur:
            cur.execute(
                f"UPDATE app_users SET {', '.join(sets)} WHERE username = %s",
                tuple(params),
            )
            ok = cur.rowcount > 0
        conn.commit()
        _release(conn)
        return ok
    except Exception as exc:
        logger.error(f"app_users set_role_tenant error: {exc}")
        try:
            conn.rollback()
        except Exception:
            pass
        _release(conn, close=True)
        return False


def sync_admin_roles(admin_usernames, superadmin_usernames=None) -> int:
    """
    Bootstrap de roles: marca como 'admin' a las cuentas de admin_usernames y
    como 'superadmin' a las de superadmin_usernames que existan en app_users.
    Idempotente. Devuelve cuantas filas se actualizaron. Best-effort.
    """
    if not is_available():
        return 0
    conn = _conn()
    if conn is None:
        return 0
    updated = 0
    try:
        _ensure_table(conn)
        with conn.cursor() as cur:
            if admin_usernames:
                cur.execute(
                    "UPDATE app_users SET rol = 'admin' "
                    "WHERE username = ANY(%s) AND rol <> 'superadmin'",
                    (list(admin_usernames),),
                )
                updated += cur.rowcount
            if superadmin_usernames:
                cur.execute(
                    "UPDATE app_users SET rol = 'superadmin' WHERE username = ANY(%s)",
                    (list(superadmin_usernames),),
                )
                updated += cur.rowcount
        conn.commit()
        _release(conn)
        return updated
    except Exception as exc:
        logger.error(f"app_users sync_admin_roles error: {exc}")
        try:
            conn.rollback()
        except Exception:
            pass
        _release(conn, close=True)
        return 0


def create_tenant(tenant_id: str, nombre: str = "", plan: str = "basico") -> bool:
    """Crea una empresa (tenant). Idempotente. Best-effort."""
    tenant_id = (tenant_id or "").strip()
    if not tenant_id or not is_available():
        return False
    conn = _conn()
    if conn is None:
        return False
    try:
        _ensure_table(conn)
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO tenants (id, nombre, plan) VALUES (%s, %s, %s) "
                "ON CONFLICT (id) DO NOTHING",
                (tenant_id, nombre or tenant_id, plan or "basico"),
            )
        conn.commit()
        _release(conn)
        return True
    except Exception as exc:
        logger.error(f"tenants create error: {exc}")
        try:
            conn.rollback()
        except Exception:
            pass
        _release(conn, close=True)
        return False


def list_tenants() -> list[dict]:
    """Lista de empresas: [{id, nombre, activo, plan, created_at}]. []."""
    if not is_available():
        return []
    conn = _conn()
    if conn is None:
        return []
    try:
        _ensure_table(conn)
        with conn.cursor() as cur:
            cur.execute("SELECT id, nombre, activo, plan, created_at FROM tenants ORDER BY id ASC")
            rows = cur.fetchall()
        _release(conn)
        return [{
            "id": r[0], "nombre": r[1], "activo": bool(r[2]), "plan": r[3],
            "created_at": r[4].isoformat() if hasattr(r[4], "isoformat") else str(r[4]),
        } for r in rows]
    except Exception as exc:
        logger.error(f"tenants list error: {exc}")
        try:
            conn.rollback()
        except Exception:
            pass
        _release(conn, close=True)
        return []


def is_tenant_active(tenant_id: str) -> bool:
    """
    True si el tenant existe y esta activo. Un tenant desconocido se considera
    ACTIVO (para no bloquear el login del tenant '__legacy__' antes de crearlo).
    """
    tenant_id = (tenant_id or "").strip()
    if not tenant_id or not is_available():
        return True
    conn = _conn()
    if conn is None:
        return True
    try:
        _ensure_table(conn)
        with conn.cursor() as cur:
            cur.execute("SELECT activo FROM tenants WHERE id = %s LIMIT 1", (tenant_id,))
            row = cur.fetchone()
        _release(conn)
        if row is None:
            return True  # tenant no registrado aun -> no bloquear
        return bool(row[0])
    except Exception as exc:
        logger.error(f"tenants is_active error: {exc}")
        try:
            conn.rollback()
        except Exception:
            pass
        _release(conn, close=True)
        return True
