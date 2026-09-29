# -*- coding: utf-8 -*-
"""
api_keys.py — Claves de API por empresa (tenant) para la API publica de analisis.

QUE ES
------
Permite que sistemas externos (un CRM, un bot de WhatsApp, otra app de la
empresa) envien textos a analizar SIN iniciar sesion, autenticandose con una
clave de API. Cada clave pertenece a un tenant, de modo que el analisis queda
aislado por empresa igual que en la app web.

SEGURIDAD
---------
- La clave se muestra UNA sola vez al crearla; en la base se guarda solo su HASH
  (SHA-256). Si se pierde, se genera otra: no se puede "recuperar" la original.
- Se puede desactivar una clave sin borrarla (active=false).
- Tabla propia `api_keys`. No toca ninguna otra tabla.
- Best-effort: si PG no esta, validar devuelve None (acceso denegado) y crear
  devuelve None.
"""
from __future__ import annotations

import hashlib
import logging
import secrets

logger = logging.getLogger(__name__)

_table_ready = False
_PREFIX = "ak_"  # prefijo legible de las claves (no secreto)


def _hash(raw: str) -> str:
    return hashlib.sha256((raw or "").encode("utf-8")).hexdigest()


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
            CREATE TABLE IF NOT EXISTS api_keys (
                key_hash    TEXT        NOT NULL,
                tenant_id   TEXT        NOT NULL DEFAULT '__legacy__',
                label       TEXT        NOT NULL DEFAULT '',
                active      BOOLEAN     NOT NULL DEFAULT TRUE,
                created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
                last_used   TIMESTAMPTZ,
                PRIMARY KEY (key_hash)
            )
            """
        )
        cur.execute(
            "CREATE INDEX IF NOT EXISTS idx_apikeys_tenant ON api_keys (tenant_id)"
        )
    conn.commit()
    _table_ready = True


def create_key(tenant_id: str, label: str = "") -> str | None:
    """
    Genera una clave nueva para el tenant, guarda su HASH y devuelve la clave EN
    CLARO (unica vez que se ve). None si PG no esta o falla.
    """
    if not is_available():
        return None
    raw = _PREFIX + secrets.token_urlsafe(32)
    conn = _conn()
    if conn is None:
        return None
    try:
        _ensure_table(conn)
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO api_keys (key_hash, tenant_id, label) VALUES (%s, %s, %s)",
                (_hash(raw), tenant_id or "__legacy__", str(label or "")[:120]),
            )
        conn.commit()
        _release(conn)
        return raw
    except Exception as exc:  # noqa: BLE001
        logger.error(f"api_keys create error: {exc}")
        try:
            conn.rollback()
        except Exception:
            pass
        _release(conn, close=True)
        return None


def resolve_tenant(raw_key: str) -> str | None:
    """
    Valida una clave en claro. Si es valida y esta activa, devuelve su tenant_id
    y actualiza last_used. None si no existe, esta inactiva o PG no disponible.
    """
    raw = (raw_key or "").strip()
    if not raw or not is_available():
        return None
    conn = _conn()
    if conn is None:
        return None
    try:
        _ensure_table(conn)
        with conn.cursor() as cur:
            cur.execute(
                "SELECT tenant_id FROM api_keys WHERE key_hash = %s AND active = TRUE LIMIT 1",
                (_hash(raw),),
            )
            row = cur.fetchone()
            if row:
                cur.execute(
                    "UPDATE api_keys SET last_used = now() WHERE key_hash = %s",
                    (_hash(raw),),
                )
                conn.commit()
        _release(conn)
        return row[0] if row else None
    except Exception as exc:  # noqa: BLE001
        logger.error(f"api_keys resolve error: {exc}")
        try:
            conn.rollback()
        except Exception:
            pass
        _release(conn, close=True)
        return None


def list_keys(tenant_id: str) -> list[dict]:
    """
    Lista las claves del tenant (SIN la clave en claro: solo metadata). Muestra
    un prefijo/hint del hash para identificarlas.
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
                "SELECT key_hash, label, active, created_at, last_used "
                "FROM api_keys WHERE tenant_id = %s ORDER BY created_at DESC",
                (tenant_id or "__legacy__",),
            )
            rows = cur.fetchall()
        _release(conn)
        out = []
        for r in rows:
            out.append({
                "hint": (r[0] or "")[:8],  # primeros 8 chars del hash, para identificar
                "label": r[1] or "",
                "active": bool(r[2]),
                "created_at": r[3].isoformat() if hasattr(r[3], "isoformat") else str(r[3]),
                "last_used": r[4].isoformat() if (r[4] and hasattr(r[4], "isoformat")) else None,
            })
        return out
    except Exception as exc:  # noqa: BLE001
        logger.error(f"api_keys list error: {exc}")
        try:
            conn.rollback()
        except Exception:
            pass
        _release(conn, close=True)
        return []


def deactivate(tenant_id: str, hint: str) -> bool:
    """
    Desactiva una clave del tenant identificada por el 'hint' (prefijo del hash).
    Best-effort. True si desactivo al menos una.
    """
    h = (hint or "").strip()
    if not h or not is_available():
        return False
    conn = _conn()
    if conn is None:
        return False
    try:
        _ensure_table(conn)
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE api_keys SET active = FALSE "
                "WHERE tenant_id = %s AND key_hash LIKE %s",
                (tenant_id or "__legacy__", h + "%"),
            )
            n = cur.rowcount
        conn.commit()
        _release(conn)
        return n > 0
    except Exception as exc:  # noqa: BLE001
        logger.error(f"api_keys deactivate error: {exc}")
        try:
            conn.rollback()
        except Exception:
            pass
        _release(conn, close=True)
        return False
