# -*- coding: utf-8 -*-
"""
message_store_pg.py — Buzon de consultas/sugerencias de los vendedores hacia el
administrador, persistido en PostgreSQL.

QUE ES
------
Un vendedor puede enviar una consulta ("necesito ayuda") o una sugerencia desde
un widget de chat guiado. El mensaje se guarda aca y el administrador lo ve como
notificacion cuando entra. NO es un chatbot con IA: es un buzon unidireccional
vendedor -> admin (mas un "leido/resuelto" del lado admin).

Multi-tenant: cada mensaje pertenece a un tenant_id, asi el admin de una empresa
solo ve los mensajes de SU empresa. Reutiliza el pool de history_manager. Todo
best-effort: un fallo nunca rompe la accion del usuario.
"""
from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

_table_ready = False

VALID_KINDS = {"ayuda", "sugerencia"}


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
            CREATE TABLE IF NOT EXISTS user_messages (
                id         BIGSERIAL   PRIMARY KEY,
                tenant_id  TEXT        NOT NULL DEFAULT '__legacy__',
                from_user  TEXT        NOT NULL,
                kind       TEXT        NOT NULL DEFAULT 'ayuda',
                text       TEXT        NOT NULL,
                image      TEXT        NOT NULL DEFAULT '',
                resolved   BOOLEAN     NOT NULL DEFAULT false,
                ts         TIMESTAMPTZ NOT NULL DEFAULT now()
            )
            """
        )
        # Migracion segura para tablas ya existentes: agregar la columna image
        # (data URL de la foto adjunta, opcional). Vacio = sin imagen.
        cur.execute(
            "ALTER TABLE user_messages ADD COLUMN IF NOT EXISTS image TEXT NOT NULL DEFAULT ''"
        )
        cur.execute(
            "CREATE INDEX IF NOT EXISTS idx_msg_tenant_resolved_ts "
            "ON user_messages (tenant_id, resolved, ts DESC)"
        )
    conn.commit()
    _table_ready = True


# Tope de tamano de la imagen adjunta (data URL). ~1.4 MB de texto base64 ~
# 1 MB de imagen. El cliente ya comprime/redimensiona antes de enviar; esto es
# la red de seguridad del backend para no inflar la base.
_MAX_IMAGE_CHARS = 1_400_000


def sanitize_image(image: str) -> str:
    """
    Valida y normaliza la imagen adjunta (data URL). Funcion PURA (sin PG), para
    poder testearla de forma aislada. Devuelve la imagen si es valida, o '' si:
      - esta vacia,
      - no es un data URL de imagen ('data:image/...'),
      - supera el tope de tamano (_MAX_IMAGE_CHARS).
    """
    image = (image or "").strip()
    if not image:
        return ""
    if not image.startswith("data:image/"):
        return ""
    if len(image) > _MAX_IMAGE_CHARS:
        return ""
    return image


def add_message(from_user: str, text: str, kind: str = "ayuda",
                tenant_id: str = "__legacy__", image: str = "") -> bool:
    """
    Guarda un mensaje del vendedor, con imagen adjunta OPCIONAL (data URL).
    Best-effort: nunca lanza.
    """
    text = (text or "").strip()
    if not from_user or not text or not is_available():
        return False
    if kind not in VALID_KINDS:
        kind = "ayuda"
    # Validar la imagen: solo data URLs de imagen y dentro del tope de tamano.
    image = sanitize_image(image)
    conn = _conn()
    if conn is None:
        return False
    try:
        _ensure_table(conn)
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO user_messages (tenant_id, from_user, kind, text, image) "
                "VALUES (%s, %s, %s, %s, %s)",
                (tenant_id or "__legacy__", from_user, kind, text[:2000], image),
            )
        conn.commit()
        _release(conn)
        return True
    except Exception as exc:
        logger.error(f"user_messages add error: {exc}")
        try:
            conn.rollback()
        except Exception:
            pass
        _release(conn, close=True)
        return False


def list_messages(tenant_id: str = "__legacy__", only_unresolved: bool = True,
                  limit: int = 100) -> list[dict]:
    """
    Mensajes de UN tenant, mas recientes primero. Si only_unresolved, solo los
    no resueltos. [] si PG no esta disponible.
    """
    if not is_available():
        return []
    conn = _conn()
    if conn is None:
        return []
    try:
        _ensure_table(conn)
        where = "tenant_id = %s"
        params = [tenant_id or "__legacy__"]
        if only_unresolved:
            where += " AND resolved = false"
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, from_user, kind, text, resolved, ts, image FROM user_messages "
                "WHERE " + where + " ORDER BY ts DESC LIMIT %s",
                tuple(params) + (int(limit),),
            )
            rows = cur.fetchall()
        _release(conn)
        out = []
        for r in rows:
            out.append({
                "id": r[0], "from_user": r[1], "kind": r[2], "text": r[3],
                "resolved": bool(r[4]),
                "ts": r[5].isoformat() if hasattr(r[5], "isoformat") else str(r[5]),
                "image": r[6] or "",
            })
        return out
    except Exception as exc:
        logger.error(f"user_messages list error: {exc}")
        try:
            conn.rollback()
        except Exception:
            pass
        _release(conn, close=True)
        return []


def count_unresolved(tenant_id: str = "__legacy__") -> int:
    """Cantidad de mensajes sin resolver de un tenant (para el badge)."""
    if not is_available():
        return 0
    conn = _conn()
    if conn is None:
        return 0
    try:
        _ensure_table(conn)
        with conn.cursor() as cur:
            cur.execute(
                "SELECT COUNT(*) FROM user_messages "
                "WHERE tenant_id = %s AND resolved = false",
                (tenant_id or "__legacy__",),
            )
            n = cur.fetchone()[0]
        _release(conn)
        return int(n or 0)
    except Exception as exc:
        logger.error(f"user_messages count error: {exc}")
        try:
            conn.rollback()
        except Exception:
            pass
        _release(conn, close=True)
        return 0


def mark_resolved(message_id: int, tenant_id: str = "__legacy__") -> bool:
    """
    Marca un mensaje como resuelto, SOLO si pertenece al tenant dado (un admin de
    una empresa no puede tocar mensajes de otra).
    """
    if not is_available():
        return False
    conn = _conn()
    if conn is None:
        return False
    try:
        _ensure_table(conn)
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE user_messages SET resolved = true "
                "WHERE id = %s AND tenant_id = %s",
                (int(message_id), tenant_id or "__legacy__"),
            )
            ok = cur.rowcount > 0
        conn.commit()
        _release(conn)
        return ok
    except Exception as exc:
        logger.error(f"user_messages resolve error: {exc}")
        try:
            conn.rollback()
        except Exception:
            pass
        _release(conn, close=True)
        return False
