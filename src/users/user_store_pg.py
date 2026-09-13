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
    """Create the app_users table if it does not exist."""
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
    conn.commit()


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
    """Return {'password_hash', 'ficha'} for a user, or None if not found."""
    if not is_available():
        return None
    conn = _conn()
    if conn is None:
        return None
    try:
        _ensure_table(conn)
        with conn.cursor() as cur:
            cur.execute(
                "SELECT password_hash, ficha FROM app_users WHERE username = %s LIMIT 1",
                (username,),
            )
            row = cur.fetchone()
        _release(conn)
        if not row:
            return None
        return {"password_hash": row[0] or "", "ficha": row[1] or ""}
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
