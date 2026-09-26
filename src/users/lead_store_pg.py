# -*- coding: utf-8 -*-
"""
lead_store_pg.py — Fichas de Lead / CRM por vendedor, persistidas en PostgreSQL.

QUE ES
------
Cada vendedor tiene DOS casillas persistentes (no temporales) que ve apenas
entra al sistema, ademas del texto principal de analisis:
  - CRM:  un texto libre para volcar informacion del cliente / seguimiento.
  - LEAD: una ficha estructurada del lead (nombre, contacto, tipo de operacion,
          presupuesto, zona, estado, notas).

Se guarda UNA fila por (tenant_id, username): la casilla es del vendedor y se
sobrescribe al guardar (upsert). Multi-tenant: aislado por tenant_id. Reutiliza
el pool de history_manager. Best-effort: un fallo nunca rompe la accion.
"""
from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

_table_ready = False

# Estados validos del lead (para el filtro de estado).
VALID_ESTADOS = {"nuevo", "seguimiento", "cerrado", "perdido"}


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
            CREATE TABLE IF NOT EXISTS lead_fichas (
                tenant_id       TEXT        NOT NULL DEFAULT '__legacy__',
                username        TEXT        NOT NULL,
                crm_text        TEXT        NOT NULL DEFAULT '',
                lead_nombre     TEXT        NOT NULL DEFAULT '',
                lead_contacto   TEXT        NOT NULL DEFAULT '',
                lead_operacion  TEXT        NOT NULL DEFAULT '',
                lead_presupuesto TEXT       NOT NULL DEFAULT '',
                lead_zona       TEXT        NOT NULL DEFAULT '',
                lead_estado     TEXT        NOT NULL DEFAULT 'nuevo',
                lead_notas      TEXT        NOT NULL DEFAULT '',
                updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
                PRIMARY KEY (tenant_id, username)
            )
            """
        )
    conn.commit()
    _table_ready = True


def get_ficha(username: str, tenant_id: str = "__legacy__") -> dict:
    """Devuelve la ficha CRM/Lead del vendedor, o una ficha vacia si no existe."""
    vacia = {
        "crm_text": "", "lead_nombre": "", "lead_contacto": "",
        "lead_operacion": "", "lead_presupuesto": "", "lead_zona": "",
        "lead_estado": "nuevo", "lead_notas": "",
    }
    if not username or not is_available():
        return vacia
    conn = _conn()
    if conn is None:
        return vacia
    try:
        _ensure_table(conn)
        with conn.cursor() as cur:
            cur.execute(
                "SELECT crm_text, lead_nombre, lead_contacto, lead_operacion, "
                "lead_presupuesto, lead_zona, lead_estado, lead_notas "
                "FROM lead_fichas WHERE tenant_id = %s AND username = %s LIMIT 1",
                (tenant_id or "__legacy__", username),
            )
            row = cur.fetchone()
        _release(conn)
        if not row:
            return vacia
        return {
            "crm_text": row[0] or "", "lead_nombre": row[1] or "",
            "lead_contacto": row[2] or "", "lead_operacion": row[3] or "",
            "lead_presupuesto": row[4] or "", "lead_zona": row[5] or "",
            "lead_estado": row[6] or "nuevo", "lead_notas": row[7] or "",
        }
    except Exception as exc:
        logger.error(f"lead_fichas get error: {exc}")
        try:
            conn.rollback()
        except Exception:
            pass
        _release(conn, close=True)
        return vacia


def save_ficha(username: str, ficha: dict, tenant_id: str = "__legacy__") -> bool:
    """
    Guarda (upsert) la ficha CRM/Lead del vendedor. Una fila por
    (tenant_id, username). Best-effort. Devuelve True si guardo.
    """
    if not username or not is_available():
        return False
    f = ficha or {}
    estado = str(f.get("lead_estado", "nuevo")).strip().lower()
    if estado not in VALID_ESTADOS:
        estado = "nuevo"

    def _s(key, limit=4000):
        return str(f.get(key, "") or "").strip()[:limit]

    conn = _conn()
    if conn is None:
        return False
    try:
        _ensure_table(conn)
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO lead_fichas
                    (tenant_id, username, crm_text, lead_nombre, lead_contacto,
                     lead_operacion, lead_presupuesto, lead_zona, lead_estado,
                     lead_notas, updated_at)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s, now())
                ON CONFLICT (tenant_id, username) DO UPDATE SET
                    crm_text        = EXCLUDED.crm_text,
                    lead_nombre     = EXCLUDED.lead_nombre,
                    lead_contacto   = EXCLUDED.lead_contacto,
                    lead_operacion  = EXCLUDED.lead_operacion,
                    lead_presupuesto= EXCLUDED.lead_presupuesto,
                    lead_zona       = EXCLUDED.lead_zona,
                    lead_estado     = EXCLUDED.lead_estado,
                    lead_notas      = EXCLUDED.lead_notas,
                    updated_at      = now()
                """,
                (tenant_id or "__legacy__", username,
                 _s("crm_text", 8000), _s("lead_nombre", 200),
                 _s("lead_contacto", 200), _s("lead_operacion", 60),
                 _s("lead_presupuesto", 100), _s("lead_zona", 200),
                 estado, _s("lead_notas", 4000)),
            )
        conn.commit()
        _release(conn)
        return True
    except Exception as exc:
        logger.error(f"lead_fichas save error: {exc}")
        try:
            conn.rollback()
        except Exception:
            pass
        _release(conn, close=True)
        return False


def list_fichas(tenant_id: str = "__legacy__", limit: int = 500) -> list[dict]:
    """
    Lista las fichas de todos los vendedores de un tenant (para el admin/CRM).
    [] si PG no esta disponible.
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
                "SELECT username, lead_nombre, lead_contacto, lead_operacion, "
                "lead_presupuesto, lead_zona, lead_estado, lead_notas, crm_text, updated_at "
                "FROM lead_fichas WHERE tenant_id = %s "
                "ORDER BY updated_at DESC LIMIT %s",
                (tenant_id or "__legacy__", int(limit)),
            )
            rows = cur.fetchall()
        _release(conn)
        out = []
        for r in rows:
            out.append({
                "username": r[0], "lead_nombre": r[1] or "", "lead_contacto": r[2] or "",
                "lead_operacion": r[3] or "", "lead_presupuesto": r[4] or "",
                "lead_zona": r[5] or "", "lead_estado": r[6] or "nuevo",
                "lead_notas": r[7] or "", "crm_text": r[8] or "",
                "updated_at": r[9].isoformat() if hasattr(r[9], "isoformat") else str(r[9]),
            })
        return out
    except Exception as exc:
        logger.error(f"lead_fichas list error: {exc}")
        try:
            conn.rollback()
        except Exception:
            pass
        _release(conn, close=True)
        return []
